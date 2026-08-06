"""Dashboard rendering.

Every function here returns a string. Nothing prints, nothing touches the
database, nothing recomputes a statistic -- the numbers arrive settled in a
``Snapshot`` and this module only decides where they sit on the line. That is
what makes the layout testable: render a fixed snapshot into a colourless
``Terminal`` and compare the text.

The visual rules, in short: alignment does the structuring, so there are no
boxes; ``dim`` does the de-emphasis, so labels inherit the user's own
foreground; colour appears only where it means something.

Every block returned here carries its own top margin and ends without a
trailing newline, so a caller writes ``print(render.dashboard(...))`` and gets
the spacing the layout intends.
"""

from __future__ import annotations

import textwrap
from datetime import date

from . import stats
from .store import DayStat, RepoStat
from .term import Terminal, visible_len

INDENT = "  "
LABEL_W = 12  # width of the "Today / Streak / This week" column
ROW_LABEL_W = 5  # width of the "Mon / Wed / Fri" column
GRID_ORIGIN = len(INDENT) + ROW_LABEL_W  # first column of the heatmap
MONTH_OVERHANG = 3  # how far a month label may extend past the last week

# The block has a natural width of its own. Letting the footer stretch to the
# full width of a maximised terminal pulls the totals miles away from the grid
# they describe, so the right margin stops here unless the grid is wider.
CONTENT_WIDTH = 72

# Weekday rows that get a label, GitHub-style. The others still occupy a row.
LABELLED_ROWS = (0, 2, 4)

MAX_ACTIVE_REPOS = 3
MAX_REPO_NAME = 16


def dashboard(snapshot: stats.Snapshot, term: Terminal, weeks: int | None = None) -> str:
    """The whole view: three figures, a heatmap, a legend.

    ``weeks`` caps how many columns are drawn. ``None`` means "as many as the
    snapshot holds and the terminal can take".
    """
    blocks = [
        headline(snapshot, term),
        heatmap(snapshot.grid, term, weeks),
        legend(snapshot, term, weeks),
    ]
    return "\n" + "\n\n".join(b for b in blocks if b)


# -- headline ------------------------------------------------------------


def headline(snapshot: stats.Snapshot, term: Terminal) -> str:
    """The three lines that answer "how am I doing" without scrolling."""
    rows: list[tuple[str, str, list[str]]] = [
        ("Today", _num(snapshot.today.commits), _today_parts(snapshot.today, term)),
        ("Streak", _num(snapshot.streak.current), _streak_parts(snapshot.streak, term)),
        ("This week", _num(snapshot.week.commits), _week_parts(snapshot, term)),
    ]

    # Right-align the leading figure across the rows so the digits form a column
    # instead of drifting with the length of the number above.
    num_w = max(visible_len(n) for _, n, _ in rows)
    gutter = len(INDENT) + LABEL_W + num_w + 1

    lines = [
        INDENT
        + term.ljust(label, LABEL_W)
        + term.rjust(num, num_w)
        + " "
        + _fit_parts(parts, term, gutter)
        for label, num, parts in rows
    ]

    # The week's repos continue the line above rather than earning a label of
    # their own: the indent already says which figure they belong to.
    repos = _repo_parts(snapshot.top_repos, term)
    if repos:
        lines.append(" " * gutter + _fit_parts(repos, term, gutter))
    return "\n".join(lines)


def _today_parts(today: DayStat, term: Terminal) -> list[str]:
    parts = [term.style(_unit(today.commits, "commit"), dim=True)]
    if today.commits:
        parts.append(_count(term, today.repos, "repo"))
        parts.append(_churn(today, term))
    return parts


def _streak_parts(streak: stats.Streak, term: Terminal) -> list[str]:
    parts = [
        term.style(_unit(streak.current, "day"), dim=True),
        term.style("longest", dim=True) + " " + _num(streak.longest),
    ]
    if not streak.alive and streak.last_active:
        parts.append(term.style("last", dim=True) + " " + _day_name(streak.last_active))
    return parts


def _week_parts(snapshot: stats.Snapshot, term: Terminal) -> list[str]:
    days = (
        _num(snapshot.active_this_week)
        + " "
        + term.style("of", dim=True)
        + " 7 "
        + term.style("days", dim=True)
    )
    return [
        term.style(_unit(snapshot.week.commits, "commit"), dim=True),
        days,
        _churn(snapshot.week, term),
    ]


