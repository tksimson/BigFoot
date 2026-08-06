"""Finding git repositories and reading commits out of them.

Two design choices carry most of the weight here.

**Discovery is a single pruned walk.** The old version shelled out to ``find``
once per configured root, and the default roots overlapped (``~/dev`` and ``~``),
so every repository was discovered two or three times. Here each root is walked
once, descent stops at the first ``.git`` found on a branch, and results are
keyed by resolved path.

**Reading is one ``git log`` per repository, not one per day.** The old backfill
ran ``git log`` for every (day, repo) pair and then ``git show`` for every
commit -- 90 days across 40 repos was over 3,600 subprocess calls before
counting a single line. One ``--numstat`` call per repo returns the same
information, and the work is bucketed by date in Python.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .store import Commit
from .term import sanitize

RECORD_SEP = "\x1e"
FIELD_SEP = "\x1f"

# Wide enough for a decade of history on a large repo, short enough that a
# hung filesystem does not hang the whole sync.
GIT_TIMEOUT = 120

# Ceiling on a single repository's log output. Comfortably above a decade of
# a large project (the Linux kernel's numstat log is a few hundred MB over its
# whole history), and low enough that eight concurrent reads cannot take the
# machine down.
MAX_LOG_BYTES = 512 * 2**20

# Only the last line of stderr is ever shown, so there is no reason to read more.
_STDERR_LIMIT = 64 * 2**10


@dataclass(frozen=True)
class Found:
    """A git repository on disk."""

    path: Path
    key: str
    name: str


@dataclass(frozen=True)
class SyncResult:
    repo: Found
    commits: list[Commit]
    error: str | None = None


def discover(
    roots: Iterable[Path],
    ignore_dirs: Sequence[str],
    max_depth: int,
) -> list[Found]:
    """Find git repositories under ``roots``.

    Descent stops at a repository boundary, so submodules and vendored
    checkouts inside a project are not reported separately -- their commits
    already belong to the parent's history from the author's point of view.
    """
    ignore = {d.lower() for d in ignore_dirs}
    candidates: list[Path] = []

    for base in _outermost(roots):
        base_depth = len(base.parts)
        for dirpath, dirnames, _ in os.walk(base, topdown=True, followlinks=False):
            current = Path(dirpath)

            # ``.git`` is a directory in a normal clone and a file in a
            # worktree or submodule; both mark a boundary worth stopping at.
            if (current / ".git").exists():
                dirnames[:] = []
                candidates.append(current)
                continue

            if len(current.parts) - base_depth >= max_depth:
                dirnames[:] = []
                continue

            dirnames[:] = [d for d in dirnames if d.lower() not in ignore]

    # Identifying a repo costs a `git config` call, so do them concurrently.
    # On a machine with a few hundred repos this is the difference between a
    # visible pause and none.
    seen: dict[str, Found] = {}
    if candidates:
        with ThreadPoolExecutor(max_workers=min(16, len(candidates))) as pool:
            for found in pool.map(_identify, candidates):
                if found:
                    seen.setdefault(found.key, found)

    return sorted(seen.values(), key=lambda f: f.name.lower())


def _outermost(roots: Iterable[Path]) -> list[Path]:
    """Resolve roots and drop any that sit inside another one.

    Configuring both ``~`` and ``~/dev`` used to mean walking ``~/dev`` twice.
    Deduplication downstream hid the cost but did not remove it.
    """
    resolved: list[Path] = []
    for root in roots:
        try:
            path = root.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if path.is_dir():
            resolved.append(path)

    resolved.sort(key=lambda p: len(p.parts))
    kept: list[Path] = []
    for path in resolved:
        if not any(path.is_relative_to(k) for k in kept):
            kept.append(path)
    return kept


def _identify(path: Path) -> Found | None:
    """Build a stable identity for a repository.

    Keyed by normalised remote URL when there is one, so two clones of the same
    project on one machine collapse into a single entry. Without a remote the
    resolved path is the key. Either way the key is unique -- the old code used
    ``basename``, so two projects both called ``api`` silently overwrote each
    other's history.
    """
    if not (path / ".git").exists():
        return None
    remote = _remote_url(path)
    key = normalize_remote(remote) if remote else f"path:{path}"
    name = sanitize(_name_from(remote, path)) or path.name
    return Found(path=path, key=key, name=name)


def _remote_url(path: Path) -> str | None:
    for remote in ("origin", "upstream"):
        out = _run(["git", "config", "--get", f"remote.{remote}.url"], path)
        if out:
            return out.strip()
    out = _run(["git", "remote"], path)
    if out and out.strip():
        first = out.strip().splitlines()[0]
        url = _run(["git", "config", "--get", f"remote.{first}.url"], path)
        if url:
            return url.strip()
    return None


# scp-style remotes: ``git@github.com:owner/repo``. The ``user@`` part is
# optional in git's own parser, so it is optional here too.
_SCP_LIKE = re.compile(r"^(?:[\w.+-]+@)?([\w.-]+):(?!/)(.+)$")
_SCHEME = re.compile(r"^[a-zA-Z][\w+.-]*://")


def normalize_remote(url: str) -> str:
    """Reduce a remote URL to a lowercase ``host/owner/repo`` key.

    ``git@github.com:tksimson/GitFoot.git``, ``https://github.com/tksimson/GitFoot``,
    ``ssh://git@github.com/tksimson/GitFoot.git/`` and ``github.com:tksimson/gitfoot``
    all collapse to one key.

    The whole key is lowercased, not just the host. Two remotes for one project
    differing only in capitalisation is a real and common thing; two genuinely
    different projects on one machine differing only in capitalisation is not.
    Case is preserved separately for display.
    """
    url = url.strip().rstrip("/")

    scp = _SCP_LIKE.match(url)
    if scp:
        host, path = scp.group(1), scp.group(2)
    elif _SCHEME.match(url):
        without_scheme = _SCHEME.sub("", url)
        host, _, path = without_scheme.partition("/")
        host = host.rpartition("@")[2]
        host = host.partition(":")[0]
    else:
        return f"path:{url}"

    path = path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not path:
        return f"path:{url}"
    return f"{host}/{path}".lower()


def _name_from(remote: str | None, path: Path) -> str:
    """Display name, taken from the remote with its original capitalisation."""
    if remote and not normalize_remote(remote).startswith("path:"):
        tail = remote.strip().rstrip("/").rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if tail.endswith(".git"):
            tail = tail[:-4]
        if tail:
            return tail
    return path.name


def read_commits(
    repo: Found,
    emails: set[str],
    since: str | None = None,
) -> SyncResult:
    """Read your commits from one repository.

    Merge commits are excluded: they record an integration, not a day's work,
    and ``--numstat`` reports nothing for them anyway.

    All refs are scanned, not just the checked-out branch, so work sitting on a
    feature branch still counts. Deduplication happens on SHA in the store.
    """
    cmd = [
        "git",
        "log",
        "--all",
        "--no-merges",
        "--numstat",
        "--date=short",
        f"--pretty=format:{RECORD_SEP}%H{FIELD_SEP}%ad{FIELD_SEP}%ae",
    ]
    if since:
        cmd.append(f"--since={since}")

    try:
        code, stdout, stderr = _capture(cmd, repo.path, GIT_TIMEOUT, MAX_LOG_BYTES)
    except subprocess.TimeoutExpired:
        return SyncResult(repo, [], f"timed out after {GIT_TIMEOUT}s")
    except _TooMuchOutput:
        return SyncResult(repo, [], f"history larger than {MAX_LOG_BYTES // 2**20} MB")
    except OSError as exc:
        return SyncResult(repo, [], sanitize(str(exc)))

    if code != 0:
        detail = stderr.strip().splitlines()
        # An empty repository has no HEAD; that is not an error worth reporting.
        message = sanitize(detail[-1]) if detail else f"git exited {code}"
        if "does not have any commits" in message or "unknown revision" in message:
            return SyncResult(repo, [], None)
        return SyncResult(repo, [], message)

    return SyncResult(repo, list(parse_log(stdout, emails)), None)


class _TooMuchOutput(Exception):
    """A repository produced more log output than we are willing to hold."""


def _capture(
    cmd: list[str], cwd: Path, timeout: int, limit: int
) -> tuple[int, str, str]:
    """Run a command, spooling output to disk and refusing to load it past ``limit``.

    ``subprocess.run(capture_output=True)`` reads until EOF, so how much memory
    it uses is the child's decision. ``--numstat`` output grows with files
    changed rather than with commits, eight of these run concurrently during a
    sync, and a repository can be built to emit gigabytes. Spooling to a
    temporary file keeps that off the heap, and the size check happens before
    anything is read back.

    Both streams go to files rather than pipes, so there is no buffer to fill
    and no deadlock to reach: draining stdout while git blocks writing stderr
    is the classic way to hang here.
    """
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        code = subprocess.run(
            cmd, stdout=out, stderr=err, cwd=str(cwd), timeout=timeout
        ).returncode

        if out.tell() > limit:
            raise _TooMuchOutput

        out.seek(0)
        err.seek(0)
        return (
            code,
            out.read().decode("utf-8", errors="replace"),
            err.read(_STDERR_LIMIT).decode("utf-8", errors="replace"),
        )


def parse_log(output: str, emails: set[str]) -> Iterable[Commit]:
    """Turn ``git log --numstat`` output into commits authored by ``emails``.

    An empty ``emails`` set matches nothing. That is deliberate: attributing
    every commit in a shared repository to whoever ran the tool is exactly the
    bug this replaces.
    """
    wanted = {e.lower() for e in emails}
    if not wanted:
        return

    for record in output.split(RECORD_SEP):
        record = record.strip("\n")
        if not record:
            continue

        header, _, body = record.partition("\n")
        parts = header.split(FIELD_SEP)
        if len(parts) != 3:
            continue
        sha, day, email = (p.strip() for p in parts)
        if email.lower() not in wanted:
            continue
        if not _plausible_day(day):
            continue
        email = sanitize(email)

        insertions = deletions = files = 0
        for line in body.splitlines():
            if not line or "\t" not in line:
                continue
            # numstat is "added<TAB>deleted<TAB>path". A path containing tabs
            # is quoted by git, and splitting only twice keeps it out of the way.
            added, removed = line.split("\t", 2)[:2]
            files += 1
            # Binary files report "-" for both counts.
            if added.isdigit():
                insertions += int(added)
            if removed.isdigit():
                deletions += int(removed)

        yield Commit(
            sha=sha,
            day=day,
            email=email,
            insertions=insertions,
            deletions=deletions,
            files=files,
        )


def _plausible_day(day: str) -> bool:
    """Reject dates that are not a real, sane ``YYYY-MM-DD``.

    Author dates come from whoever made the commit and git prints them back
    verbatim, five-digit years included. ``date.fromisoformat("10000-01-01")``
    raises, and because that value sorts before every real date it becomes
    ``MIN(day)`` and takes the dashboard down on every run, from anywhere in
    the database, with nothing to point at the repository that caused it.

    A year either side of today absorbs timezone edges and honest clock skew.
    """
    try:
        parsed = date.fromisoformat(day)
    except ValueError:
        return False
    today = date.today()
    return today.replace(year=today.year - 100) <= parsed <= today.replace(
        year=today.year + 1
    )


def read_all(
    repos: Sequence[Found],
    emails: set[str],
    since_for: Callable[[Found], str | None],
    workers: int = 8,
    on_done: Callable[[SyncResult], None] | None = None,
) -> list[SyncResult]:
    """Read every repository, in parallel.

    The work is subprocess I/O, so threads are the right tool and the GIL is
    not in the way.
    """
    if not repos:
        return []
    results: list[SyncResult] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(repos))) as pool:
        futures = [
            pool.submit(read_commits, repo, emails, since_for(repo)) for repo in repos
        ]
        for future in futures:
            result = future.result()
            results.append(result)
            if on_done:
                on_done(result)
    return results


def author_counts(repos: Sequence[Found], workers: int = 8) -> list[tuple[str, int]]:
    """Every author email appearing in ``repos``, most prolific first.

    Used only by ``gitfoot init``, to *ask* which addresses are yours. Most
    people commit under two or three over the years -- a work address, a
    personal one, a GitHub noreply -- and a tracker that silently knows about
    one of them undercounts and looks broken.

    The old code did the opposite and treated every author it saw as the user,
    which is how a shared repository turned a colleague's work into yours.
    Same data, opposite default: offered, not assumed.
    """
    counts: Counter[str] = Counter()
    if not repos:
        return []

    def emails_in(repo: Found) -> list[str]:
        out = _run(["git", "log", "--all", "--format=%ae"], repo.path)
        return out.splitlines() if out else []

    with ThreadPoolExecutor(max_workers=min(workers, len(repos))) as pool:
        for lines in pool.map(emails_in, repos):
            counts.update(
                sanitize(line).lower() for line in lines if "@" in line and sanitize(line)
            )

    return counts.most_common()


def git_version() -> str | None:
    """The installed git version, or ``None`` if git is not on PATH."""
    out = _run(["git", "--version"], Path.cwd())
    return out.strip() if out else None


def _run(cmd: list[str], cwd: Path) -> str | None:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, cwd=str(cwd), timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None
