"""Analytics.

Everything here is a pure function over dates and counts. Nothing touches git,
the terminal, or the filesystem, which is what makes the streak rules testable
instead of a thing you discover by staring at a dashboard in December.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise

from .store import DayStat, RepoStat, Store

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int
    last_active: str | None

    @property
    def alive(self) -> bool:
        return self.current > 0


@dataclass(frozen=True)
class Cell:
    """One day in the activity grid."""

    day: date
    commits: int
    in_range: bool  # False for grid padding before the first tracked day


@dataclass(frozen=True)
class Grid:
    """Activity calendar: columns are weeks, rows are weekdays."""

    weeks: list[list[Cell]]  # each inner list is 7 cells, Monday first
    month_labels: list[tuple[int, str]]  # (column index, month name)
    peak: int


@dataclass(frozen=True)
class Snapshot:
    """Everything the dashboard needs, resolved in one pass."""

    today: DayStat
    week: DayStat
    month: DayStat
    year: DayStat
    streak: Streak
    grid: Grid
    active_this_week: int
    top_repos: list[RepoStat]
    tracked_repos: int
    first_day: str | None


def streak(active: list[str], today: date | None = None) -> Streak:
    """Current and longest run of consecutive active days.

    A day with no commits *yet* does not break the streak -- only a completed
    day does. So at 9am on a day you have not committed, a streak that ran
    through yesterday still reads as alive. Miss the whole of yesterday and it
    is gone.

    Days in the future are ignored. A commit can legitimately carry tomorrow's
    date -- author dates come from the committer's timezone, so a colleague
    thirteen hours ahead does it routinely, and a clock an hour fast does it by
    accident. Counting from the newest date in the database rather than from
    today would then measure a run that has not happened yet, and quietly keep
    a broken streak alive.
    """
    now = today or date.today()
    days = sorted({d for d in (date.fromisoformat(x) for x in active) if d <= now})
    if not days:
        return Streak(0, 0, None)

    longest = run = 1
    for prev, cur in pairwise(days):
        run = run + 1 if (cur - prev).days == 1 else 1
        longest = max(longest, run)

    last = days[-1]
    gap = (now - last).days
    if gap > 1:
        current = 0
    else:
        current = 1
        cursor = last
        index = len(days) - 2
        while index >= 0 and (cursor - days[index]).days == 1:
            current += 1
            cursor = days[index]
            index -= 1

    return Streak(current=current, longest=longest, last_active=last.isoformat())


def grid(
    counts: dict[str, int],
    weeks: int,
    today: date | None = None,
    first_tracked: date | None = None,
) -> Grid:
    """Build a weeks-wide activity calendar ending on the current week.

    Columns are weeks running left to right, rows are Monday through Sunday.
    Days before ``first_tracked`` are marked out of range so the renderer can
    show them as absent rather than as zero-commit days -- there is a
    difference between "I did not code" and "I was not tracking yet".
    """
    now = today or date.today()
    end_of_week = now + timedelta(days=6 - now.weekday())
    start = end_of_week - timedelta(days=weeks * 7 - 1)

    columns: list[list[Cell]] = []
    labels: list[tuple[int, str]] = []
    last_month = None
    peak = 0

    for w in range(weeks):
        week_start = start + timedelta(days=w * 7)
        cells: list[Cell] = []
        for d in range(7):
            day = week_start + timedelta(days=d)
            n = counts.get(day.isoformat(), 0)
            in_range = day <= now and (first_tracked is None or day >= first_tracked)
            peak = max(peak, n)
            cells.append(Cell(day=day, commits=n, in_range=in_range))
        columns.append(cells)

        # Label a column when its week introduces a new month.
        month = week_start.strftime("%b")
        if month != last_month and week_start.day <= 7:
            labels.append((w, month))
            last_month = month
        elif last_month is None:
            last_month = month

    return Grid(weeks=columns, month_labels=labels, peak=peak)


def level(commits: int, peak: int) -> int:
    """Map a commit count to one of five intensity levels (0-4).

    Thresholds are relative to the user's own peak, so a four-commit day looks
    busy for someone who averages one and ordinary for someone who averages ten.
    """
    if commits <= 0:
        return 0
    if peak <= 1:
        return 4
    ratio = commits / peak
    if ratio <= 0.25:
        return 1
    if ratio <= 0.5:
        return 2
    if ratio <= 0.75:
        return 3
    return 4


def snapshot(store: Store, weeks: int = 26, today: date | None = None) -> Snapshot:
    """Collect every figure the dashboard shows."""
    now = today or date.today()
    iso = now.isoformat()

    week_start = now - timedelta(days=now.weekday())
    month_start = now.replace(day=1)
    year_start = now - timedelta(days=364)

    grid_end = now + timedelta(days=6 - now.weekday())
    grid_start = grid_end - timedelta(days=weeks * 7 - 1)

    days = store.day_stats(grid_start.isoformat(), grid_end.isoformat())
    counts = {d: s.commits for d, s in days.items()}

    active_this_week = sum(
        1
        for offset in range((now - week_start).days + 1)
        if counts.get((week_start + timedelta(days=offset)).isoformat(), 0) > 0
    )

    first = store.first_day()
    first_tracked = date.fromisoformat(first) if first else None

    return Snapshot(
        today=days.get(iso, DayStat(iso, 0, 0, 0, 0)),
        week=store.range_total(week_start.isoformat(), iso),
        month=store.range_total(month_start.isoformat(), iso),
        year=store.range_total(year_start.isoformat(), iso),
        streak=streak(store.active_days(), now),
        grid=grid(counts, weeks, now, first_tracked),
        active_this_week=active_this_week,
        top_repos=store.repo_stats(week_start.isoformat(), iso)[:5],
        tracked_repos=len(store.repos()),
        first_day=first,
    )