def _repo_parts(repos: list[RepoStat], term: Terminal) -> list[str]:
    """Where the week's commits landed, busiest first."""
    live = [r for r in repos if r.commits > 0][:MAX_ACTIVE_REPOS]
    return [
        term.style(term.truncate(r.name, MAX_REPO_NAME), dim=True) + " " + _num(r.commits)
        for r in live
    ]


def _fit_parts(parts: list[str], term: Terminal, gutter: int) -> str:
    """Join what fits and drop the rest from the right.

    The segments are ordered by how much they matter, so a narrow terminal loses
    the churn before it loses the commit count.
    """
    budget = term.width - gutter
    kept: list[str] = []
    used = 0
    for part in parts:
        if not part:
            continue
        width = visible_len(part) + (3 if kept else 0)
        if kept and used + width > budget:
            break
        kept.append(part)
        used += width
    return _join(kept, term)


# -- heatmap -------------------------------------------------------------


def heatmap(grid: stats.Grid, term: Terminal, weeks: int | None = None) -> str:
    """The activity calendar: weeks left to right, Monday down to Sunday."""
    if not grid.weeks:
        return ""

    columns, step, dropped = _fit(grid, term, weeks)
    if not columns:
        return ""

    width = _grid_width(len(columns), step)
    months = _month_row(grid.month_labels, columns, step, width, dropped, term)

    # Every weekday keeps its row whether or not it is labelled; dropping the
    # quiet ones would shear the grid.
    rows = [_day_row(row, columns, step, grid.peak, term) for row in range(7)]
    return "\n".join(([months] if months else []) + rows)


def _fit(
    grid: stats.Grid, term: Terminal, weeks: int | None
) -> tuple[list[list[stats.Cell]], int, int]:
    """Choose the column spacing and how much history survives the width.

    A blank column between weeks is what gives the month labels room to breathe,
    so it is the last thing given up: first the gap goes, then the oldest weeks.
    Returns the columns kept, the step, and how many leading columns were cut.
    """
    columns = grid.weeks
    dropped = 0
    if weeks is not None and weeks < len(columns):
        dropped = len(columns) - weeks
        columns = columns[dropped:]

    available = term.width - GRID_ORIGIN
    step = 2 if _grid_width(len(columns), 2) <= available else 1
    if _grid_width(len(columns), step) > available:
        keep = max(1, available)
        dropped += len(columns) - keep
        columns = columns[-keep:]
    return columns, step, dropped


def _grid_width(count: int, step: int) -> int:
    """Printed width of ``count`` columns, without a trailing separator."""
    return count * step - (step - 1) if count else 0


def _month_row(
    labels: list[tuple[int, str]],
    columns: list[list[stats.Cell]],
    step: int,
    width: int,
    dropped: int,
    term: Terminal,
) -> str:
    """Month names sitting exactly above the week they start in.

    The one place a terminal heatmap gives itself away is a label row that is
    off by one, so the names are painted into a fixed-width buffer at
    ``column * step`` rather than assembled by joining and hoping.

    The buffer is allowed a few characters past the last column, bounded by the
    real terminal width. Without that slack the current month goes unlabelled
    whenever the year ends mid-month, which at 52 weeks is eleven months out of
    twelve. An overhanging label reads as intentional; a missing one reads as a
    bug, and it is the label the reader cares about most.
    """
    slack = max(0, min(term.width - GRID_ORIGIN - width, MONTH_OVERHANG))
    buffer = [" "] * (width + slack)
    cursor = 0
    for column, name in labels:
        index = column - dropped
        if index < 0:
            continue
        start = index * step
        # Skip a label rather than let it collide with the previous one; at one
        # column per week the months are only four characters apart.
        if start < cursor or start + len(name) > len(buffer):
            continue
        buffer[start : start + len(name)] = list(name)
        cursor = start + len(name) + 1

    row = "".join(buffer).rstrip()
    return " " * GRID_ORIGIN + term.style(row, dim=True) if row else ""


