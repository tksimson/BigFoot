"""Command line interface.

argparse rather than click, because the whole point of this rewrite is that
`gitfoot` installs instantly and cannot break on a dependency resolution. The
help text is hand-written for the same reason: it is the first thing anyone
sees, and it should read like a manual page, not a pitch deck.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shlex
import shutil
import sys
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path

from . import __version__, config, gitscan, render, stats, term
from .store import Store

# Where projects usually live. Only ever *offered* -- never tracked, and no
# commit ever read, without the user saying yes. `init` does walk these to
# count what is in them, because a bare path is not enough to choose from, but
# nothing outside this list is touched and nothing is recorded until asked.
CANDIDATE_ROOTS = (
    "~/dev",
    "~/code",
    "~/src",
    "~/projects",
    "~/work",
    "~/repos",
    "~/git",
    "~/Documents/GitHub",
)

# Days of overlap re-read on an incremental sync. Cheap insurance against
# rebases and clock skew; duplicate SHAs are ignored by the store anyway.
SYNC_OVERLAP_DAYS = 7

# How far back a sync reaches. Sentinels rather than dates, because "everything"
# has to become *no* --since argument: there is no date old enough to mean it
# safely (see resolve_since).
INCREMENTAL = object()
FULL = object()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    out = term.Terminal(color=args.color, stream=sys.stdout)
    try:
        return dispatch(args, out)
    except KeyboardInterrupt:
        print(file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0
    except Exception as exc:
        print(f"gitfoot: {exc}", file=sys.stderr)
        return 1


def dispatch(args: argparse.Namespace, out: term.Terminal) -> int:
    handlers = {
        None: cmd_dashboard,
        "sync": cmd_sync,
        "repos": cmd_repos,
        "config": cmd_config,
        "init": cmd_init,
        "doctor": cmd_doctor,
    }
    return handlers[args.command](args, out)


# -- commands ------------------------------------------------------------


def cmd_dashboard(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()
    with open_store(args) as store:
        if store.is_empty():
            if args.json:
                emit_json({"commits": 0, "configured": cfg.configured})
                return 0
            print(render.first_run(out, configured=cfg.configured, prefix=invocation()))
            return 0

        snap = stats.snapshot(store, weeks=args.weeks)
        if args.json:
            emit_json(snapshot_json(snap))
            return 0
        print(render.dashboard(snap, out, weeks=args.weeks))
    return 0


def cmd_sync(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()
    if not cfg.configured:
        print(render.first_run(out, configured=False, prefix=invocation()))
        return 1

    emails = set(cfg.emails)
    if not emails:
        print(
            "gitfoot: no author emails configured, so nothing can be attributed to you.\n"
            f"         run '{invocation()} config --add-email you@example.com'",
            file=sys.stderr,
        )
        return 1

    since_override = resolve_since(args)
    quiet = getattr(args, "quiet", False) or args.json

    started = time.monotonic()
    progress = Progress(not quiet)
    progress.show("scanning for repositories")

    found = gitscan.discover(cfg.root_paths(), cfg.ignore_dirs, cfg.max_depth)
    if not found:
        progress.clear()
        print(
            f"gitfoot: no git repositories under {', '.join(cfg.roots)}",
            file=sys.stderr,
        )
        return 1

    with open_store(args) as store:
        ids = {f.key: store.upsert_repo(f.key, f.name, str(f.path)) for f in found}

        def since_for(repo: gitscan.Found) -> str | None:
            if since_override is FULL:
                return None
            if since_override is not INCREMENTAL:
                return since_override  # an explicit date
            last = store.latest_day(ids[repo.key])
            if not last:
                return None
            overlap = date.fromisoformat(last) - timedelta(days=SYNC_OVERLAP_DAYS)
            return overlap.isoformat()

        done = [0]

        def tick(_: gitscan.SyncResult) -> None:
            done[0] += 1
            progress.show(f"reading {done[0]} of {len(found)} repositories")

        results = gitscan.read_all(found, emails, since_for, on_done=tick)

        errors: list[tuple[str, str]] = []
        stamp = date.today().isoformat()
        before = store.total_commits()
        for result in results:
            if result.error:
                errors.append((result.repo.name, result.error))
                continue
            repo_id = ids[result.repo.key]
            store.add_commits(repo_id, result.commits)
            store.mark_synced(repo_id, stamp)

        # Report the change in distinct commits rather than rows written. The
        # two differ only when one commit is visible through two repositories,
        # and "6 new, 3 total" on the same line is worse than useless.
        total = store.total_commits()
        added = total - before

    elapsed = time.monotonic() - started
    progress.clear()

    # A sync where every repository failed is a failed sync. Reporting success
    # would let a broken cron job look healthy indefinitely.
    status = 1 if errors and len(errors) == len(found) else 0

    if args.json:
        emit_json(
            {
                "repositories": len(found),
                "commits_new": added,
                "commits_total": total,
                "seconds": round(elapsed, 2),
                "errors": [{"repo": r, "error": e} for r, e in errors],
            }
        )
        return status

    if not quiet:
        print(render.sync_summary(out, len(found), added, total, elapsed, errors))
    elif errors:
        for name, message in errors:
            print(f"gitfoot: {name}: {message}", file=sys.stderr)
    return status


def cmd_repos(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()

    if args.add:
        missing = [p for p in args.add if not Path(p).expanduser().is_dir()]
        if missing:
            # A mistyped root would otherwise sit in the config forever,
            # contributing nothing and explaining nothing.
            print(f"gitfoot: no such directory: {', '.join(missing)}", file=sys.stderr)
            return 1
        updated = config.with_roots(cfg, args.add)
        config.save(updated)
        print(f"scanning {len(updated.roots)} directories. run '{invocation()} sync'.")
        return 0

    if args.remove:
        drop = [Path(p).expanduser().resolve() for p in args.remove]
        kept = [r for r in cfg.roots if Path(r) not in drop]
        if len(kept) == len(cfg.roots):
            print(f"gitfoot: not a tracked root: {', '.join(args.remove)}", file=sys.stderr)
            return 1
        config.save(dataclasses.replace(cfg, roots=kept))

        # Dropping a root should drop what it contributed. Leaving the rows
        # behind means removed repositories keep padding the streak, which is
        # the sort of quiet wrongness this rewrite exists to remove.
        forgotten = 0
        with open_store(args) as store:
            for repo in store.repos():
                path = Path(repo.path)
                if any(path == d or path.is_relative_to(d) for d in drop):
                    forgotten += store.forget_repo(repo.key)
        print(
            f"scanning {len(kept)} directories. "
            f"forgot {forgotten} repositories and their history."
        )
        return 0

    with open_store(args) as store:
        rows = store.repo_stats()
        total = store.total_commits()

    if args.json:
        emit_json(
            {
                "roots": cfg.roots,
                "repositories": [
                    {
                        "name": r.name,
                        "path": r.path,
                        "commits": r.commits,
                        "last_commit": r.last_commit,
                    }
                    for r in rows
                ],
            }
        )
        return 0

    print(render.repo_list(out, cfg.roots, rows, total))
    return 0


def cmd_config(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()

    if args.path:
        print(cfg.path)
        return 0

    if args.add_email:
        updated = config.with_emails(cfg, args.add_email)
        config.save(updated)
        print(f"attributing commits from: {', '.join(updated.emails)}")
        return 0

    if args.json:
        emit_json(
            {
                "path": str(cfg.path),
                "roots": cfg.roots,
                "emails": cfg.emails,
                "max_depth": cfg.max_depth,
                "database": str(db_location(args)),
            }
        )
        return 0

    print(render.config_view(out, cfg, db_location(args)))
    return 0


CHANGE_PROMPT = "\n  change what? [numbers to toggle, or type to add, Enter to keep] "


def reconfigure(args: argparse.Namespace, out: term.Terminal, cfg: config.Config, how: str) -> int:
    """Already set up: show what is tracked, and change it in place.

    Re-running `init` used to offer the same eight well-known directories
    whether or not they were already tracked, and never showed what *was*
    tracked -- so the one command anybody would try could neither add a
    directory it had not heard of nor remove one.
    """
    progress = Progress()
    progress.show("counting repositories")

    on_paths = [Path(r) for r in cfg.roots]
    off_paths = [
        candidate
        for p in CANDIDATE_ROOTS
        if (candidate := Path(p).expanduser()).is_dir()
        and not any(candidate == t or t in candidate.parents for t in on_paths)
    ]
    counts = count_repos(on_paths + off_paths, cfg)
    found = gitscan.discover(on_paths, cfg.ignore_dirs, cfg.max_depth)
    progress.show("reading author names")
    authors = dict(gitscan.author_counts(found)) if found else {}
    progress.clear()

    def repo_note(path: Path) -> str:
        return _plural(counts[path], "repo")

    rows = [(str(p), repo_note(p)) for p in on_paths]
    spare = [(str(p), repo_note(p)) for p in off_paths]
    print(render.toggle_list(out, rows, spare, "Scanning these:", "Also found:"))

    change = ask_changes(
        len(rows) + len(spare), CHANGE_PROMPT, _as_directory, "no such directory"
    )
    dropped: list[Path] = []
    if change:
        toggled, added = change
        dropped = [on_paths[i] for i in toggled if i < len(on_paths)]
        gained = [str(off_paths[i - len(on_paths)]) for i in toggled if i >= len(on_paths)]
        keep = [str(p) for p in on_paths if p not in dropped]
        cfg = config.with_roots(dataclasses.replace(cfg, roots=keep), gained + added)

    # Identities, the same way: what counts as you, and who else showed up.
    known = {e.lower() for e in cfg.emails}
    mine = [(e, _plural(authors.get(e.lower(), 0), "commit")) for e in cfg.emails]
    others = [(e, _plural(n, "commit")) for e, n in authors.items() if e.lower() not in known]
    print(render.toggle_list(out, mine, others, "Counted as you:", "Also found:"))

    identity = ask_changes(
        len(mine) + len(others), CHANGE_PROMPT, _as_email, "not an email address"
    )
    forgotten_emails: list[str] = []
    if identity:
        toggled, added = identity
        forgotten_emails = [cfg.emails[i] for i in toggled if i < len(mine)]
        gained = [others[i - len(mine)][0] for i in toggled if i >= len(mine)]
        keep = [e for e in cfg.emails if e not in forgotten_emails]
        cfg = config.with_emails(dataclasses.replace(cfg, emails=keep), gained + added)

    if not cfg.roots:
        print("gitfoot: nothing left to scan, so nothing was saved.", file=sys.stderr)
        return 1
    if not cfg.emails:
        print("gitfoot: nobody left to count, so nothing was saved.", file=sys.stderr)
        return 1

    config.save(cfg)

    # Dropping a root or an identity has to drop what it contributed, or the
    # streak goes on being padded by history nobody claims.
    forgotten = 0
    with open_store(args) as store:
        for repo in store.repos():
            path = Path(repo.path)
            if any(path == d or path.is_relative_to(d) for d in dropped):
                forgotten += store.forget_repo(repo.key)
        for email in forgotten_emails:
            store.forget_email(email)

    print(f"tracking {_plural(len(cfg.roots), 'directory')} as {', '.join(cfg.emails)}")
    if forgotten or forgotten_emails:
        print(
            f"forgot {_plural(forgotten, 'repository')} "
            f"and {_plural(len(forgotten_emails), 'identity')}."
        )
    print(f"config: {cfg.path}")

    if args.no_sync:
        print(f"run '{how} sync' when ready.")
        return 0
    return cmd_sync(
        argparse.Namespace(**{**vars(args), "command": "sync", "days": None, "since": None,
                              "all": True}),
        out,
    )


def cmd_init(args: argparse.Namespace, out: term.Terminal) -> int:
    """Set up tracking: choose the directories, then confirm the identities.

    Both steps ask. Scanning someone's home directory and deciding on their
    behalf which commits are theirs are exactly the two things a tool like this
    should not do quietly.
    """
    cfg = config.load()
    interactive = sys.stdin.isatty() and not args.yes
    how = invocation()

    # Already set up and nothing named on the command line: this is somebody
    # coming back to change something, not to start over.
    if cfg.configured and interactive and not args.root and not args.email:
        return reconfigure(args, out, cfg, how)

    # 1. Which directories.
    roots = [str(Path(r).expanduser().resolve()) for r in (args.root or [])]
    if not roots:
        suggested = [p for p in CANDIDATE_ROOTS if Path(p).expanduser().is_dir()]
        if not suggested:
            print(
                "gitfoot: none of the usual project directories exist here.\n"
                f"         point it somewhere: {how} init --root ~/somewhere",
                file=sys.stderr,
            )
            return 1

        # Counted before the question, not after: an empty directory and one
        # holding thirty repositories look identical as bare paths. One scan
        # across all of them, attributed afterwards -- a scan per candidate
        # would run git once per repository in directories about to be declined.
        counting = Progress()
        counting.show("counting repositories")
        bases = [Path(p).expanduser() for p in suggested]
        tally = dict.fromkeys(bases, 0)
        for found in gitscan.discover(bases, cfg.ignore_dirs, cfg.max_depth):
            for base in bases:
                if base == found.path or base in found.path.parents:
                    tally[base] += 1
                    break
        entries = list(zip(suggested, (tally[b] for b in bases), strict=True))
        counting.clear()

        print(render.init_roots(out, entries))
        if not sys.stdin.isatty() and not args.yes:
            # Nobody is there to answer, and consent cannot be assumed from
            # silence. The whole point of offering rather than guessing is
            # lost if a redirected stdin counts as yes.
            print(
                "gitfoot: not a terminal, so nothing was assumed.\n"
                "         re-run with -y to accept these, or --root DIR to choose.",
                file=sys.stderr,
            )
            return 1
        if interactive:
            roots = ask_roots(entries)
            if not roots:
                print(f"nothing changed. try: {how} init --root ~/somewhere")
                return 0
        else:
            roots = [str(Path(p).expanduser().resolve()) for p in suggested]

    cfg = config.with_roots(cfg, roots)

    # 2. Which commits are yours.
    progress = Progress()
    progress.show("looking for repositories")
    found = gitscan.discover(cfg.root_paths(), cfg.ignore_dirs, cfg.max_depth)
    progress.show("reading author names")
    authors = gitscan.author_counts(found) if found else []
    progress.clear()

    if not found:
        print(f"gitfoot: no git repositories under {', '.join(cfg.roots)}", file=sys.stderr)
        return 1

    # Identities already known are yours whether or not they turn up in the
    # scan. Filtering them by what was found would report "nobody yet" to
    # someone whose git identity is set perfectly well but who has not yet
    # committed inside these particular directories.
    mine = config.dedupe(list(cfg.emails) + config.git_emails() + list(args.email or []))
    known = {e.lower() for e in mine}
    others = [(e, n) for e, n in authors if e.lower() not in known]

    if interactive and others:
        print(render.init_emails(out, len(found), mine, others))
        mine += [others[i][0] for i in ask_indexes("also count as you", len(others))]
    elif not args.yes:
        print(render.init_emails(out, len(found), mine, others[:8]))

    if not mine:
        print(
            "gitfoot: no identity chosen, so nothing would be counted.\n"
            f"         set git's user.email, or: {how} config --add-email you@example.com",
            file=sys.stderr,
        )
        return 1

    cfg = config.with_emails(cfg, mine)
    config.save(cfg)
    print(f"tracking {len(found)} repositories as {', '.join(cfg.emails)}")
    print(f"config: {cfg.path}")

    if args.no_sync:
        print(f"run '{how} sync' when ready.")
        return 0

    sync_args = argparse.Namespace(
        **{**vars(args), "command": "sync", "days": None, "since": None, "all": True}
    )
    return cmd_sync(sync_args, out)


def cmd_doctor(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()
    checks: list[tuple[str, bool, str]] = []

    git = gitscan.git_version()
    checks.append(("git", bool(git), git or "not found"))
    checks.append(
        ("config", cfg.path.is_file(), str(cfg.path) if cfg.path.is_file() else "not written yet")
    )
    checks.append(("roots", bool(cfg.roots), ", ".join(cfg.roots) or "none configured"))
    checks.append(
        ("identity", bool(cfg.emails), ", ".join(cfg.emails) or "no emails configured")
    )

    path = db_location(args)
    try:
        with open_store(args) as store:
            total = store.total_commits()
            repos = len(store.repos())
            first = store.first_day()
        checks.append(("database", True, f"{path} ({total} commits, {repos} repos)"))
        # Informational, never a failure. An install that is set up correctly
        # but has not synced yet is healthy, and should not exit non-zero.
        checks.append(("history", True, f"since {first}" if first else "nothing synced yet"))
    except Exception as exc:
        checks.append(("database", False, f"{path}: {exc}"))

    if args.json:
        emit_json({"checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks]})
        return 0

    print(render.doctor(out, checks))
    return 0 if all(ok for _, ok, _ in checks) else 1


# -- helpers -------------------------------------------------------------


def open_store(args: argparse.Namespace) -> Store:
    return Store(db_location(args))


def db_location(args: argparse.Namespace) -> Path:
    return Path(args.db).expanduser() if args.db else config.db_path()


def resolve_since(args: argparse.Namespace) -> str | None:
    """Translate the sync range flags into a ``--since`` value.

    Three outcomes, and they are genuinely distinct:

    * ``INCREMENTAL`` -- each repository picks up where it left off.
    * ``FULL`` -- no ``--since`` argument at all.
    * a date string -- passed through to git.

    ``--all`` must not be expressed as an early date. ``--since=1970-01-01``
    converts to a negative timestamp in any timezone ahead of UTC, git rejects
    it, and the command reports success having read nothing. It works in London
    and returns zero commits in Warsaw, which is the worst kind of bug to ship.
    """
    if getattr(args, "all", False):
        return FULL
    if getattr(args, "since", None):
        return args.since
    if getattr(args, "days", None):
        return (date.today() - timedelta(days=args.days)).isoformat()
    return INCREMENTAL


class Progress:
    """Transient one-line progress on stderr.

    Only ever writes to a real terminal. Redirected into a file or a pipe the
    carriage returns never redraw anything, so what should have been a single
    updating line becomes a wall of half-overwritten text in the log. Scripts
    and cron get silence instead.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled and sys.stderr.isatty()
        self._width = 0

    def show(self, message: str) -> None:
        if not self.enabled:
            return
        print("\r" + message.ljust(self._width), end="", flush=True, file=sys.stderr)
        self._width = max(self._width, len(message))

    def clear(self) -> None:
        if not self.enabled or not self._width:
            return
        print("\r" + " " * self._width + "\r", end="", flush=True, file=sys.stderr)
        self._width = 0


