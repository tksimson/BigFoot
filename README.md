# gitfoot

A local git activity tracker. Run it, see whether you showed up.

## Commit count is not productivity

It isn't, and gitfoot doesn't claim it is. A day of hard thinking can produce
one commit. A day of nothing can produce twelve. Anyone who has shipped
software knows this.

What a commit history does record is attendance. Days you opened the editor,
days you didn't, and how long the current run is. That is the whole claim.
gitfoot is a mirror, not a score. There is no leaderboard, no ranking, no
badge, and nothing to optimise against.

If you want it to say you were productive, you will have to lie to it.

## What it looks like

```
  Today        4 commits · 3 repos · +177 −108
  Streak       3 days · longest 8
  This week   12 commits · 3 of 7 days · +786 −262
                 api 3 · notes 3 · webapp 3

          Sep  Oct Nov Dec  Jan Feb Mar  Apr May Jun  Jul Aug
  Mon  ▒··▓·▒█▓▓·▒▓·▒██▒█▓▓█▒░█···▒░·░▓▓·███▒▓▒░·▒█·▒▒▓█▒·▓
       ▓▓▒░▓·░▒▓▓▓··▒▒▒░░·▒▒▒▓▒▒█·▓░·░▒▓█·██▓·░▓▓░▒▓░·░·▓▒░
  Wed  ▓▒··░▓·█·▓▒░·██▒·▓░▒·▓▒▒▒░░░░·▒···█▓█·▓░░·░░▒▒·█░·▓▒
       █▓▓·▓·▒·▓░█▓░▓▒·▒░▒▒·▒░▒·▒░▓·▒░▓█▒▒▒░·█▒···▒▒··▓▓▒░
  Fri  ▓▒▒█·▓·▓▒░··░·░▒▒··▒▒··▓·░░░░█▓▒·▓▓▓░▒█░▒░·▒·░·▓▓▒▓
       ·····░··░▒░·░░···░····▒·░··········▒░···▒·░···░░·░·
       ··░░···░········▒·░▒░·····▒··▓··········░····░·░···

       Less ·░▒▓█ More             874 commits · 6 repos · last 52 weeks
```

Colour carries the same information as the shading, so it survives `NO_COLOR`,
a light background, and a pipe. The bottom two rows are the weekend.

## Install

```bash
uvx gitfoot          # run it without installing
pipx install gitfoot # keep it on PATH, isolated
pip install gitfoot
```

Python 3.11+ and git. Zero runtime dependencies: no click, no rich, no
requests, nothing to resolve and nothing to break on upgrade. The install is
one pure-Python package and the standard library.

## Use

```bash
gitfoot init   # pick the directories to scan, confirm which commits are yours
gitfoot sync   # read new commits
gitfoot        # the dashboard
```

`init` runs a full-history sync when it finishes, so the first dashboard has
everything in it. After that, `sync` is the one you repeat.

`init` offers the usual project directories (`~/dev`, `~/code`, `~/src`,
`~/projects`, `~/work`, `~/repos`, `~/git`, `~/Documents/GitHub`) and asks
before scanning any of them. It never picks on its own. Add `-y` to skip the
prompt, `--no-sync` to write config without reading anything yet, and
`--root DIR` / `--email ADDR` (both repeatable) to skip the interactive part
entirely.

`sync` is incremental: each repository is read from where it left off, with a
week of overlap to absorb rebases and clock skew. Re-running is always safe,
because commits are keyed by SHA. To widen the range:

```bash
gitfoot sync --days 90          # re-read the last 90 days
gitfoot sync --since 2024-01-01 # re-read from a date
gitfoot sync --all              # re-read complete history
gitfoot sync -q                 # only report errors, for cron and shell hooks
```

The dashboard takes `--weeks N` for the size of the activity calendar. The
default is 52, a year, which fits in an 80-column terminal:

```bash
gitfoot --weeks 13
```

Other commands:

```bash
gitfoot repos                   # tracked repositories and scan roots
gitfoot repos --add ~/clients   # add a scan root
gitfoot repos --remove ~/old    # stop scanning a root, and forget its history
gitfoot config                  # current settings and where they live
gitfoot config --path           # just the config file path
gitfoot config --add-email me@work.example
gitfoot doctor                  # git, config, identity, database, history
```

Global flags, accepted before or after the subcommand: `--json`, `--no-color`,
`--db PATH`, `--version`.

## Privacy

There is no network code in this repository. No telemetry, no update check, no
account, no API key. The only imports are stdlib, and the check takes ten
seconds:

```bash
grep -rnE '^\s*(import|from) ' gitfoot/ | grep -E 'urllib|http|socket|ssl|requests'
```