def _day_row(
    row: int,
    columns: list[list[stats.Cell]],
    step: int,
    peak: int,
    term: Terminal,
) -> str:
    """One weekday across every visible week."""
    label = stats.WEEKDAYS[row] if row in LABELLED_ROWS else ""
    cells = _cells(row, columns, step, peak, term)
    return (INDENT + term.ljust(label, ROW_LABEL_W) + cells).rstrip()


def _cells(row: int, columns: list[list[stats.Cell]], step: int, peak: int, term: Terminal) -> str:
    """Render one row's cells, merging neighbours that share a level.

    Runs are merged because a per-character escape sequence turns a 26-column
    row into two kilobytes of noise the moment anyone pipes it into a file.
    """
    out: list[str] = []
    run: list[str] = []
    run_level: int | None = None
    gap = " " * (step - 1)

    for index, week in enumerate(columns):
        cell = week[row]
        if cell.in_range:
            level: int | None = stats.level(cell.commits, peak)
            glyph = term.glyphs.heat[level]
        else:
            # Not tracked yet, or still in the future. Absent, which is a
            # different statement from a zero-commit day.
            level = None
            glyph = term.glyphs.blank

        if level != run_level and run:
            out.append(_paint(run, run_level, term))
            run = []
        run_level = level
        run.append(glyph if index == len(columns) - 1 else glyph + gap)

    if run:
        out.append(_paint(run, run_level, term))
    return "".join(out)


def _paint(run: list[str], level: int | None, term: Terminal) -> str:
    text = "".join(run)
    if level is None:
        return text
    # Level 0 is dimmed as well as greyed: a tracked day with no commits should
    # recede, and dim is the one attribute that behaves on light backgrounds.
    return term.style(text, term.theme.ramp[level], dim=level == 0)


# -- legend --------------------------------------------------------------


def legend(snapshot: stats.Snapshot, term: Terminal, weeks: int | None = None) -> str:
    """The colour key on the left, the totals for the window on the right.

    The right edge is the terminal's, mirroring the left margin, rather than the
    grid's: the totals are about the whole view, and hanging them off the last
    week column would make the line look accidentally short.
    """
    columns, step, _ = _fit(snapshot.grid, term, weeks)
    key = _ramp_key(term)
    right_edge = min(
        term.width - len(INDENT),
        max(GRID_ORIGIN + _grid_width(len(columns), step), CONTENT_WIDTH),
    )

    if not columns:
        return INDENT + _totals(snapshot, columns, term, full=True)

    totals = ""
    for full in (True, False):
        totals = _totals(snapshot, columns, term, full=full)
        slack = right_edge - GRID_ORIGIN - visible_len(key) - visible_len(totals)
        if slack >= 4:
            return " " * GRID_ORIGIN + key + " " * slack + totals
    return " " * GRID_ORIGIN + key + "\n" + " " * GRID_ORIGIN + totals


def _ramp_key(term: Terminal) -> str:
    swatches = "".join(
        term.style(glyph, term.theme.ramp[i], dim=i == 0)
        for i, glyph in enumerate(term.glyphs.heat)
    )
    return term.style("Less ", dim=True) + swatches + term.style(" More", dim=True)


def _totals(
    snapshot: stats.Snapshot,
    columns: list[list[stats.Cell]],
    term: Terminal,
    full: bool = True,
) -> str:
    """Totals for exactly the window drawn, so the figures match the picture.

    The repository count comes from the snapshot's window rather than from the
    cells, which carry commits only. All-time would be wrong here: quoting "38
    repos" beside thirteen weeks of commits invites the reader to divide one by
    the other and get a number that means nothing.
    """
    commits = sum(cell.commits for week in columns for cell in week if cell.in_range)
    window = _count(term, len(columns), "week")
    parts = [
        _count(term, commits, "commit"),
        _count(term, snapshot.window.repos, "repo"),
        (term.style("last ", dim=True) + window) if full else window,
    ]
    return _join(parts, term)


# -- empty states --------------------------------------------------------


def first_run(term: Terminal, configured: bool = False) -> str:
    """Nothing to show yet: one sentence, one command, nothing else.

    The two ways of having no data need different next steps, which is the only
    reason this branches at all.
    """
    if configured:
        return empty_state(term)
    return _prompt(
        term,
        "Not watching any directories yet.",
        "gitfoot init",
        "Picks the folders your git repositories live in.",
    )


