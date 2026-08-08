"""Terminal capabilities and a very small ANSI toolkit.

Nothing here knows what GitFoot displays. The renderer owns the layout and asks
this module only three things: may I use colour, how many colours, and which
glyphs survive this terminal. Keeping those apart is what lets the dashboard be
tested as plain text -- build a ``Term`` with colour off and the output is
diffable.

There is no dependency here on purpose. Colour detection and padding are forty
lines of stdlib; pulling in a rendering library to get them would cost more than
it returns.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from typing import IO

# Matches SGR sequences only, which is all we emit. Cursor movement and the rest
# of the ANSI zoo never appear in a string GitFoot produces.
_SGR = re.compile(r"\x1b\[[0-9;]*m")

RESET = "\x1b[0m"

# A dashboard that needs more than 100 columns is a dashboard with too much on
# it; below 40 no amount of cleverness helps.
MIN_WIDTH = 40
MAX_WIDTH = 100
FALLBACK_WIDTH = 80


class Depth(IntEnum):
    """How many colours the terminal can be trusted with."""

    NONE = 0
    ANSI16 = 1
    ANSI256 = 2
    TRUECOLOR = 3


@dataclass(frozen=True)
class Color:
    """One colour, expressed once per capability tier.

    Stating all three up front beats computing the fallbacks: the 256-colour
    cube approximation of a hand-picked RGB value is usually worse than the
    xterm index a human would have chosen.
    """

    rgb: tuple[int, int, int]
    xterm: int  # 0-255
    ansi: int  # SGR foreground code, 30-37 or 90-97

    def sgr(self, depth: Depth) -> str:
        """The SGR parameter fragment for this colour at ``depth``."""
        if depth is Depth.TRUECOLOR:
            r, g, b = self.rgb
            return f"38;2;{r};{g};{b}"
        if depth is Depth.ANSI256:
            return f"38;5;{self.xterm}"
        return str(self.ansi)


@dataclass(frozen=True)
class Theme:
    """The complete colour vocabulary. If it is not here, it is not coloured.

    Everything structural -- labels, units, separators -- rides on the ``dim``
    attribute with no colour at all, so it inherits the user's own foreground
    and stays legible on light and dark backgrounds alike. Colour is reserved
    for the two things where it carries information: activity level and the
    direction of a line change.
    """

    muted: Color
    added: Color
    removed: Color
    ok: Color
    bad: Color
    ramp: tuple[Color, Color, Color, Color, Color]  # activity levels 0-4


# Mid-luminance greens. A ramp tuned for a dark background (GitHub's, say)
# collapses into the page on a light one, so these sit near 45-50% lightness
# where both backgrounds keep some contrast. The glyph ramp carries the same
# information in parallel, which is what makes the heatmap survive `| cat`.
DEFAULT_THEME = Theme(
    muted=Color(rgb=(128, 128, 128), xterm=244, ansi=90),
    added=Color(rgb=(74, 155, 100), xterm=71, ansi=32),
    removed=Color(rgb=(192, 91, 91), xterm=167, ansi=31),
    ok=Color(rgb=(74, 155, 100), xterm=71, ansi=32),
    bad=Color(rgb=(192, 91, 91), xterm=167, ansi=31),
    ramp=(
        Color(rgb=(96, 96, 96), xterm=240, ansi=90),
        Color(rgb=(78, 121, 96), xterm=65, ansi=32),
        Color(rgb=(74, 155, 100), xterm=71, ansi=32),
        Color(rgb=(63, 186, 108), xterm=77, ansi=92),
        Color(rgb=(46, 216, 122), xterm=83, ansi=92),
    ),
)


@dataclass(frozen=True)
class Glyphs:
    """The characters the renderer is allowed to use.

    ``heat`` is indexed by activity level 0-4. Level 0 is deliberately a mark
    rather than a block: a tracked day with no commits should read as quiet, not
    as a wall.
    """

    unicode: bool
    heat: tuple[str, str, str, str, str]
    blank: str  # untracked or future day -- absent, not zero
    minus: str
    dot: str  # separator between figures
    ellipsis: str
    tick: str  # marks an entry as tracked


UNICODE_GLYPHS = Glyphs(
    unicode=True,
    heat=("·", "░", "▒", "▓", "█"),  # · ░ ▒ ▓ █
    blank=" ",
    minus="−",  # a real minus, not a hyphen
    dot="·",
    ellipsis="…",
    tick="✓",
)

ASCII_GLYPHS = Glyphs(
    unicode=False,
    heat=(".", ":", "+", "*", "#"),  # ink coverage stands in for colour
    blank=" ",
    minus="-",
    dot="|",
    ellipsis="...",
    tick="*",
)

# Probe string: if the encoding takes these, it takes everything we emit.
_PROBE = (
    "".join(UNICODE_GLYPHS.heat)
    + UNICODE_GLYPHS.minus
    + UNICODE_GLYPHS.ellipsis
    + UNICODE_GLYPHS.tick
)


class Terminal:
    """A resolved terminal: what it can display, and how to say it.

    Capabilities are worked out once at construction and then fixed, so a render
    cannot change its mind halfway down the page. Every automatic decision has an
    explicit override, because detection is a guess and the user is not:
    ``Terminal(color=False)`` is what ``--no-color`` passes.
    """

    __slots__ = ("depth", "glyphs", "theme", "width")

    def __init__(
        self,
        *,
        color: bool | None = None,
        unicode: bool | None = None,
        width: int | None = None,
        depth: Depth | None = None,
        stream: IO[str] | None = None,
        env: Mapping[str, str] | None = None,
        theme: Theme = DEFAULT_THEME,
    ) -> None:
        out = stream if stream is not None else sys.stdout
        environ = env if env is not None else os.environ

        self.depth = depth if depth is not None else _detect_depth(out, color, environ)
        self.glyphs = _detect_glyphs(out, unicode, environ)
        self.width = _detect_width(width)
        self.theme = theme

    def __repr__(self) -> str:
        return (
            f"Terminal(depth={self.depth.name}, unicode={self.unicode}, width={self.width})"
        )

    @property
    def color(self) -> bool:
        return self.depth is not Depth.NONE

    @property
    def unicode(self) -> bool:
        return self.glyphs.unicode

    # -- styling ---------------------------------------------------------

    def style(
        self,
        text: str,
        fg: Color | None = None,
        *,
        dim: bool = False,
        bold: bool = False,
    ) -> str:
        """Wrap ``text`` in the requested attributes, or return it untouched.

        Empty strings are passed through so callers can style optional fragments
        without producing a bare escape pair that pads the visible length by
        zero but the byte length by nine.
        """
        if not text or self.depth is Depth.NONE:
            return text

        params: list[str] = []
        if bold:
            params.append("1")
        if dim:
            params.append("2")
        if fg is not None:
            params.append(fg.sgr(self.depth))
        if not params:
            return text
        return f"\x1b[{';'.join(params)}m{text}{RESET}"

    # -- measurement and alignment ---------------------------------------

    def ljust(self, text: str, width: int, fill: str = " ") -> str:
        return text + fill * max(0, width - visible_len(text))

    def rjust(self, text: str, width: int, fill: str = " ") -> str:
        return fill * max(0, width - visible_len(text)) + text

    def center(self, text: str, width: int) -> str:
        pad = max(0, width - visible_len(text))
        left = pad // 2
        return " " * left + text + " " * (pad - left)

    def truncate(self, text: str, width: int) -> str:
        """Cut plain text to ``width`` visible columns, marking the cut.

        Not escape-aware: truncate before styling, never after.
        """
        if visible_len(text) <= width:
            return text
        mark = self.ellipsis_for(width)
        budget = width - visible_len(mark)
        if budget <= 0:
            return mark[:width]
        out: list[str] = []
        used = 0
        for ch in text:
            w = _char_width(ch)
            if used + w > budget:
                break
            out.append(ch)
            used += w
        return "".join(out) + mark

    def ellipsis_for(self, width: int) -> str:
        """The widest ellipsis that still leaves room for content."""
        mark = self.glyphs.ellipsis
        return mark if width > visible_len(mark) else ""


def visible_len(text: str) -> int:
    """Printed width of ``text``, ignoring escapes and counting wide chars.

    Repo names come from the filesystem and can hold anything, CJK included, so
    column arithmetic has to ask the character how wide it is rather than count
    code points.
    """
    return sum(_char_width(ch) for ch in strip_ansi(text))


def strip_ansi(text: str) -> str:
    return _SGR.sub("", text)


def sanitize(text: str) -> str:
    """Strip control characters from text GitFoot did not write itself.

    Author emails, repository names and git's own error messages all end up on
    screen, and all three are chosen by whoever made the repository. A carriage
    return or an OSC sequence in an email address lets a commit redraw the line
    it is printed on. That matters most at the ``gitfoot init`` prompt, where
    the user picks an identity by number from a list of these strings: an entry
    that repaints itself to look like the user's own address gets added to the
    identity list by hand.

    Escapes are removed rather than made visible, because the point is a clean
    line, not a forensic transcript. Width arithmetic is a separate concern and
    lives in ``visible_len``.
    """
    return "".join(
        ch for ch in text if ch.isprintable() or ch == " "
    ).strip()


def _char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    # 'A' (ambiguous) covers the shading blocks. Treating it as narrow is right
    # for every terminal outside a CJK locale, and being wrong there costs
    # alignment, not correctness.
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


# -- capability detection ------------------------------------------------


def _detect_depth(stream: IO[str], override: bool | None, env: Mapping[str, str]) -> Depth:
    if override is False:
        return Depth.NONE

    if override is None:
        # NO_COLOR wins over FORCE_COLOR. Both are user intent, but one of them
        # is a promise the ecosystem made about accessibility, and the other is
        # usually set by a CI image the user never looked at.
        if "NO_COLOR" in env:
            return Depth.NONE

        forced = env.get("FORCE_COLOR")
        if forced is not None:
            value = forced.strip().lower()
            if value in ("0", "false", "no", "none"):
                return Depth.NONE
            if value == "1":
                return Depth.ANSI16
            if value == "2":
                return Depth.ANSI256
            if value == "3":
                return Depth.TRUECOLOR
        elif env.get("TERM", "").lower() == "dumb" or not _isatty(stream):
            return Depth.NONE

    return _depth_from_env(env)


def _depth_from_env(env: Mapping[str, str]) -> Depth:
    colorterm = env.get("COLORTERM", "").lower()
    if "truecolor" in colorterm or "24bit" in colorterm:
        return Depth.TRUECOLOR

    term = env.get("TERM", "").lower()
    if "direct" in term:  # e.g. xterm-direct, the terminfo way of saying 24-bit
        return Depth.TRUECOLOR
    if "256" in term:
        return Depth.ANSI256
    return Depth.ANSI16


def _detect_glyphs(stream: IO[str], override: bool | None, env: Mapping[str, str]) -> Glyphs:
    if override is not None:
        return UNICODE_GLYPHS if override else ASCII_GLYPHS
    if env.get("TERM", "").lower() == "dumb":
        return ASCII_GLYPHS

    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        _PROBE.encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return ASCII_GLYPHS
    return UNICODE_GLYPHS


def _detect_width(override: int | None) -> int:
    if override is None:
        override = shutil.get_terminal_size((FALLBACK_WIDTH, 24)).columns
    return max(MIN_WIDTH, min(MAX_WIDTH, override))


def _isatty(stream: IO[str]) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):  # closed or substituted stream
        return False