def invocation() -> str:
    """The command prefix that will actually work in the reader's shell.

    ``uvx gitfoot`` runs from a throwaway environment and installs nothing, so
    every hint that says ``gitfoot init`` names a command the reader cannot
    run. Asking PATH is cheaper than guessing how we were launched, and it is
    the precise condition that decides which of the two spellings works.
    """
    return "gitfoot" if shutil.which("gitfoot") else "uvx gitfoot"


def _plural(count: int, singular: str) -> str:
    if count == 1:
        return f"{count} {singular}"
    plural = singular[:-1] + "ies" if singular.endswith("y") else singular + "s"
    return f"{count} {plural}"


def count_repos(bases: list[Path], cfg: config.Config) -> dict[Path, int]:
    """How many repositories sit under each base, in one walk rather than N."""
    tally = dict.fromkeys(bases, 0)
    if not bases:
        return tally
    for found in gitscan.discover(bases, cfg.ignore_dirs, cfg.max_depth):
        for base in bases:
            if base == found.path or base in found.path.parents:
                tally[base] += 1
                break
    return tally


def ask_changes(
    count: int,
    prompt: str,
    validate: Callable[[str], str | None],
    reject: str,
) -> tuple[list[int], list[str]] | None:
    """Numbers toggle what is listed, anything else is added.

    Returns the toggled indexes and the added values, or None for "leave it
    alone" -- which is what an empty answer means here, unlike first run where
    there is nothing yet to leave alone.
    """
    if not sys.stdin.isatty():
        return None

    for _ in range(3):
        try:
            answer = input(prompt).strip()
        except EOFError:
            return None
        if not answer:
            return None

        toggled: list[int] = []
        added: list[str] = []
        unknown: list[str] = []
        refused: list[str] = []
        for token in _tokens(answer):
            if token.isdigit():
                index = int(token) - 1
                if 0 <= index < count:
                    toggled.append(index)
                else:
                    unknown.append(token)
                continue
            value = validate(token)
            if value:
                added.append(value)
            else:
                refused.append(token)

        if not unknown and not refused:
            return sorted(set(toggled)), config.dedupe(added)
        if unknown:
            print(f"  no option numbered {', '.join(unknown)}", file=sys.stderr)
        if refused:
            print(f"  {reject}: {', '.join(refused)}", file=sys.stderr)
    return None


