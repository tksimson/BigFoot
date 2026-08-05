"""Storage, and the idempotency the old daily-aggregate schema could not give.

The recurring bug in the previous version was double counting: totals were kept
as per-repo-per-day aggregates, so a second sync of the same work added it
again. One row per commit sha makes that impossible, and these tests are what
keep it impossible.
"""

from __future__ import annotations

import pytest
from conftest import COLLEAGUE, ME, commit

from bigfoot.store import Commit, Store

# -- idempotency ---------------------------------------------------------


def test_syncing_the_same_commits_repeatedly_inserts_them_once(store):
    repo_id = store.upsert_repo("github.com/acme/api", "api", "/w/api")
    batch = [commit("aaa", "2026-08-03"), commit("bbb", "2026-08-04")]

    first = store.add_commits(repo_id, batch)
    again = [store.add_commits(repo_id, batch) for _ in range(5)]

    assert first == 2
    assert again == [0, 0, 0, 0, 0]
    assert store.total_commits() == 2


def test_repeated_syncs_do_not_move_any_total(store):
    repo_id = store.upsert_repo("github.com/acme/api", "api", "/w/api")
    batch = [
        commit("aaa", "2026-08-03", insertions=10, deletions=1),
        commit("bbb", "2026-08-03", insertions=5, deletions=2),
        commit("ccc", "2026-08-04", insertions=7, deletions=0),
    ]

    store.add_commits(repo_id, batch)
    baseline = store.day_stats("2026-08-01", "2026-08-31")
    totals = store.range_total("2026-08-01", "2026-08-31")

    for _ in range(3):
        store.add_commits(repo_id, batch)

    assert store.day_stats("2026-08-01", "2026-08-31") == baseline
    assert store.range_total("2026-08-01", "2026-08-31") == totals
    assert baseline["2026-08-03"].commits == 2
    assert baseline["2026-08-03"].insertions == 15


def test_add_commits_reports_the_number_of_rows_actually_inserted(store):
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(repo_id, [commit("aaa"), commit("bbb")])

    mixed = store.add_commits(repo_id, [commit("bbb"), commit("ccc"), commit("ddd")])

    assert mixed == 2
    assert store.total_commits() == 4


def test_add_commits_of_nothing_inserts_nothing(store):
    repo_id = store.upsert_repo("k", "n", "/p")

    assert store.add_commits(repo_id, []) == 0
    assert store.total_commits() == 0


def test_a_resynced_commit_keeps_its_original_numbers(store):
    """Re-inserting an existing sha is ignored, not applied as an update."""
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(repo_id, [commit("aaa", insertions=10, deletions=1, files=2)])

    store.add_commits(repo_id, [commit("aaa", insertions=999, deletions=999, files=9)])

    total = store.range_total("2000-01-01", "2100-01-01")
    assert (total.commits, total.insertions, total.deletions) == (1, 10, 1)


# -- one commit seen through two repositories ----------------------------


@pytest.fixture
def shared_sha(store):
    """The same commit recorded under two repository rows."""
    left = store.upsert_repo("github.com/acme/api", "api", "/w/api")
    right = store.upsert_repo("path:/w/api-fork", "api-fork", "/w/api-fork")
    same = commit("shared", "2026-08-03", insertions=10, deletions=2, files=1)
    assert store.add_commits(left, [same]) == 1
    assert store.add_commits(right, [same]) == 1
    return store


def test_one_sha_in_two_repositories_counts_once_in_the_total(shared_sha):
    assert shared_sha.total_commits() == 1


def test_one_sha_in_two_repositories_counts_once_in_the_days(shared_sha):
    day = shared_sha.day_stats("2026-08-03", "2026-08-03")["2026-08-03"]

    assert day.commits == 1
    # One project seen through two clones is one project, not two. Commits are
    # collapsed on SHA before anything is counted, so every column agrees.
    assert day.repos == 1


def test_one_sha_in_two_repositories_counts_once_in_a_range(shared_sha):
    assert shared_sha.range_total("2026-08-01", "2026-08-31").commits == 1


