# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-08-05

A full rewrite. The 0.x line counted commits that were not yours, lost history
on upgrade, and double counted by design. Every one of those is a schema or an
identity problem, so the schema and the identity rules were replaced rather
than patched.

Upgrading from 0.x: there is no migration. The old database lived inside the
installed package and its numbers cannot be trusted, so it is not read. Run
`bigfoot init` and then `bigfoot sync --all` to rebuild from your repositories,
which is fast and produces correct numbers.

### Fixed

- **Other people's commits counted as yours.** The author filter was a no-op:
  identity was harvested from every author in the last 100 commits of each
  repository, so in any shared repo your colleagues' work landed in your
  totals. Identity now comes from `git config user.email` (global and system)
  plus addresses added explicitly with `bigfoot config --add-email`, and an
  empty list matches nothing rather than everything.
- **Repositories collided by name.** Repos were keyed by directory basename
  under a `UNIQUE(repo, date)` constraint, so `~/work/api` and `~/oss/api`
  were the same record and overwrote each other's history. Identity is now the
  normalised remote URL (`host/owner/repo`), falling back to the resolved path
  when there is no remote. Two clones of one project now collapse into a
  single entry instead of doubling it.
- **Upgrading destroyed history.** The database was created inside the
  installed package directory, so reinstalling or upgrading wiped it. It now
  lives at `$XDG_DATA_HOME/bigfoot/bigfoot.db`, with `BIGFOOT_HOME` to
  relocate it and `--db` to override it per invocation.
- **Every repository was discovered two or three times.** The default scan
  roots overlapped (`~/dev` inside `~`) and each was walked separately.
  Discovery is now a single pruned walk per root, deduplicated by repo key.
- **Double counting was structural.** Storage was one row per (repo, day)
  holding an aggregate, with no way to know whether a commit had been recorded
  before, so re-running a sync re-added work that was already there. Fixing it
  in one place moved it to another. Storage is now one row per commit keyed by
  SHA and it cannot recur.
- Unreachable code in the motivational message helper: a branch after an
  unconditional return that could never run.

Found by the new test suite while writing it, and fixed before release:

- **Line counts doubled for a commit visible through two clones.** Commits
  were deduplicated with `COUNT(DISTINCT sha)` but insertions and deletions
  were summed over every row, so the commit total was right next to a doubled
  churn figure. Rows are now collapsed on SHA before anything is counted.
- **A corrupt config file crashed every command.** `config.load` caught
  `TOMLDecodeError` but not the `UnicodeDecodeError` raised when the file is
  not valid UTF-8. One bad byte took the whole tool down instead of falling
  back to defaults.
- **`max_depth = true` was accepted as a depth of 1.** `bool` subclasses
  `int`, so the validation passed and discovery silently found almost nothing.
- **Case-varying remotes produced separate repositories.** Only the host was
  lowercased, so `github.com/TKSimson/BigFoot` and `github.com/tksimson/BigFoot`
  were two projects. The whole key is now lowercased, with display names
  keeping their original capitalisation.
- **`git log`-style remotes without a user prefix fell back to a path key.**
  `github.com:owner/repo` is valid scp-style syntax that git accepts; it now
  normalises like the rest.
- **`bigfoot doctor` exited non-zero on a correct but unsynced install**, so
  it could not be used as a health check in a script.
- **A sync in which every repository failed still exited 0**, letting a broken
  cron job look healthy indefinitely.
- **Removing a scan root left its commits in the database**, where they went on
  padding streaks and totals for a directory no longer being tracked.

### Security

Author email and author date are chosen by whoever makes a commit and survive a
clone, so both are hostile input on a machine holding repositories from other
people. Found in review, fixed before release:

- **A future-dated commit froze a repository's sync permanently.** `day` is
  stored as text, so `MAX(day)` was lexicographic: one commit authored 2099
  became the resume point, every later sync asked git for commits since 2098,
  found none, and reported success. The repository stopped updating and nothing
  said so.
- **An out-of-range commit date broke every command.** git prints five-digit
  years verbatim, and such a value sorts before every real date, so it became
  `MIN(day)` and the dashboard raised on it from then on. Dates outside a
  plausible range are now refused when read.
- **Terminal escape sequences from a repository reached the terminal.** Author
  emails and repository names are displayed verbatim, including at the
  `bigfoot init` prompt where identities are chosen from a numbered list. A
  carriage return or OSC sequence in an email could repaint that line to look
  like the user's own address. Control characters are now stripped on the way in.
- **A control character in a harvested email destroyed the config.** It was
  written unescaped, TOML then rejected the file, and the fallback to defaults
  made BigFoot look unconfigured until the next save overwrote the settings.
- **A future-dated commit propped up a dead streak.** The current run was
  counted back from the newest date in the database rather than from today, so
  a commit dated ahead (a colleague thirteen timezones east, a fast clock) kept
  a streak alive that had actually ended days earlier. Future days are now
  ignored when measuring a streak.
- **Unbounded memory while reading a repository.** `git log --numstat` output
  was buffered whole, eight repositories at a time. Output is now spooled to
  disk and refused past a size ceiling.
- Config and database are created mode `0600` rather than following umask.

### Changed

- **Storage is one row per commit, keyed by `(sha, repo_id)`.** Sync is
  idempotent: run it a hundred times and the numbers do not move. Daily figures
  are computed with `COUNT(DISTINCT sha)`, so a commit reachable from two
  clones counts once.
- **`backfill` and `track` merged into one incremental `sync`.** Each
  repository resumes where it left off, with a week of overlap to absorb
  rebases and clock skew. `--days N`, `--since DATE` and `--all` widen the
  range; all three are safe to repeat.
- **Discovery is a pruned pure-Python walk** instead of shelling out to `find`.
  Descent stops at a repository boundary, at `max_depth` (default 6), and at
  ignored directory names. Roots nested inside other roots are walked once.
- **One `git log --numstat` per repository** replaces O(days x repos)
  subprocess calls. The old backfill ran a `git log` per (day, repo) pair and a
  `git show` per commit: over 3,600 process spawns for 90 days across 40
  repos. Repositories are now read eight at a time in a thread pool, and a
  failure in one is reported without aborting the sync.
- **Zero runtime dependencies.** Dropped `click`, `rich`, `pyyaml` and
  `python-dateutil` for `argparse`, hand-written ANSI output, `tomllib` and
  `datetime`. Install is one pure-Python package with nothing to resolve.
- **Configuration is TOML at an XDG path**
  (`$XDG_CONFIG_HOME/bigfoot/config.toml`), read with the stdlib `tomllib` and
  written by hand. It holds `roots`, `emails`, `ignore_dirs` and `max_depth`,
  and it is a file you can read and edit.
- Merge commits are excluded, and all refs are scanned rather than just the
  checked-out branch, so work on unmerged feature branches counts.
- `--json` on every command, progress on stderr, `--no-color` and `NO_COLOR`
  honoured, so output composes with `jq` and shell pipelines.
- `init` asks before scanning anything and never guesses a directory on its
  own.
- Requires Python 3.11 (for `tomllib`), up from 3.8.

### Removed

- Achievements and the hall of fame. They turned attendance into a score, which
  is the thing this tool is explicitly not.
- Randomised motivational messaging.
- `track` and `backfill`, replaced by `sync`.

[Unreleased]: https://github.com/tksimson/BigFoot/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/tksimson/BigFoot/releases/tag/v1.0.0