def _as_directory(token: str) -> str | None:
    path = Path(token).expanduser()
    return str(path.resolve()) if path.is_dir() else None


def _as_email(token: str) -> str | None:
    cleaned = term.sanitize(token)
    return cleaned if "@" in cleaned and " " not in cleaned else None


def _tokens(answer: str) -> list[str]:
    """Split an answer into numbers and paths, keeping spaces inside a path.

    ``~/my projects`` is one answer, not two. A directory that is exactly the
    whole line wins outright; otherwise shell quoting decides, which is the
    convention the reader already has in their fingers.
    """
    if Path(answer).expanduser().is_dir():
        return [answer]
    separated = answer.replace(",", " ")
    try:
        return shlex.split(separated)
    except ValueError:  # an unbalanced quote
        return separated.split()


def ask_roots(entries: list[tuple[str, int]]) -> list[str]:
    """Choose directories to scan: all of them, some of them, or your own.

    A bare number picks from the list and anything else is read as a path. One
    prompt rather than two, because "which of these" and "any others" are the
    same decision and nobody names a project directory ``2``.

    A path that does not exist is refused rather than stored. A typo here would
    otherwise be discovered much later, as a dashboard of zeros with nothing on
    screen to explain it.
    """
    if not sys.stdin.isatty():
        return []

    for _ in range(3):
        try:
            answer = input("\n  scan these? [Enter for all, numbers, or paths] ").strip()
        except EOFError:
            return []
        if not answer:
            return [str(Path(p).expanduser().resolve()) for p, _ in entries]

        picked: list[str] = []
        unknown: list[str] = []
        missing: list[str] = []
        for token in _tokens(answer):
            if token.isdigit():
                index = int(token) - 1
                if 0 <= index < len(entries):
                    picked.append(str(Path(entries[index][0]).expanduser().resolve()))
                else:
                    unknown.append(token)
                continue
            path = Path(token).expanduser()
            if path.is_dir():
                picked.append(str(path.resolve()))
            else:
                missing.append(token)

        if not unknown and not missing:
            return config.dedupe(picked)
        if unknown:
            print(f"  no option numbered {', '.join(unknown)}", file=sys.stderr)
        if missing:
            print(f"  no such directory: {', '.join(missing)}", file=sys.stderr)
    return []


