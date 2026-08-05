"""Streaks, the activity grid, and intensity levels.

Streak rules are the thing users argue about, so each rule gets its own test
name. Every date-sensitive call is given an explicit ``today``: none of this
depends on when the suite runs.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from conftest import ME, commit

from bigfoot import stats

TODAY = date(2026, 8, 5)  # a Wednesday


def days_before(*offsets: int, anchor: date = TODAY) -> list[str]:
    """Day strings, given as "this many days before ``anchor``"."""
    return [(anchor - timedelta(days=n)).isoformat() for n in offsets]


# -- streaks -------------------------------------------------------------


def test_no_activity_at_all_is_no_streak():
    result = stats.streak([], TODAY)

    assert (result.current, result.longest, result.last_active) == (0, 0, None)
    assert result.alive is False


def test_committing_today_alone_is_a_streak_of_one():
    result = stats.streak(days_before(0), TODAY)

    assert (result.current, result.longest) == (1, 1)
    assert result.alive is True


def test_a_day_you_have_not_committed_on_yet_does_not_break_the_streak():
    """At 9am today, a run that reached yesterday is still alive."""
    result = stats.streak(days_before(3, 2, 1), TODAY)

    assert result.current == 3
    assert result.alive is True
    assert result.last_active == (TODAY - timedelta(days=1)).isoformat()


def test_a_fully_missed_day_breaks_the_streak():
    result = stats.streak(days_before(4, 3, 2), TODAY)

    assert result.current == 0
    assert result.longest == 3
    assert result.alive is False


def test_a_gap_of_exactly_one_day_keeps_the_run_going():
    """Consecutive calendar days extend a run; that is the whole rule."""
    result = stats.streak(days_before(2, 1, 0), TODAY)

    assert result.current == 3


def test_a_gap_of_two_days_starts_a_new_run():
    result = stats.streak(days_before(5, 3, 2, 1, 0), TODAY)

    assert result.current == 4
    assert result.longest == 4


def test_current_and_longest_differ_when_an_older_run_was_longer():
    older = days_before(20, 19, 18, 17, 16, 15)  # six days
    recent = days_before(1, 0)  # two days

    result = stats.streak(older + recent, TODAY)

    assert result.current == 2
    assert result.longest == 6


def test_the_longest_run_survives_a_broken_current_streak():
    result = stats.streak(days_before(10, 9, 8, 7), TODAY)

    assert result.current == 0
    assert result.longest == 4
    assert result.last_active == (TODAY - timedelta(days=7)).isoformat()


def test_unsorted_input_is_normalised_before_counting():
    scrambled = days_before(0, 3, 1, 2)

    assert stats.streak(scrambled, TODAY).current == 4


def test_duplicate_days_count_once():
    duplicated = days_before(2, 2, 1, 1, 1, 0)

    result = stats.streak(duplicated, TODAY)

    assert (result.current, result.longest) == (3, 3)


def test_a_single_day_long_ago_is_a_longest_of_one_and_no_current():
    result = stats.streak(days_before(100), TODAY)

    assert (result.current, result.longest) == (0, 1)


def test_last_active_is_always_the_most_recent_day():
    result = stats.streak(days_before(30, 2, 9), TODAY)

    assert result.last_active == (TODAY - timedelta(days=2)).isoformat()


def test_a_streak_spanning_a_month_boundary_is_unbroken():
    anchor = date(2026, 3, 2)
    across = [(anchor - timedelta(days=n)).isoformat() for n in range(4)]

    result = stats.streak(across, anchor)

    assert result.current == 4  # Feb 27, 28, Mar 1, Mar 2


# -- grid ----------------------------------------------------------------


@pytest.mark.parametrize("weeks", [1, 4, 26, 53])
def test_the_grid_is_always_weeks_columns_of_exactly_seven_days(weeks):
    result = stats.grid({}, weeks, TODAY)

    assert len(result.weeks) == weeks
    assert {len(column) for column in result.weeks} == {7}


@pytest.mark.parametrize("today", [date(2026, 8, 3), date(2026, 8, 5), date(2026, 8, 9)])
def test_every_row_holds_one_weekday_monday_first(today):
    result = stats.grid({}, 6, today)

    for column in result.weeks:
        assert [cell.day.weekday() for cell in column] == list(range(7))


@pytest.mark.parametrize(
    ("today", "row"),
    [
        (date(2026, 8, 3), 0),  # Monday
        (date(2026, 8, 5), 2),  # Wednesday
        (date(2026, 8, 9), 6),  # Sunday
    ],
)
def test_today_sits_in_its_own_weekday_row_of_the_last_column(today, row):
    result = stats.grid({}, 8, today)

    assert result.weeks[-1][row].day == today


def test_the_grid_ends_on_the_current_week_and_covers_exactly_the_window():
    result = stats.grid({}, 4, TODAY)

    first_day = result.weeks[0][0].day
    last_day = result.weeks[-1][-1].day

    assert (last_day - first_day).days == 4 * 7 - 1
    assert first_day <= TODAY <= last_day


def test_days_after_today_are_out_of_range():
    result = stats.grid({}, 3, TODAY)

    future = [cell for column in result.weeks for cell in column if cell.day > TODAY]

    assert future  # the current week has days left in it
    assert all(cell.in_range is False for cell in future)


def test_days_before_the_first_tracked_day_are_out_of_range():
    first_tracked = TODAY - timedelta(days=10)

    result = stats.grid({}, 6, TODAY, first_tracked)

    untracked = [
        cell for column in result.weeks for cell in column if cell.day < first_tracked
    ]
    assert untracked
    assert all(cell.in_range is False for cell in untracked)


def test_a_tracked_day_with_no_commits_is_still_in_range():
    """"I did not code that day" and "I was not tracking yet" must stay distinct."""
    first_tracked = TODAY - timedelta(days=10)
    quiet_day = TODAY - timedelta(days=3)

    result = stats.grid({}, 6, TODAY, first_tracked)

    cell = next(
        cell for column in result.weeks for cell in column if cell.day == quiet_day
    )
    assert cell.commits == 0
    assert cell.in_range is True


def test_the_first_tracked_day_itself_is_in_range():
    first_tracked = TODAY - timedelta(days=10)

    result = stats.grid({}, 6, TODAY, first_tracked)

    cell = next(
        cell for column in result.weeks for cell in column if cell.day == first_tracked
    )
    assert cell.in_range is True


def test_without_a_first_tracked_day_every_past_day_is_in_range():
    result = stats.grid({}, 3, TODAY)

    past = [cell for column in result.weeks for cell in column if cell.day <= TODAY]

    assert all(cell.in_range is True for cell in past)


def test_commit_counts_land_on_their_own_day():
    counts = {
        TODAY.isoformat(): 4,
        (TODAY - timedelta(days=8)).isoformat(): 2,
    }

    result = stats.grid(counts, 4, TODAY)

    placed = {
        cell.day.isoformat(): cell.commits
        for column in result.weeks
        for cell in column
        if cell.commits
    }
    assert placed == counts


def test_the_peak_is_the_busiest_day_inside_the_window():
    counts = {
        TODAY.isoformat(): 3,
        (TODAY - timedelta(days=5)).isoformat(): 9,
        (TODAY - timedelta(days=400)).isoformat(): 99,  # outside a 4 week grid
    }

    assert stats.grid(counts, 4, TODAY).peak == 9


def test_the_peak_of_an_empty_grid_is_zero():
    assert stats.grid({}, 4, TODAY).peak == 0


@pytest.mark.parametrize("weeks", [4, 9, 26, 53])
@pytest.mark.parametrize("today", [date(2026, 1, 1), date(2026, 8, 5), date(2026, 12, 31)])
def test_month_labels_ascend_and_point_at_real_columns(weeks, today):
    result = stats.grid({}, weeks, today)

    columns = [index for index, _ in result.month_labels]

    assert columns == sorted(columns)
    assert len(columns) == len(set(columns))
    assert all(0 <= index < weeks for index in columns)


def test_a_month_label_names_the_month_its_column_belongs_to():
    result = stats.grid({}, 26, TODAY)

    for index, name in result.month_labels:
        week_start = result.weeks[index][0].day
        assert week_start.strftime("%b") == name
        assert week_start.day <= 7  # the week that introduces the month


def test_a_year_wide_grid_labels_every_month_it_covers():
    """Exactly the columns whose week opens a month carry that month's label."""
    result = stats.grid({}, 53, TODAY)

    expected = {
        index: column[0].day.strftime("%b")
        for index, column in enumerate(result.weeks)
        if column[0].day.day <= 7
    }

    assert dict(result.month_labels) == expected
    assert len(expected) >= 12


