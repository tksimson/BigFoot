"""Command line interface.

argparse rather than click, because the whole point of this rewrite is that
`bigfoot` installs instantly and cannot break on a dependency resolution. The
help text is hand-written for the same reason: it is the first thing anyone
sees, and it should read like a manual page, not a pitch deck.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from . import __version__, config, gitscan, render, stats, term
from .store import Store

# Where projects usually live. Only ever *offered* -- never scanned without
# the user saying yes. A tool that walks your home directory on first run
# deserves the reception it gets.
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
        print(f"bigfoot: {exc}", file=sys.stderr)
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
            print(render.first_run(out, configured=cfg.configured))
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
        print(render.first_run(out, configured=False))
        return 1

    emails = set(cfg.emails)
    if not emails:
        print(
            "bigfoot: no author emails configured, so nothing can be attributed to you.\n"
            "         run 'bigfoot config --add-email you@example.com'",
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
            f"bigfoot: no git repositories under {', '.join(cfg.roots)}",
            file=sys.stderr,
        )
        return 1

    with open_store(args) as store:
        ids = {f.key: store.upsert_repo(f.key, f.name, str(f.path)) for f in found}

        def since_for(repo: gitscan.Found) -> str | None:
            if since_override is not None:
                return since_override
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
            print(f"bigfoot: {name}: {message}", file=sys.stderr)
    return status


def cmd_repos(args: argparse.Namespace, out: term.Terminal) -> int:
    cfg = config.load()

    if args.add:
        missing = [p for p in args.add if not Path(p).expanduser().is_dir()]
        if missing:
            # A mistyped root would otherwise sit in the config forever,
            # contributing nothing and explaining nothing.
            print(f"bigfoot: no such directory: {', '.join(missing)}", file=sys.stderr)
            return 1
        updated = config.with_roots(cfg, args.add)
        config.save(updated)
        print(f"scanning {len(updated.roots)} directories. run 'bigfoot sync'.")
        return 0

    if args.remove:
        drop = [Path(p).expanduser().resolve() for p in args.remove]
        kept = [r for r in cfg.roots if Path(r) not in drop]
        if len(kept) == len(cfg.roots):
            print(f"bigfoot: not a tracked root: {', '.join(args.remove)}", file=sys.stderr)
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


def cmd_init(args: argparse.Namespace, out: term.Terminal) -> int:
    """Set up tracking: choose the directories, then confirm the identities.

    Both steps ask. Scanning someone's home directory and deciding on their
    behalf which commits are theirs are exactly the two things a tool like this
    should not do quietly.
    """
    cfg = config.load()
    interactive = sys.stdin.isatty() and not args.yes

    # 1. Which directories.
    roots = [str(Path(r).expanduser().resolve()) for r in (args.root or [])]
    if not roots:
        suggested = [p for p in CANDIDATE_ROOTS if Path(p).expanduser().is_dir()]
        if not suggested:
            print(
                "bigfoot: none of the usual project directories exist here.\n"
                "         point it somewhere: bigfoot init --root ~/somewhere",
                file=sys.stderr,
            )
            return 1
        print(render.init_roots(out, suggested))
        if not sys.stdin.isatty() and not args.yes:
            # Nobody is there to answer, and consent cannot be assumed from
            # silence. The whole point of offering rather than guessing is
            # lost if a redirected stdin counts as yes.
            print(
                "bigfoot: not a terminal, so nothing was assumed.\n"
                "         re-run with -y to accept these, or --root DIR to choose.",
                file=sys.stderr,
            )
            return 1
        if interactive and not confirm("scan these?"):
            print("nothing changed. try: bigfoot init --root ~/somewhere")
            return 0
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
        print(f"bigfoot: no git repositories under {', '.join(cfg.roots)}", file=sys.stderr)
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
            "bigfoot: no identity chosen, so nothing would be counted.\n"
            "         set git's user.email, or: bigfoot config --add-email you@example.com",
            file=sys.stderr,
        )
        return 1

    cfg = config.with_emails(cfg, mine)
    config.save(cfg)
    print(f"tracking {len(found)} repositories as {', '.join(cfg.emails)}")
    print(f"config: {cfg.path}")

    if args.no_sync:
        print("run 'bigfoot sync' when ready.")
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

    ``None`` means "incremental": each repo picks up where it left off.
    """
    if getattr(args, "all", False):
        return "1970-01-01"
    if getattr(args, "since", None):
        return args.since
    if getattr(args, "days", None):
        return (date.today() - timedelta(days=args.days)).isoformat()
    return None


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
        prog="bigfoot",
        description="Your local git activity, at a glance. Nothing leaves your machine.",
        epilog=(
            "run 'bigfoot init' once, then 'bigfoot sync' whenever you want fresh numbers.\n"
            "commit counts are not productivity. this only shows whether you showed up."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"bigfoot {__version__}")
    parser.set_defaults(command=None)

    # Shared flags are attached to the bare `bigfoot` invocation *and* to every
    # subcommand, so `bigfoot --json sync` and `bigfoot sync --json` both work.
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
