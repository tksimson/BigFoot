"""SQLite storage.

One row per commit, not per repo-day. Aggregates were the source of the
recurring "double counting" bug: re-running a sync re-added work that was
already recorded, and there was no key to notice it had been seen before. With
the commit SHA as the key, a sync is idempotent by construction -- run it a
hundred times and the numbers do not move.

Daily totals use ``COUNT(DISTINCT sha)`` so the same commit reachable from two
clones of one project is counted once.
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS repos (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    path        TEXT NOT NULL,
    last_synced TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    sha        TEXT NOT NULL,
    repo_id    INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    email      TEXT NOT NULL,
    insertions INTEGER NOT NULL DEFAULT 0,
    deletions  INTEGER NOT NULL DEFAULT 0,
    files      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sha, repo_id)
);

CREATE INDEX IF NOT EXISTS idx_commits_day ON commits(day);
CREATE INDEX IF NOT EXISTS idx_commits_repo ON commits(repo_id);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# One row per commit SHA within a date range, collapsing the same commit seen
# through two repositories.
#
# Counting distinct SHAs while summing line counts over every row was subtly
# wrong: a project cloned twice, or a fork whose remote differs, produced the
# right commit total next to doubled insertions. Deduplicating first means one
# rule applies to every column.
_DISTINCT_COMMITS = """
    SELECT sha,
           MIN(day)        AS day,
           MIN(repo_id)    AS repo_id,
           MAX(insertions) AS insertions,
           MAX(deletions)  AS deletions
    FROM commits
    WHERE day BETWEEN ? AND ?
    GROUP BY sha