def test_one_sha_in_two_repositories_counts_its_lines_once(shared_sha):
    day = shared_sha.day_stats("2026-08-03", "2026-08-03")["2026-08-03"]

    assert (day.insertions, day.deletions) == (10, 2)


# -- repository rows -----------------------------------------------------


def test_upserting_a_repository_twice_returns_the_same_id(store):
    first = store.upsert_repo("github.com/acme/api", "api", "/w/api")

    second = store.upsert_repo("github.com/acme/api", "api", "/w/api")

    assert first == second
    assert len(store.repos()) == 1


def test_upserting_refreshes_the_name_and_path_but_keeps_the_identity(store):
    repo_id = store.upsert_repo("github.com/acme/api", "api", "/old/api")

    again = store.upsert_repo("github.com/acme/api", "payments", "/new/payments")

    (row,) = store.repos()
    assert again == repo_id
    assert (row.name, row.path) == ("payments", "/new/payments")


def test_repositories_with_different_keys_are_different_rows(store):
    first = store.upsert_repo("path:/work/api", "api", "/work/api")
    second = store.upsert_repo("path:/personal/api", "api", "/personal/api")

    assert first != second
    assert len(store.repos()) == 2


def test_forgetting_a_repository_removes_its_commits(store):
    keep = store.upsert_repo("keep", "keep", "/keep")
    drop = store.upsert_repo("drop", "drop", "/drop")
    store.add_commits(keep, [commit("aaa")])
    store.add_commits(drop, [commit("bbb")])

    removed = store.forget_repo("drop")

    assert removed is True
    assert store.total_commits() == 1
    assert [r.name for r in store.repos()] == ["keep"]


def test_forgetting_an_unknown_repository_reports_nothing_removed(store):
    assert store.forget_repo("never-seen") is False


def test_marking_a_repository_synced_records_the_timestamp(store):
    repo_id = store.upsert_repo("k", "n", "/p")

    store.mark_synced(repo_id, "2026-08-05T09:00:00")

    assert store.repos()[0].last_synced == "2026-08-05T09:00:00"


# -- incremental sync ----------------------------------------------------


def test_latest_day_is_per_repository(store):
    left = store.upsert_repo("left", "left", "/l")
    right = store.upsert_repo("right", "right", "/r")
    store.add_commits(left, [commit("aaa", "2026-08-01"), commit("bbb", "2026-08-04")])
    store.add_commits(right, [commit("ccc", "2026-07-20")])

    assert store.latest_day(left) == "2026-08-04"
    assert store.latest_day(right) == "2026-07-20"


def test_latest_day_of_an_unsynced_repository_is_unknown(store):
    repo_id = store.upsert_repo("k", "n", "/p")

    assert store.latest_day(repo_id) is None


# -- queries -------------------------------------------------------------


def test_day_stats_is_inclusive_of_both_ends_and_skips_silent_days(store):
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(
        repo_id,
        [
            commit("before", "2026-07-31"),
            commit("start", "2026-08-01"),
            commit("end", "2026-08-03"),
            commit("after", "2026-08-04"),
        ],
    )

    days = store.day_stats("2026-08-01", "2026-08-03")

    assert sorted(days) == ["2026-08-01", "2026-08-03"]  # 08-02 is absent, not zero


def test_a_day_with_no_commits_is_absent_rather_than_zero(store):
    """Callers fill gaps, so a silent day must not be confused with a tracked zero."""
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(repo_id, [commit("aaa", "2026-08-01")])

    assert store.day_stats("2026-08-02", "2026-08-02") == {}
    assert store.range_total("2026-08-02", "2026-08-02").commits == 0


def test_range_total_collapses_the_window(store):
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(
        repo_id,
        [
            commit("aaa", "2026-08-01", insertions=3, deletions=1),
            commit("bbb", "2026-08-02", insertions=4, deletions=0),
            commit("ccc", "2026-09-01", insertions=99, deletions=99),
        ],
    )

    total = store.range_total("2026-08-01", "2026-08-31")

    assert (total.commits, total.insertions, total.deletions, total.repos) == (2, 7, 1, 1)