# -- levels --------------------------------------------------------------


def test_level_zero_means_no_commits_at_all():
    assert stats.level(0, 10) == 0
    assert stats.level(-1, 10) == 0
    assert stats.level(1, 10) != 0


def test_the_busiest_day_reaches_the_top_level():
    assert stats.level(10, 10) == 4
    assert stats.level(1, 1) == 4


def test_a_peak_of_zero_or_one_does_not_divide_by_zero():
    assert stats.level(1, 0) == 4
    assert stats.level(3, 1) == 4


@pytest.mark.parametrize(
    ("commits", "expected"),
    [(1, 1), (5, 1), (6, 2), (10, 2), (11, 3), (15, 3), (16, 4), (20, 4)],
)
def test_levels_scale_with_the_users_own_peak(commits, expected):
    assert stats.level(commits, 20) == expected


def test_levels_never_decrease_as_commits_rise():
    levels = [stats.level(n, 12) for n in range(0, 13)]

    assert levels == sorted(levels)
    assert levels[0] == 0
    assert levels[-1] == 4


# -- snapshot ------------------------------------------------------------


def test_a_snapshot_of_an_empty_store_is_all_zeros(store):
    result = stats.snapshot(store, weeks=4, today=TODAY)

    assert result.today.commits == 0
    assert result.streak.current == 0
    assert result.first_day is None
    assert result.tracked_repos == 0
    assert result.grid.peak == 0
    assert len(result.grid.weeks) == 4