def empty_state(term: Terminal, command: str = "gitfoot sync") -> str:
    """Configured, but the database is empty."""
    return _prompt(
        term,
        "No commits recorded yet.",
        command,
        "Reads your repositories and records the commits authored by you.",
    )


def _prompt(term: Terminal, situation: str, command: str, explanation: str) -> str:
    lines = ["", *_wrap(term, situation), "", INDENT + INDENT + command, ""]
    lines += [term.style(line, dim=True) for line in _wrap(term, explanation)]
    return "\n".join(lines)


def _wrap(term: Terminal, text: str) -> list[str]:
    """Prose, wrapped to the terminal and indented like everything else."""
    wrapped = textwrap.wrap(
        text,
        width=max(24, term.width),
        initial_indent=INDENT,
        subsequent_indent=INDENT,
    )
    return wrapped or [""]


# -- the other commands --------------------------------------------------


def sync_summary(
    term: Terminal,
    repositories: int,
    added: int,
    total: int,
    elapsed: float,
    errors: list[tuple[str, str]],
) -> str:
    """What a sync did. One line when it worked, plus the failures when it did not."""
    parts = [
        _count(term, repositories, "repo"),
        _num(added) + " " + term.style("new", dim=True),
        _num(total) + " " + term.style("total", dim=True),
        term.style(f"{elapsed:.1f}s", dim=True),
    ]
    gutter = len(INDENT) + LABEL_W
    lines = ["", INDENT + term.ljust("Synced", LABEL_W) + _fit_parts(parts, term, gutter)]

    if errors:
        lines.append("")
        width = min(MAX_REPO_NAME, max(visible_len(name) for name, _ in errors))
        for index, (name, message) in enumerate(errors):
            label = "Failed" if index == 0 else ""
            lines.append(
                INDENT
                + term.ljust(label, LABEL_W)
                + term.ljust(term.truncate(name, width), width + 2)
                + term.style(_one_line(term, message, term.width - LABEL_W - width - 4), dim=True)
            )
    return "\n".join(lines)


def repo_list(
    term: Terminal, roots: list[str], repos: list[RepoStat], total: int | None = None
) -> str:
    """Every tracked repository, busiest first, with the roots they came from.

    ``total`` is the distinct commit count. Summing the per-repository figures
    would overcount a commit that two repositories can both see, and then the
    footer here would disagree with the dashboard.
    """
    lines = [""] + _labelled(term, "Scanning", roots, "nothing yet")

    if not repos:
        lines += ["", INDENT + term.style("No repositories recorded yet.", dim=True)]
        return "\n".join(lines)

    count_w = max(visible_len(_num(r.commits)) for r in repos)
    name_w = max(
        4,
        min(
            max(visible_len(r.name) for r in repos),
            term.width - len(INDENT) - count_w - 12,
        ),
    )
    lines.append("")
    for repo in repos:
        seen = _day_name(repo.last_commit) if repo.last_commit else ""
        lines.append(
            INDENT
            + term.ljust(term.truncate(repo.name, name_w), name_w + 2)
            + term.rjust(_num(repo.commits), count_w)
            + "  "
            + term.style(seen, dim=True)
        )

    if total is None:
        total = sum(r.commits for r in repos)
    lines += [
        "",
        INDENT + _join([_count(term, len(repos), "repo"), _count(term, total, "commit")], term),
    ]
    return "\n".join(lines)


def config_view(term: Terminal, cfg: object, database: object) -> str:
    """Where everything lives and who counts as you.

    ``cfg`` is a ``config.Config``; it is typed loosely so the renderer stays a
    leaf module that imports nothing from the rest of the package.
    """
    rows = [
        ("Config", [str(getattr(cfg, "path", ""))], ""),
        ("Database", [str(database)], ""),
        ("Scanning", list(getattr(cfg, "roots", [])), "nothing yet"),
        ("Identity", list(getattr(cfg, "emails", [])), "nobody yet"),
        ("Depth", [str(getattr(cfg, "max_depth", ""))], ""),
    ]

    lines = [""]
    for label, values, fallback in rows:
        lines += _labelled(term, label, values, fallback)
    return "\n".join(lines)


def init_roots(term: Terminal, suggested: list[str]) -> str:
    """The directories GitFoot proposes to scan, before it scans anything."""
    lines = ["", INDENT + "Found these project directories:", ""]
    lines += [INDENT + INDENT + _shorten(term, path) for path in suggested]
    return "\n".join(lines)


