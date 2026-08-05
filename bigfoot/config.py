"""Paths, configuration, and author identity.

Config lives at ``$XDG_CONFIG_HOME/bigfoot/config.toml`` and is read with the
stdlib ``tomllib``. It is written by hand -- the schema is four keys, and a TOML
writer is not worth a dependency.

Set ``BIGFOOT_HOME`` to relocate both config and data (useful for tests and for
keeping BigFoot inside a dotfiles repo).
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

# Directory names never descended into when looking for repositories.
#
# This is a plain list rather than a heuristic on purpose. An earlier version
# skipped every dot-directory, which was fast and wrong: it lost dotfiles repos
# and things like ~/.config/nvim. A list you can read and edit beats a rule you
# have to reverse-engineer from surprising results.
DEFAULT_IGNORE_DIRS: tuple[str, ...] = (
    # package managers and build output
    "node_modules",
    "bower_components",
    "vendor",
    "site-packages",
    "target",
    "dist",
    "build",
    "__pycache__",
    # virtualenvs and toolchains
    "venv",
    ".venv",
    ".tox",
    ".nox",
    ".pyenv",
    ".rbenv",
    ".nvm",
    ".npm",
    ".cargo",
    ".rustup",
    ".gem",
    ".m2",
    ".gradle",
    ".stack",
    # caches and machine state
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".terraform",
    ".Trash",
    ".gnupg",
    ".ssh",
    # other VCS metadata
    ".svn",
    ".hg",
    # platform junk
    "Library",
    "AppData",
    "snap",
    "flatpak",
)

DEFAULT_MAX_DEPTH = 6


def _home() -> Path | None:
    override = os.environ.get("BIGFOOT_HOME")
    return Path(override).expanduser() if override else None


def config_dir() -> Path:
    """Directory holding ``config.toml``."""
    override = _home()
    if override:
        return override
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".config"
    return root / "bigfoot"


def data_dir() -> Path:
    """Directory holding ``bigfoot.db``."""
    override = _home()
    if override:
        return override
    base = os.environ.get("XDG_DATA_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "share"
    return root / "bigfoot"


def config_path() -> Path:
    return config_dir() / "config.toml"


def db_path() -> Path:
    return data_dir() / "bigfoot.db"


@dataclass
class Config:
    """Resolved configuration.

    ``roots`` are the directories scanned for git repositories. An empty list
    means the user has not chosen any yet -- BigFoot asks rather than guessing,
    because silently walking someone's home directory is not ours to do.
    """

    roots: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    ignore_dirs: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_DIRS))
    max_depth: int = DEFAULT_MAX_DEPTH
    path: Path = field(default_factory=config_path)

    @property
    def configured(self) -> bool:
        return bool(self.roots)

    def root_paths(self) -> list[Path]:
        return [Path(r).expanduser() for r in self.roots]


def load(path: Path | None = None) -> Config:
    """Read config from disk. A missing or unreadable file yields defaults."""
    target = path or config_path()
    if not target.is_file():
        return Config(path=target)

    try:
        with open(target, "rb") as fh:
            raw = tomllib.load(fh)
    except (OSError, ValueError):
        # ValueError covers TOMLDecodeError and the UnicodeDecodeError tomllib
        # raises on a file that is not valid UTF-8. A corrupt config should
        # cost you your settings, not every command.
        return Config(path=target)

    return Config(
        roots=_str_list(raw.get("roots")),
        emails=_str_list(raw.get("emails")),
        ignore_dirs=_str_list(raw.get("ignore_dirs")) or list(DEFAULT_IGNORE_DIRS),
        max_depth=_positive_int(raw.get("max_depth"), DEFAULT_MAX_DEPTH),
        path=target,
    )


def save(cfg: Config) -> Path:
    """Write config to disk, creating the directory if needed."""
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    body = [
        "# BigFoot configuration",
        "# https://github.com/tksimson/bigfoot",
        "",
        "# Directories scanned for git repositories.",
        _toml_array("roots", cfg.roots),
        "",
        "# Commits are yours if the author email is in this list.",
        _toml_array("emails", cfg.emails),
        "",
        "# Directory names never descended into.",
        _toml_array("ignore_dirs", cfg.ignore_dirs),
        "",
        "# How deep below each root to look.",
        f"max_depth = {cfg.max_depth}",
        "",
    ]
    # Written via a temporary file so an interrupted save cannot leave a
    # half-written config behind, and mode 0600 because the contents map every
    # project directory on the machine plus every colleague email seen in a
    # shared repo. Not secret, but nobody else's business on a shared host.
    tmp = cfg.path.with_suffix(".toml.tmp")
    tmp.write_text("\n".join(body), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(cfg.path)
    return cfg.path


def with_emails(cfg: Config, emails: list[str]) -> Config:
    """Return a copy with ``emails`` merged in, deduplicated, order preserved."""
    return replace(cfg, emails=dedupe(cfg.emails + emails))


def with_roots(cfg: Config, roots: list[str]) -> Config:
    """Return a copy with ``roots`` merged in, normalised to absolute paths."""
    resolved = [str(Path(r).expanduser().resolve()) for r in roots]
    return replace(cfg, roots=dedupe(cfg.roots + resolved))


def git_emails() -> list[str]:
    """Email addresses git is configured to sign your commits with.

    This is the *only* automatic source of identity. The previous implementation
    harvested every author from recent history, which meant a shared repo made
    your colleagues' commits indistinguishable from your own.
    """
    found: list[str] = []
    for scope in ("--global", "--system"):
        value = _git_config(scope, "user.email")
        if value:
            found.append(value)
    return dedupe(found)


def _git_config(scope: str, key: str, cwd: Path | None = None) -> str | None:
    try:
        result = subprocess.run(
            ["git", "config", scope, "--get", key],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=str(cwd) if cwd else None,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value or None


def dedupe(items: list[str]) -> list[str]:
    """Drop blanks and case-insensitive duplicates, keeping the first spelling."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            out.append(key)
    return out


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _positive_int(value: object, fallback: int) -> int:
    # bool is a subclass of int, so `max_depth = true` would otherwise load as
    # a depth of 1 and quietly scan almost nothing.
    if isinstance(value, bool) or not isinstance(value, int):
        return fallback
    return value if value > 0 else fallback


def _toml_array(name: str, values: list[str]) -> str:
    if not values:
        return f"{name} = []"
    items = "".join(f'  "{_escape(v)}",\n' for v in values)
    return f"{name} = [\n{items}]"


def _escape(value: str) -> str:
    """Escape a value for a TOML basic string.

    Control characters are illegal raw in TOML, and ``load`` falls back to
    defaults on a parse error. Writing one unescaped would therefore not just
    corrupt the file, it would make BigFoot look unconfigured, and the next
    save would overwrite the settings for good.
    """
    out = value.replace("\\", "\\\\").replace('"', '\\"')
    return "".join(ch if ch.isprintable() else f"\\u{ord(ch):04X}" for ch in out)