def ask_indexes(question: str, count: int) -> list[int]:
    """Ask for a comma-separated selection. Empty answer selects nothing."""
    if not sys.stdin.isatty() or count == 0:
        return []
    try:
        answer = input(f"\n  {question}? [numbers, or Enter for none] ").strip()
    except EOFError:
        return []
    picked: list[int] = []
    for token in answer.replace(",", " ").split():
        if token.isdigit() and 1 <= int(token) <= count:
            picked.append(int(token) - 1)
    return sorted(set(picked))


def confirm(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"\n  {question} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def emit_json(payload: dict) -> None:
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def snapshot_json(snap: stats.Snapshot) -> dict:
    return {
        "today": {
            "commits": snap.today.commits,
            "repos": snap.today.repos,
            "insertions": snap.today.insertions,
            "deletions": snap.today.deletions,
        },
        "week": {"commits": snap.week.commits, "active_days": snap.active_this_week},
        "month": {"commits": snap.month.commits},
        "year": {"commits": snap.year.commits},
        "streak": {
            "current": snap.streak.current,
            "longest": snap.streak.longest,
            "last_active": snap.streak.last_active,
        },
        "repositories": snap.tracked_repos,
        "first_day": snap.first_day,
        "days": {
            cell.day.isoformat(): cell.commits
            for week in snap.grid.weeks
            for cell in week
            if cell.in_range
        },
    }


def valid_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None


def positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected a number, got {value!r}") from None
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


# -- parser --------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitfoot",
        description="Your local git activity, at a glance. Nothing leaves your machine.",
        epilog=(
            "run 'gitfoot init' once, then 'gitfoot sync' whenever you want fresh numbers.\n"
            "commit counts are not productivity. this only shows whether you showed up."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"gitfoot {__version__}")
    parser.set_defaults(command=None)

    # Shared flags are attached to the bare `gitfoot` invocation *and* to every
    # subcommand, so `gitfoot --json sync` and `gitfoot sync --json` both work.
    # The subcommand copies suppress their defaults; otherwise argparse would
    # apply them after parsing and quietly clobber a flag given before the
    # subcommand name.
    def add_common(target: argparse.ArgumentParser, *, suppress: bool) -> None:
        blank = argparse.SUPPRESS if suppress else None
        target.add_argument(
            "--json",
            action="store_true",
            default=argparse.SUPPRESS if suppress else False,
            help="machine-readable output",
        )
        target.add_argument(
            "--no-color",
            dest="color",
            action="store_false",
            default=blank,
            help="disable colour (NO_COLOR is honoured too)",
        )
        target.add_argument(
            "--db", metavar="PATH", default=blank, help="use a different database file"
        )

    common = argparse.ArgumentParser(add_help=False)
    add_common(common, suppress=True)
    add_common(parser, suppress=False)

    parser.add_argument(
        "--weeks",
        type=positive,
        default=52,
        metavar="N",
        help="weeks of history in the activity calendar (default: 52)",
    )

    subs = parser.add_subparsers(dest="command", metavar="<command>")

    init = subs.add_parser(
        "init",
        parents=[common],
        help="choose which directories to track",
        description="Pick the directories to scan and confirm which commits are yours.",
    )
    init.add_argument("--root", action="append", metavar="DIR", help="directory to scan")
    init.add_argument("--email", action="append", metavar="ADDR", help="an email that is yours")
    init.add_argument("-y", "--yes", action="store_true", help="skip the confirmation")
    init.add_argument("--no-sync", action="store_true", help="do not sync afterwards")

    sync = subs.add_parser(
        "sync",
        parents=[common],
        help="read new commits from your repositories",
        description=(
            "Incremental by default: each repository is read from where it left off. "
            "Re-running is always safe, because commits are keyed by SHA and nothing "
            "is ever counted twice."
        ),
    )
    group = sync.add_mutually_exclusive_group()
    group.add_argument("--days", type=positive, metavar="N", help="re-read the last N days")
    group.add_argument("--since", type=valid_date, metavar="DATE", help="re-read since YYYY-MM-DD")
    group.add_argument("--all", action="store_true", help="re-read complete history")
    sync.add_argument("-q", "--quiet", action="store_true", help="only report errors")

    repos = subs.add_parser(
        "repos", parents=[common], help="show tracked repositories and scan roots"
    )
    repos.add_argument("--add", action="append", metavar="DIR", help="add a scan root")
    repos.add_argument("--remove", action="append", metavar="DIR", help="remove a scan root")

    cfg = subs.add_parser("config", parents=[common], help="show or change settings")
    cfg.add_argument("--path", action="store_true", help="print the config file location")
    cfg.add_argument(
        "--add-email", action="append", metavar="ADDR", help="attribute another email to you"
    )

    subs.add_parser("doctor", parents=[common], help="check the setup")

    return parser


if __name__ == "__main__":
    sys.exit(main())