def init_emails(
    term: Terminal,
    repositories: int,
    mine: list[str],
    others: list[tuple[str, int]],
) -> str:
    """Who wrote the commits, so the user can say which of them are theirs.

    The other authors are numbered from one because the prompt that follows asks
    for those numbers. Renumbering here would silently pick the wrong people.
    """
    lines = [
        "",
        INDENT + term.ljust("Scanned", LABEL_W) + _count(term, repositories, "repo"),
        "",
        INDENT + term.style("Counted as you", dim=True),
    ]
    if mine:
        lines += [INDENT + INDENT + _shorten(term, email) for email in mine]
    else:
        lines.append(INDENT + INDENT + term.style("nobody yet", dim=True))

    if others:
        index_w = len(str(len(others)))
        head = len(INDENT) * 2 + index_w + 2
        count_w = max(visible_len(_count(term, n, "commit")) for _, n in others)
        email_w = max(
            8,
            min(
                max(visible_len(e) for e, _ in others),
                term.width - head - count_w - 2,
            ),
        )
        lines += ["", INDENT + term.style("Also found", dim=True)]
        for index, (email, count) in enumerate(others, start=1):
            lines.append(
                INDENT * 2
                + term.rjust(str(index), index_w)
                + "  "
                + term.ljust(term.truncate(email, email_w), email_w + 2)
                + _count(term, count, "commit")
            )
    return "\n".join(lines)


def doctor(term: Terminal, checks: list[tuple[str, bool, str]]) -> str:
    """One line per check. The verdict is a word, so it survives no-colour."""
    lines = [""]
    for name, healthy, detail in checks:
        mark = term.style("ok", term.theme.ok) if healthy else term.style("no", term.theme.bad)
        lines.append(
            INDENT
            + term.ljust(name, LABEL_W)
            + term.ljust(mark, 4)
            + term.style(_shorten(term, detail, reserve=LABEL_W + 4), dim=True)
        )
    return "\n".join(lines)


def _labelled(term: Terminal, label: str, values: list[str], fallback: str = "") -> list[str]:
    """A labelled row, one value per line.

    Several values stack under the label rather than sharing a line, because a
    list of paths separated by dots is unreadable the moment one of them is long.
    """
    if not values:
        return [INDENT + term.ljust(label, LABEL_W) + term.style(fallback, dim=True)]
    return [
        INDENT + term.ljust(label if index == 0 else "", LABEL_W) + _shorten(term, value)
        for index, value in enumerate(values)
    ]


def _shorten(term: Terminal, text: str, reserve: int = LABEL_W) -> str:
    """Trim a path or address to the line, keeping the informative end.

    A truncated path is only useful if you can still see the leaf, so this cuts
    from the front.
    """
    budget = term.width - len(INDENT) - reserve
    if visible_len(text) <= budget:
        return text
    mark = term.ellipsis_for(budget)
    return mark + text[-(budget - visible_len(mark)) :]


def _one_line(term: Terminal, text: str, width: int) -> str:
    """Collapse a git error to something that fits on one line."""
    return term.truncate(" ".join(text.split()), max(0, width))


# -- small formatting helpers --------------------------------------------


def _num(value: int) -> str:
    return f"{value:,}"


def _unit(count: int, singular: str) -> str:
    return singular if count == 1 else singular + "s"


def _count(term: Terminal, count: int, singular: str) -> str:
    """A figure and its unit: the number carries, the unit recedes."""
    return _num(count) + " " + term.style(_unit(count, singular), dim=True)


def _churn(stat: DayStat, term: Terminal) -> str:
    if not (stat.insertions or stat.deletions):
        return ""
    added = term.style("+" + _num(stat.insertions), term.theme.added)
    removed = term.style(term.glyphs.minus + _num(stat.deletions), term.theme.removed)
    return added + " " + removed


def _join(parts: list[str], term: Terminal) -> str:
    separator = " " + term.style(term.glyphs.dot, dim=True) + " "
    return separator.join(p for p in parts if p)


def _day_name(iso: str) -> str:
    """A date a human reads at a glance: 'Feb 3', not '2026-02-03'."""
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{day:%b} {day.day}"