"""


@dataclass(frozen=True)
class Commit:
    """A single commit attributed to you."""

    sha: str
    day: str  # YYYY-MM-DD, author date in the author's local timezone
    email: str
    insertions: int = 0
    deletions: int = 0
    files: int = 0


@dataclass(frozen=True)
class Repo:
    id: int
    key: str
    name: str
    path: str
    last_synced: str | None = None


@dataclass(frozen=True)
class DayStat:
    day: str
    commits: int
    insertions: int
    deletions: int
    repos: int


@dataclass(frozen=True)
class RepoStat:
    name: str
    path: str
    commits: int
    last_commit: str | None


class Store:
    """Thin, explicit wrapper over the SQLite file. Not thread-safe."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not self.path.exists()
        self._conn = sqlite3.connect(str(self.path))
        if fresh:
            # A record of when you work, and of every repository path on the
            # machine. Owner-only by default rather than whatever umask says.
            with contextlib.suppress(OSError):
                self.path.chmod(0o600)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- schema ----------------------------------------------------------

    def _migrate(self) -> None:
        self._conn.executescript(_SCHEMA)
        current = self.meta_get("schema_version")
        if current is None:
            self.meta_set("schema_version", str(SCHEMA_VERSION))
        self._conn.commit()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- meta ------------------------------------------------------------

    def meta_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def meta_set(self, key: str, value: str) -> None:
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # -- repos -----------------------------------------------------------

    def upsert_repo(self, key: str, name: str, path: str) -> int:
        """Insert or refresh a repo, returning its id."""
        with self._tx() as conn:
            conn.execute(
                "INSERT INTO repos (key, name, path) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET name = excluded.name, path = excluded.path",
                (key, name, path),
            )
            row = conn.execute("SELECT id FROM repos WHERE key = ?", (key,)).fetchone()
        return int(row["id"])

    def mark_synced(self, repo_id: int, when: str) -> None:
        with self._tx() as conn:
            conn.execute("UPDATE repos SET last_synced = ? WHERE id = ?", (when, repo_id))

    def repos(self) -> list[Repo]:
        rows = self._conn.execute(
            "SELECT id, key, name, path, last_synced FROM repos ORDER BY name"
        ).fetchall()
        return [Repo(**dict(r)) for r in rows]

    def forget_repo(self, key: str) -> bool:
        """Drop a repo and its commits. Returns whether anything was removed."""
        with self._tx() as conn:
            cur = conn.execute("DELETE FROM repos WHERE key = ?", (key,))
        return cur.rowcount > 0

    # -- commits ---------------------------------------------------------

    def add_commits(self, repo_id: int, commits: Iterable[Commit]) -> int:
        """Record commits. Already-known SHAs are ignored, not duplicated.

        Returns the number of rows actually inserted.
        """
        rows = [
            (c.sha, repo_id, c.day, c.email, c.insertions, c.deletions, c.files)
            for c in commits
        ]
        if not rows:
            return 0
        before = self._conn.total_changes
        with self._tx() as conn:
            conn.executemany(
                "INSERT OR IGNORE INTO commits "
                "(sha, repo_id, day, email, insertions, deletions, files) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return self._conn.total_changes - before

    def latest_day(self, repo_id: int, today: str | None = None) -> str | None:
        """Most recent authored day recorded for a repo, for incremental sync.

        Future dates are excluded. ``day`` is TEXT, so ``MAX`` is lexicographic:
        a single commit authored ``2099-01-01`` (author dates are chosen freely
        by whoever made the commit, and survive a clone) would otherwise become
        the resume point and every later sync would ask git for commits since
        2098, find none, and report success. The repository would silently
        stop updating forever.
        """
        row = self._conn.execute(
            "SELECT MAX(day) AS d FROM commits WHERE repo_id = ? AND day <= ?",
            (repo_id, today or date.today().isoformat()),
        ).fetchone()
        return row["d"] if row and row["d"] else None

    # -- queries ---------------------------------------------------------

    def day_stats(self, start: str, end: str) -> dict[str, DayStat]:
        """Per-day totals between ``start`` and ``end`` inclusive.

        Only days with activity appear. Callers fill the gaps.
        """
        rows = self._conn.execute(
            f"""
            SELECT day,
                   COUNT(*)                AS commits,
                   SUM(insertions)         AS insertions,
                   SUM(deletions)          AS deletions,
                   COUNT(DISTINCT repo_id) AS repos
            FROM ({_DISTINCT_COMMITS})
            GROUP BY day
            """,
            (start, end),
        ).fetchall()
        return {
            r["day"]: DayStat(
                day=r["day"],
                commits=r["commits"],
                insertions=r["insertions"] or 0,
                deletions=r["deletions"] or 0,
                repos=r["repos"],
            )
            for r in rows
        }

    def active_days(self) -> list[str]:
        """Every day with at least one commit, oldest first."""
        rows = self._conn.execute(
            "SELECT DISTINCT day FROM commits ORDER BY day"
        ).fetchall()
        return [r["day"] for r in rows]

    def range_total(self, start: str, end: str) -> DayStat:
        """Collapsed totals for a date range."""
        row = self._conn.execute(
            f"""
            SELECT COUNT(*)                AS commits,
                   SUM(insertions)         AS insertions,
                   SUM(deletions)          AS deletions,
                   COUNT(DISTINCT repo_id) AS repos
            FROM ({_DISTINCT_COMMITS})
            """,
            (start, end),
        ).fetchone()
        return DayStat(
            day=start,
            commits=row["commits"] or 0,
            insertions=row["insertions"] or 0,
            deletions=row["deletions"] or 0,
            repos=row["repos"] or 0,
        )

    def repo_stats(self, start: str | None = None, end: str | None = None) -> list[RepoStat]:
        """Per-repo commit counts, busiest first."""
        where, params = "", []
        if start and end:
            where = "WHERE c.day BETWEEN ? AND ?"
            params = [start, end]
        rows = self._conn.execute(
            f"""
            SELECT r.name AS name,
                   r.path AS path,
                   COUNT(DISTINCT c.sha) AS commits,
                   MAX(c.day) AS last_commit
            FROM repos r
            JOIN commits c ON c.repo_id = r.id
            {where}
            GROUP BY r.id
            ORDER BY commits DESC, r.name
            """,
            params,
        ).fetchall()
        return [RepoStat(**dict(r)) for r in rows]

    def first_day(self) -> str | None:
        row = self._conn.execute("SELECT MIN(day) AS d FROM commits").fetchone()
        return row["d"] if row and row["d"] else None

    def total_commits(self) -> int:
        row = self._conn.execute("SELECT COUNT(DISTINCT sha) AS n FROM commits").fetchone()
        return int(row["n"] or 0)

    def is_empty(self) -> bool:
        return self.total_commits() == 0


def today() -> str:
    return date.today().isoformat()