That comes back empty. Verify it rather than take my word. The unanchored
pattern matters: an import hidden inside a function would slip past a `^import`
grep, which is exactly the sort of check that looks like proof and isn't.

All the state is two files, both under standard XDG paths:

| What | Where |
| --- | --- |
| database | `$XDG_DATA_HOME/gitfoot/gitfoot.db`, default `~/.local/share/gitfoot/gitfoot.db` |
| config | `$XDG_CONFIG_HOME/gitfoot/config.toml`, default `~/.config/gitfoot/config.toml` |

`GITFOOT_HOME=/path` relocates both, which is how you keep the whole thing
inside a dotfiles repo or throw it away after trying it. `--db PATH` points a
single invocation at a different database. Deleting the two files above is a
complete uninstall of your data.

gitfoot reads commit SHAs, dates, author emails and diff line counts. It does
not read commit messages, file names, file contents, or branch names.

## How it decides what's yours

Only commits whose author email is in your configured list.

Most people have committed under more than one address over the years: a work
one, a personal one, a GitHub noreply. So `gitfoot init` counts the author
emails across the repositories it found, shows them with commit counts, marks
the ones git already knows are yours, and asks about the rest:

```
  Scanned     2 repos

  Counted as you
    you@example.com

  Also found
    1  colleague@work.example  5 commits
    2  you@work.example        3 commits
    3  root@localhost          1 commit

  also count as you? [numbers, or Enter for none] 2
```

Offered, never assumed. That distinction is the whole point: 0.x harvested
every author from the last 100 commits of each repository and treated them all
as you, so on a shared repository your colleagues' work quietly became yours.

Non-interactive when you need it: `--email ADDR` is repeatable, and `-y` takes
the git-configured identities without asking.

The list grows later with:

```bash
gitfoot config --add-email me@work.example
gitfoot sync --all
```

An empty email list matches nothing rather than everything. Two more rules
worth knowing up front:

- **Merge commits are excluded.** They record an integration, not a day's work.
- **All refs are scanned**, not just the checked-out branch, so work sitting on
  a feature branch still counts. Duplicates collapse on SHA.

Repositories are identified by normalised remote URL, so two clones of the same
project on one machine count as one repository, not two.

## JSON

Every command takes `--json` and writes it to stdout. The two exceptions are
the flags that already do one thing: `config --path` prints a path, and
`repos --add` / `--remove` print a confirmation line.

```bash
gitfoot --json | jq '.streak.current'
gitfoot --json | jq -r '.days | to_entries[] | select(.value > 0) | "\(.key)\t\(.value)"'
gitfoot sync --json | jq '.commits_new'
gitfoot repos --json | jq -r '.repositories[] | "\(.commits)\t\(.name)"' | sort -rn | head
gitfoot doctor --json | jq -e 'all(.checks[]; .ok)'
```

Useful in a shell prompt:

```bash
printf 'streak: %s\n' "$(gitfoot --json | jq -r '.streak.current')"
```

Progress output goes to stderr, so pipes stay clean without `-q`.

## Limitations

Honest list, not a roadmap.

- **Squashed and rebased history reads as one day.** If your team squashes
  pull requests, the merge date wins and the days you actually worked vanish.
  Nothing local can recover them.
- **Co-authored commits count once, for the author.** `Co-authored-by` trailers
  are not parsed, so pairing shows up only in the driver's history.
- **Rewritten history leaves orphans.** Commits recorded before a rebase keep
  their rows, because gitfoot never deletes. `--all` re-reads but does not prune.
- **Discovery stops at the first `.git` it finds.** Submodules and vendored
  checkouts inside a project are not counted separately. Nested independent
  repositories are invisible.
- **Discovery is a list, not a heuristic.** Scan depth (6 levels below a root)
  and the skipped directory names are both in `config.toml`, and a repository
  outside those rules is simply not seen. `gitfoot repos` shows what was found,
  which is the fastest way to notice something missing.
- **Author dates, in whatever timezone the machine had at commit time.** Travel
  or a badly set clock will put a commit on the wrong day, and `git commit
  --date` is trusted as given.
- **Empty and unreachable repositories are skipped quietly**; git failures are
  reported per repository at the end of a sync instead of aborting it.

## Development

```bash
pip install -e '.[dev]'
pytest
```

The modules are small and single-purpose: `gitscan` (find repos, read commits),
`store` (SQLite), `stats` (pure date arithmetic), `render` and `term` (output),
`cli` (argparse). Patches that keep the dependency list empty are welcome;
[docs/architecture.md](docs/architecture.md) explains why the data model looks
the way it does before you change it.

More answers, including the awkward ones, in [docs/faq.md](docs/faq.md).

MIT.
