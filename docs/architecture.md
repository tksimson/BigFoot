# Architecture

Written for someone about to open a PR. Four decisions carry most of the
design; the rest is small functions.

## The data model: one row per commit

```sql
CREATE TABLE commits (
    sha        TEXT NOT NULL,
    repo_id    INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
    day        TEXT NOT NULL,
    email      TEXT NOT NULL,
    insertions INTEGER NOT NULL DEFAULT 0,
    deletions  INTEGER NOT NULL DEFAULT 0,
    files      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sha, repo_id)
);
```

0.x stored daily aggregates: one row per (repo, date) holding a count. That
shape has no way to tell whether a commit has been seen before, so every sync
either added work twice or needed a hand-written guard against doing so. Double
counting was not a bug that kept coming back; it was the schema working as
designed.

With the SHA as the key, `INSERT OR IGNORE` makes sync idempotent by
construction. Run it a hundred times and the numbers do not move. Overlapping
date ranges become free, which is why `sync` re-reads a week of history it
already has: cheap insurance against rebases and clock skew, with no
correctness cost.

The price is rows. Ten years of heavy work is a few hundred thousand rows and a
database in the tens of megabytes, and every dashboard query is a `GROUP BY` on
an indexed `day` column. Aggregation is a query concern, not a storage concern.
Counts use `COUNT(DISTINCT sha)` so one commit reachable from two clones is
counted once.

## Repo identity: normalised remote URL

`_identify()` in `gitscan.py` keys a repository by its remote, reduced to
`host/owner/repo`:

```
git@github.com:tksimson/BigFoot.git
https://github.com/tksimson/BigFoot
ssh://git@github.com/tksimson/BigFoot.git
        > github.com/tksimson/BigFoot
```

The host is lowercased; the path is not, because on some hosts it is
case-significant.

Repos with no remote fall back to `path:<resolved path>`.

0.x keyed on directory basename under a `UNIQUE(repo, date)` constraint, so
`~/work/api` and `~/oss/api` were the same repository and silently overwrote
each other's history. Basename is not an identity; it is a display name, and it
is still used as one in the `name` column.

The upside of remote-keying is that clones collapse. `~/dev/bigfoot` and
`/tmp/bigfoot-review` are one entry with one set of commits, not a doubled
streak. The downside is that a fork and its upstream share a key when the fork
has no distinct remote configured, which is the right call far more often than
not.

## Discovery: one pruned walk

`discover()` is a plain `os.walk` per configured root, with three prunes:

1. A directory containing `.git` is a repository. Record it and set
   `dirnames[:] = []` so descent stops at the boundary. Submodules and vendored
   checkouts inside a project are not separate entries.
2. Depth past `max_depth` (default 6) below the root prunes.
3. Names in `ignore_dirs` prune: `node_modules`, `.venv`, `target`, `dist`,
   caches, and so on.

There is deliberately no fourth rule pruning dot-directories. An earlier draft
had one, and it was fast and wrong: it silently lost dotfiles repos and things
like `~/.config/nvim`, because the walk never descended far enough to see their
`.git`. A list you can read and edit beats a rule you have to reverse-engineer
from surprising results.

Roots that sit inside another root are dropped before walking (`_outermost`),
and results land in a dict keyed by repo key, so overlapping roots deduplicate.
Identifying each candidate costs a `git config` call, so those run in a thread
pool.
0.x shelled out to `find` once per root with default roots that overlapped
(`~/dev` and `~`), so most repositories were discovered two or three times and
every one of them cost a subprocess.

## Reading: one `git log` per repository

```
git log --all --no-merges --numstat --date=short \
        --pretty=format:<RS>%H<US>%ad<US>%ae [--since=DATE]
```

One call per repository, parsed in `parse_log()`, bucketed by date in Python.
0.x ran `git log` for every (day, repo) pair and then `git show` per commit:
90 days across 40 repos was over 3,600 subprocess spawns before a single line
was counted. Process spawn dominated the runtime, and it scaled with the range
requested rather than with the amount of work that existed.

Details that matter if you touch this:

- `\x1e` and `\x1f` separate records and fields, because commit metadata can
  contain anything a newline-based format would be confused by.
- `--all` scans every ref, so work on unmerged feature branches counts. The SHA
  primary key absorbs the duplicates that follow from a commit being reachable
  from several refs.
- `--no-merges` because a merge records an integration, not a day's work, and
  `--numstat` reports nothing for it anyway.
- Binary files report `-` for both counts. `isdigit()` guards the parse.
- Repositories are read in a `ThreadPoolExecutor` (8 workers). The work is
  subprocess I/O, so the GIL is not in the way.
- Failures are per repository: a timeout or a corrupt repo returns a
  `SyncResult` with an error string and the rest of the sync continues.

## Author identity

`config.git_emails()` reads `git config --global/--system user.email` and
nothing else. 0.x harvested every author from the last 100 commits of each
repository, which meant that in any shared repo your colleagues' work was
recorded as yours. Additional addresses are added explicitly with
`bigfoot config --add-email`.

`parse_log()` treats an empty email set as matching nothing, deliberately. The
failure mode of a wrong default here is silently inflating someone's numbers,
so the default is to count zero and say so.

## Module map

| Module | Responsibility | Depends on |
| --- | --- | --- |
| `cli.py` | argparse surface, command handlers, JSON output | everything |
| `config.py` | XDG paths, TOML read/write, git identity | stdlib |
| `gitscan.py` | repo discovery, `git log` parsing | `store` (for `Commit`) |
| `store.py` | SQLite schema and queries | stdlib |
| `stats.py` | streaks, activity grid, snapshot | `store` |
| `render.py` | dashboard layout, strings | `stats`, `term` |
| `term.py` | colour, width, capability detection | stdlib |

The dependency direction is one way: `stats` never touches git, `gitscan` never
touches the terminal, `store` never formats anything. That is what makes the
streak rules testable without a database full of fixtures and a TTY.

## If you are adding something

- New numbers on the dashboard: add a query to `store.py`, a field to
  `stats.Snapshot`, then render it. Do not compute in the renderer.
- New date logic: it belongs in `stats.py` as a pure function taking `today` as
  an argument. Every function there does, which is why they are testable.
- A schema change needs `SCHEMA_VERSION` bumped and a migration path in
  `Store._migrate()`. The database is the user's history; upgrades must not
  destroy it. That was the 0.x failure of shipping the database inside the
  installed package.
- A runtime dependency needs a very good argument. The zero-dependency install
  is a feature people came for.