def test_a_snapshot_reports_today_this_week_and_the_streak(store):
    repo_id = store.upsert_repo("github.com/acme/api", "api", "/w/api")
    store.add_commits(
        repo_id,
        [
            commit("mon", "2026-08-03", email=ME, insertions=5, deletions=0),
            commit("tue", "2026-08-04", email=ME, insertions=3, deletions=1),
            commit("wed-1", "2026-08-05", email=ME, insertions=2, deletions=0),
            commit("wed-2", "2026-08-05", email=ME, insertions=1, deletions=0),
            commit("old", "2026-05-01", email=ME, insertions=7, deletions=7),
        ],
    )

    result = stats.snapshot(store, weeks=8, today=TODAY)

    assert result.today.commits == 2
    assert result.week.commits == 4  # Monday through today
    assert result.month.commits == 4  # August so far
    assert result.year.commits == 5
    assert result.active_this_week == 3
    assert result.streak.current == 3
    assert result.first_day == "2026-05-01"
    assert result.tracked_repos == 1
    assert [r.name for r in result.top_repos] == ["api"]


def test_a_snapshot_marks_days_before_the_first_commit_as_untracked(store):
    repo_id = store.upsert_repo("k", "api", "/w/api")
    store.add_commits(repo_id, [commit("aaa", "2026-08-03")])

    result = stats.snapshot(store, weeks=6, today=TODAY)

    cells = [cell for column in result.grid.weeks for cell in column]
    assert all(cell.in_range is False for cell in cells if cell.day < date(2026, 8, 3))
    assert any(cell.in_range and cell.commits == 0 for cell in cells)