def test_totals_of_an_empty_range_are_zero_not_none(store):
    store.upsert_repo("k", "n", "/p")

    total = store.range_total("2026-01-01", "2026-01-31")

    assert (total.commits, total.insertions, total.deletions, total.repos) == (0, 0, 0, 0)


def test_active_days_are_distinct_and_oldest_first(store):
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(
        repo_id,
        [
            commit("aaa", "2026-08-04"),
            commit("bbb", "2026-08-01"),
            commit("ccc", "2026-08-04"),
        ],
    )

    assert store.active_days() == ["2026-08-01", "2026-08-04"]


def test_repo_stats_are_busiest_first_and_windowed(store):
    quiet = store.upsert_repo("quiet", "quiet", "/q")
    busy = store.upsert_repo("busy", "busy", "/b")
    store.add_commits(quiet, [commit("q1", "2026-08-01")])
    store.add_commits(busy, [commit("b1", "2026-08-01"), commit("b2", "2026-08-02")])
    store.add_commits(quiet, [commit("q-old", "2025-01-01")])

    windowed = store.repo_stats("2026-08-01", "2026-08-31")
    everything = store.repo_stats()

    assert [(r.name, r.commits) for r in windowed] == [("busy", 2), ("quiet", 1)]
    assert {r.name: r.commits for r in everything} == {"busy": 2, "quiet": 2}
    assert windowed[0].last_commit == "2026-08-02"


def test_repo_stats_omits_repositories_with_no_commits(store):
    store.upsert_repo("empty", "empty", "/e")
    active = store.upsert_repo("active", "active", "/a")
    store.add_commits(active, [commit("aaa")])

    assert [r.name for r in store.repo_stats()] == ["active"]


def test_first_day_and_emptiness_track_the_commits_table(store):
    repo_id = store.upsert_repo("k", "n", "/p")

    assert store.is_empty() is True
    assert store.first_day() is None

    store.add_commits(repo_id, [commit("aaa", "2026-08-04"), commit("bbb", "2026-03-09")])

    assert store.is_empty() is False
    assert store.first_day() == "2026-03-09"


def test_commits_from_several_of_your_addresses_all_count(store):
    repo_id = store.upsert_repo("k", "n", "/p")
    store.add_commits(
        repo_id,
        [
            commit("aaa", "2026-08-03", email=ME),
            commit("bbb", "2026-08-03", email=COLLEAGUE),
        ],
    )

    assert store.range_total("2026-08-03", "2026-08-03").commits == 2


# -- the file itself -----------------------------------------------------


def test_opening_a_store_creates_its_directory(tmp_path):
    target = tmp_path / "nested" / "deeper" / "bigfoot.db"

    with Store(target) as opened:
        assert opened.meta_get("schema_version") == "1"

    assert target.exists()


def test_data_survives_reopening_the_same_file(tmp_path):
    target = tmp_path / "bigfoot.db"
    with Store(target) as first:
        repo_id = first.upsert_repo("k", "n", "/p")
        first.add_commits(repo_id, [commit("aaa", "2026-08-04")])

    with Store(target) as second:
        assert second.total_commits() == 1
        assert second.first_day() == "2026-08-04"


def test_reopening_does_not_reset_the_schema_version(tmp_path):
    target = tmp_path / "bigfoot.db"
    with Store(target) as first:
        first.meta_set("schema_version", "1")

    with Store(target) as second:
        assert second.meta_get("schema_version") == "1"


def test_meta_values_are_overwritten_not_duplicated(store):
    store.meta_set("last_sync", "2026-08-04")
    store.meta_set("last_sync", "2026-08-05")

    assert store.meta_get("last_sync") == "2026-08-05"
    assert store.meta_get("never-set") is None


def test_a_commit_cannot_be_attached_to_an_unknown_repository(store):
    """Foreign keys are enforced, so orphaned commits cannot accumulate."""
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        store.add_commits(999, [Commit(sha="aaa", day="2026-08-04", email=ME)])
