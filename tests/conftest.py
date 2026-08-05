"""Shared fixtures.

Two rules hold for the whole suite:

* Nothing reads or writes the developer's real environment. ``HOME``,
  ``XDG_*``, ``BIGFOOT_HOME`` and git's global/system config files are all
  redirected into ``tmp_path`` by an autouse fixture, so a test can never pick
  up the developer's git identity or clobber ``~/.config/bigfoot``.
* Nothing depends on the wall clock. Commits are made with explicit UTC
  timestamps and every date-sensitive function is called with an explicit
  ``today``.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from bigfoot import gitscan
from bigfoot.store import Commit, Store

# A fixed "today" for date-sensitive tests. A Wednesday, mid-week and mid-month,
# so weekday and month-boundary logic is exercised away from the edges.
TODAY = "2026-08-05"

ME = "me@example.com"
COLLEAGUE = "colleague@example.com"


@pytest.fixture(autouse=True)
def hermetic_env(tmp_path_factory, monkeypatch):
    """Cut every tie to the developer's real home and git configuration."""
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    # Point git at config files that do not exist: no user identity, no
    # aliases, no url.insteadOf rewriting leaking in from the developer's setup.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "absent-gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(home / "absent-gitsystem"))
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.setenv("GIT_ASKPASS", "true")
    monkeypatch.setenv("LC_ALL", "C")

    for var in ("BIGFOOT_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(var, raising=False)

    return home


# -- git repositories ----------------------------------------------------


class GitRepo:
    """A real git repository built for one test.

    Author and committer identity and dates are supplied per commit through the
    environment, so no ``user.email`` is ever configured and commits land on
    whatever day the test asks for.
    """

    def __init__(self, path: Path):
        self.path = path

    def git(self, *args: str, env: dict[str, str] | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(self.path),
            capture_output=True,
            text=True,
            env={**os.environ, **(env or {})},
            timeout=30,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} failed ({result.returncode}): {result.stderr}"
            )
        return result.stdout

    def commit(
        self,
        day: str,
        email: str = ME,
        *,
        files: dict[str, str] | None = None,
        binary: dict[str, bytes] | None = None,
        message: str = "change",
        allow_empty: bool = False,
        name: str = "Test Author",
    ) -> str:
        """Add one commit dated ``day`` (UTC noon) and return its sha."""
        for rel, content in (files or {}).items():
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        for rel, blob in (binary or {}).items():
            target = self.path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)

        self.git("add", "-A")
        args = ["commit", "-q", "-m", message]
        if allow_empty:
            args.append("--allow-empty")
        self.git(*args, env=_ident_env(day, email, name))
        return self.git("rev-parse", "HEAD").strip()

    def branch(self, name: str) -> None:
        self.git("checkout", "-q", "-b", name)

    def checkout(self, name: str) -> None:
        self.git("checkout", "-q", name)

    def merge(self, other: str, day: str, email: str = ME, message: str = "merge") -> str:
        self.git(
            "merge",
            "-q",
            "--no-ff",
            "-m",
            message,
            other,
            env=_ident_env(day, email, "Test Author"),
        )
        return self.git("rev-parse", "HEAD").strip()

    def set_remote(self, url: str, name: str = "origin") -> None:
        self.git("remote", "add", name, url)

    def found(self) -> gitscan.Found:
        identified = gitscan._identify(self.path)
        assert identified is not None, f"{self.path} is not a git repository"
        return identified


def _ident_env(day: str, email: str, name: str) -> dict[str, str]:
    stamp = f"{day}T12:00:00+00:00"
    return {
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": stamp,
        "GIT_COMMITTER_NAME": name,
        "GIT_COMMITTER_EMAIL": email,
        "GIT_COMMITTER_DATE": stamp,
    }


@pytest.fixture
def make_repo(tmp_path):
    """Factory building initialised git repositories under ``tmp_path``."""

    def build(name: str = "project", *, parent: Path | None = None, remote: str | None = None) -> GitRepo:
        path = (parent or tmp_path) / name
        path.mkdir(parents=True, exist_ok=True)
        repo = GitRepo(path)
        repo.git("init", "-q", "-b", "main")
        if remote:
            repo.set_remote(remote)
        return repo

    return build


@pytest.fixture
def repo(make_repo):
    """A repository with no commits yet."""
    return make_repo()


def plain_dir(path: Path) -> gitscan.Found:
    """A ``Found`` pointing at something that is not a repository."""
    path.mkdir(parents=True, exist_ok=True)
    return gitscan.Found(path=path, key=f"path:{path}", name=path.name)


# -- store ---------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    """An empty store in its own directory, closed on teardown."""
    with Store(tmp_path / "data" / "bigfoot.db") as opened:
        yield opened


def commit(
    sha: str,
    day: str = TODAY,
    email: str = ME,
    insertions: int = 10,
    deletions: int = 2,
    files: int = 1,
) -> Commit:
    """A commit record, for tests that do not need a real repository."""
    return Commit(
        sha=sha,
        day=day,
        email=email,
        insertions=insertions,
        deletions=deletions,
        files=files,
    )
