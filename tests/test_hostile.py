"""Regression tests for what a repository you did not write can do to you.

Users point this tool at directories full of clones from strangers. Author
email and author date are chosen by whoever made a commit and survive a clone,
so both are attacker-controlled input on an ordinary machine. Each test here
pins a failure that was reachable that way.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from gitfoot import config, gitscan, stats
from gitfoot.gitscan import FIELD_SEP, RECORD_SEP
from gitfoot.store import Commit, Store
from gitfoot.term import sanitize

MINE = {"victim@example.com"}


def log(*records: tuple[str, str, str]) -> str:
    """Build `git log --numstat` output: (sha, day, email) per commit."""
    return "".join(
        f"{RECORD_SEP}{sha}{FIELD_SEP}{day}{FIELD_SEP}{email}\n1\t0\tf.txt\n"
        for sha, day, email in records
    )


# -- dates ---------------------------------------------------------------


@pytest.mark.parametrize(
    "day",
    [
        "10000-01-01",  # git prints five-digit years verbatim for huge timestamps
        "0001-01-01",
        "not-a-date",
        "",
        "2026-13-01",
        "2026-02-30",
    ],
)
def test_a_commit_with_an_impossible_date_is_refused(day):
    assert list(gitscan.parse_log(log(("a" * 40, day, "victim@example.com")), MINE)) == []


def test_a_far_future_commit_is_refused():
    far = (date.today() + timedelta(days=400)).isoformat()

    assert list(gitscan.parse_log(log(("a" * 40, far, "victim@example.com")), MINE)) == []


def test_a_commit_dated_tomorrow_is_kept():
    """Timezones legitimately put a commit a day ahead of the local clock."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    kept = list(gitscan.parse_log(log(("a" * 40, tomorrow, "victim@example.com")), MINE))

    assert [c.day for c in kept] == [tomorrow]


def test_an_unparseable_date_cannot_reach_the_dashboard(tmp_path):
    """stats.snapshot parses every stored day; one bad row took every command down."""
    store = Store(tmp_path / "b.db")
    repo = store.upsert_repo("k", "n", "/p")
    store.add_commits(repo, list(gitscan.parse_log(log(
        ("a" * 40, "10000-01-01", "victim@example.com"),
        ("b" * 40, date.today().isoformat(), "victim@example.com"),
    ), MINE)))

    snap = stats.snapshot(store, weeks=4)

    assert snap.today.commits == 1


# -- incremental sync ----------------------------------------------------


def test_a_future_dated_commit_does_not_freeze_incremental_sync(tmp_path):
    """`day` is TEXT, so MAX() is lexicographic.

    One commit dated 2099 became the resume point, every later sync asked git
    for commits since 2098, found none, and reported success forever.
    """
    store = Store(tmp_path / "b.db")
    repo = store.upsert_repo("k", "n", "/p")
    today = date.today().isoformat()
    store.add_commits(
        repo,
        [
            Commit("a" * 40, today, "victim@example.com"),
            Commit("b" * 40, "2099-01-01", "victim@example.com"),
        ],
    )

    assert store.latest_day(repo) == today


def test_a_future_dated_commit_cannot_prop_up_a_broken_streak():
    """`streak` counted back from the newest date in the database.

    A commit dated ahead of today (a colleague thirteen timezones east, or a
    fast clock) became the anchor, so a streak that actually died last week
    still read as alive.
    """
    today = date(2026, 8, 5)
    stale = [(today - timedelta(days=n)).isoformat() for n in (5, 6, 7)]
    ahead = (today + timedelta(days=3)).isoformat()

    assert stats.streak(stale + [ahead], today).current == 0


def test_a_future_dated_commit_does_not_lengthen_a_live_streak():
    today = date(2026, 8, 5)
    live = [(today - timedelta(days=n)).isoformat() for n in (0, 1, 2)]
    ahead = (today + timedelta(days=3)).isoformat()

    assert stats.streak(live + [ahead], today).current == 3


def test_a_database_of_only_future_days_has_no_streak():
    today = date(2026, 8, 5)
    ahead = [(today + timedelta(days=n)).isoformat() for n in (1, 2, 3)]

    assert stats.streak(ahead, today) == stats.Streak(0, 0, None)


def test_latest_day_ignores_only_the_future(tmp_path):
    store = Store(tmp_path / "b.db")
    repo = store.upsert_repo("k", "n", "/p")
    store.add_commits(repo, [Commit("a" * 40, "2020-06-01", "victim@example.com")])

    assert store.latest_day(repo) == "2020-06-01"


# -- terminal escapes ----------------------------------------------------


@pytest.mark.parametrize(
    "hostile",
    [
        "a\x1b]0;OWNED\x07victim@example.com",  # OSC: rewrites the window title
        "a\rvictim@example.com",  # CR: repaints the line it is printed on
        "a\x1b[2Jvictim@example.com",  # clears the screen
        "a\x1b[31mvictim@example.com",  # leaves the terminal styled
        "a\nvictim@example.com",  # breaks the line the prompt numbers
        "a\x00victim@example.com",
    ],
)
def test_control_characters_are_stripped_from_displayed_text(hostile):
    clean = sanitize(hostile)

    assert "\x1b" not in clean
    assert "\r" not in clean
    assert "\n" not in clean
    assert "\x00" not in clean
    assert clean.isprintable()


def test_an_email_with_escapes_is_cleaned_before_it_is_stored():
    hostile = "a\x1b]0;OWNED\x07\rvictim@example.com"

    kept = list(gitscan.parse_log(log(("a" * 40, date.today().isoformat(), hostile)), {hostile}))

    assert len(kept) == 1
    assert "\x1b" not in kept[0].email and "\r" not in kept[0].email


def test_sanitize_keeps_ordinary_text_intact():
    assert sanitize("Zażółć gęślą jaźń <me@x.com>") == "Zażółć gęślą jaźń <me@x.com>"


# -- config integrity ----------------------------------------------------


def test_a_control_character_in_an_email_does_not_destroy_the_config(tmp_path):
    """An unescaped control character makes tomllib reject the file, load()
    falls back to defaults, and the next save overwrites the real settings."""
    target = tmp_path / "config.toml"
    cfg = config.Config(
        roots=["/w/dev"], emails=["ok@x.com", "evil\x1b[31m@x.com"], path=target
    )

    config.save(cfg)
    reloaded = config.load(target)

    assert reloaded.roots == ["/w/dev"]
    assert "ok@x.com" in reloaded.emails


def test_config_and_database_are_not_world_readable(tmp_path):
    cfg = config.Config(roots=["/w"], path=tmp_path / "config.toml")
    config.save(cfg)
    store = Store(tmp_path / "b.db")

    assert cfg.path.stat().st_mode & 0o077 == 0
    assert store.path.stat().st_mode & 0o077 == 0


# -- attribution ---------------------------------------------------------


def test_an_empty_identity_matches_nothing(tmp_path):
    """The bug this rewrite exists for: a no-op filter that counted everyone."""
    output = log(
        ("a" * 40, date.today().isoformat(), "victim@example.com"),
        ("b" * 40, date.today().isoformat(), "colleague@corp.com"),
    )

    assert list(gitscan.parse_log(output, set())) == []


def test_only_configured_authors_are_counted():
    output = log(
        ("a" * 40, date.today().isoformat(), "victim@example.com"),
        ("b" * 40, date.today().isoformat(), "colleague@corp.com"),
    )

    kept = list(gitscan.parse_log(output, MINE))

    assert [c.email for c in kept] == ["victim@example.com"]
