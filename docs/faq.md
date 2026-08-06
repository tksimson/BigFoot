# FAQ

## Isn't commit count a terrible metric?

Yes, as a measure of productivity it is one of the worst available. It rewards
noise, punishes thinking, and can be gamed by anyone with a keyboard. If a
manager ever points this tool at a team, that is misuse and the output will
deserve everything said about it.

gitfoot measures attendance, not output. Did you open the editor today. How
long is the current run. That question has a real answer, and for people
working alone on something long it is the question that matters, because the
failure mode of a ten-year project is not writing bad code. It is quietly
stopping.

There is no score, no ranking, no target, and no comparison against anyone
else. The number that means the most on the dashboard is the streak, and the
streak only asks whether you showed up.

## Does it phone home?

No. There is no network code in the package: no telemetry, no update check, no
crash reporting, no account, no key. The imports are stdlib only.

```bash
grep -rnE '^\s*(import|from) ' gitfoot/ | grep -E 'urllib|http|socket|ssl|requests'
```

Comes back empty. The only external program it runs is `git`, always with
`cwd` set to a repository you configured, always read-only: `git log`,
`git config --get`, `git remote`, `git --version`.

## Why does it need access to my home directory?

It doesn't, and it will not touch it unless you say so.

`gitfoot init` offers a list of directories that commonly hold projects
(`~/dev`, `~/code`, `~/src`, `~/projects`, `~/work`, `~/repos`, `~/git`,
`~/Documents/GitHub`), shows you the ones that actually exist, and waits for a
yes. Nothing is scanned before that. If you would rather be exact:

```bash
gitfoot init --root ~/dev/mine --email me@example.com -y
```

Scanning `~` directly works but is a bad idea: it is slow and it picks up every
dependency checkout on the machine. Point it at where your work lives.

What gets read from a repository: commit SHA, author date, author email, and
per-file insertion/deletion counts. Not commit messages, not file names, not
file contents, not branch names, not remotes beyond the URL used as an identity
key.

## What about merge commits?

Excluded, via `--no-merges`. A merge records an integration, not a day's work,
and `git log --numstat` reports no line counts for one anyway. If your workflow
is merge-heavy this makes your numbers lower and more honest.

## What about rebases?

A rebase rewrites SHAs, so rebased commits look new and get inserted again. The
old rows stay, because gitfoot never deletes. In practice this inflates a total
slightly and leaves the day distribution roughly intact, since the author date
survives a rebase (the committer date is what changes, and gitfoot uses the
author date).

If it bothers you, delete the database and run `gitfoot sync --all`. There is
no pruning pass, and I would rather say that plainly than pretend the number is
exact.

## What about squashed pull requests?

This is the real limitation, and it cannot be fixed locally.

If your team squashes on merge, twelve days of work collapse into one commit
dated the day it landed. The eleven days you actually worked leave no trace in
the repository, so nothing that reads the repository can recover them. On a
squash-merge team the dashboard will understate you, badly.

Nothing works around this. Local feature branches help while they exist,
because `--all` scans every ref, so your unsquashed work counts until the branch
is deleted. After that it is gone.

## What about co-authored commits?

Counted once, for the author. `Co-authored-by:` trailers are in the commit
message body, which gitfoot does not read, so pairing shows up only in the
driver's history. If you pair heavily and take the passenger seat often, the
dashboard will understate you.

`--numstat` line counts are also for the whole commit, so a pair's diff lands
entirely on the author.

## Why not just use GitHub's contribution graph?

Use it if it covers your work. Four reasons this exists:

- **It only knows GitHub.** Work on GitLab, a self-hosted Gitea, a client's
  Bitbucket, or a repository that never leaves your laptop is invisible there.
  gitfoot reads whatever is on your disk.
- **Private and unpushed work.** Commits sitting on a local branch you have not
  pushed count here and appear nowhere else.
- **It is on the internet.** The graph is a public artefact with an audience,
  which is exactly the thing that turns attendance into performance.
- **It is not scriptable.** `gitfoot --json | jq` is.

The costs are honest too: no cross-machine sync, no issues, no reviews, no PR
activity. GitHub's graph counts things gitfoot cannot see.

## Does it work with worktrees?

Yes. A linked worktree has a `.git` file rather than a directory, which
discovery accepts, and it shares config with its main checkout, so it resolves
to the same remote key and collapses into one entry. Commits are not
double counted, and because `--all` reads the shared object store nothing is
lost either.

## Does it work with submodules?

Not as separate repositories. Descent stops at the first `.git` found on a
branch, so a submodule inside a checked-out project is never walked into. Your
commits to that submodule are not counted unless it is also cloned somewhere
else under a scan root.

This is deliberate: the common case is a vendored dependency you did not write.
The uncommon case, a submodule you actively develop, is served by adding its
standalone clone as a root.

## Does it work with monorepos?

Yes, and nothing special happens. A monorepo is one repository with one
history, so it shows up as one entry with all your commits in it. There is no
per-directory or per-package breakdown, and no plans for one.

## Does it work with non-GitHub remotes?

Yes. Remote normalisation handles SCP-style (`git@host:owner/repo.git`) and any
URL scheme (`https://`, `ssh://`, `git://`), so GitLab, Bitbucket, Gitea,
Codeberg, Gerrit and self-hosted git all key correctly. A remote that is a
plain local path is keyed by that path, which is still stable.

A repository with no remote at all is keyed by its resolved filesystem path.
That works, with one consequence: move the directory and it counts as a new
repository, and the old rows keep their history under the old path.

## Does it find bare repositories?

No. Discovery looks for a `.git` entry inside a directory, which a bare repo
does not have. Bare mirrors are usually not where you work, so this has not
been worth solving.

## How large does the database get?

One row per commit, roughly 100 bytes. Ten thousand commits is about a
megabyte. It is a single SQLite file you can copy, back up, inspect with
`sqlite3`, or delete.

## How long does a sync take?

One `git log` per repository, eight in parallel. Discovery is a pruned
filesystem walk. Forty repositories on an SSD is a couple of seconds; the first
`--all` run over years of history is longer. Incremental syncs read only the
last week plus whatever is new.

Slow syncs almost always mean discovery is walking too much. Check
`gitfoot repos` for entries you did not expect, then narrow your roots or add
directory names to `ignore_dirs` in `config.toml`.

## Can I run it automatically?

Yes. `gitfoot sync -q` prints only errors and writes progress to stderr, which
makes it fine in cron, a systemd timer, or a shell hook. Concurrent syncs
against one database are not supported; SQLite will serialise or error rather
than corrupt anything, but do not schedule two at once.

## What if my email changed?

Add both:

```bash
gitfoot config --add-email old@example.com
gitfoot sync --all
```

The list only grows through this command and `init --email`. It is never
inferred from commit history, because that is precisely how the 0.x version
ended up counting other people's work as yours.

## Are the dates right?

They are author dates, in whatever timezone the machine had when the commit was
made, truncated to a day. Cross a timezone and a late-night commit can land on
the neighbouring day. `git commit --date` is trusted as given. For a tool about
whether you showed up, that is close enough; for anything requiring precision,
it is not.

## Can the numbers be faked?

Yes, trivially, and it is worth being clear about how.

Attribution is author-email equality and nothing else. Author email and author
date are both chosen freely by whoever makes a commit, and both survive a clone.
So a repository on your disk can contain commits authored as you, on any date,
and gitfoot will count them. Clone something hostile into a scanned directory
and your streak is whatever its author decided.

Two dates that are obviously not real are refused: anything that is not a valid
`YYYY-MM-DD`, and anything more than a year ahead or a century behind. That is
there so a nonsense date cannot break the tool, not to stop forgery. It cannot
stop forgery, because a plausible date is indistinguishable from a real one.

This is not a defect that can be fixed locally. Signed commits would let a tool
verify authorship, but almost nobody signs, and a tool that counted only signed
commits would report zero for most people. So: gitfoot is a mirror you point at
yourself. It is not evidence, and it should never be treated as evidence about
anybody, including you.

The one thing it does guarantee is that it will not quietly credit you with
someone else's work. Identity is the list you confirmed at `gitfoot init`, and
nothing gets added to it without you saying so.

## How do I remove it?

```bash
pipx uninstall gitfoot
rm -rf ~/.local/share/gitfoot ~/.config/gitfoot
```

Those two directories are all of it. Nothing is written anywhere else, and
nothing is written inside your repositories.

## Why Python 3.11?

`tomllib` landed in 3.11, and config is TOML. Supporting older versions means
either a `tomli` dependency or a hand-rolled parser, and the zero-dependency
install is worth more than the compatibility.

## Windows? macOS?

macOS and Linux are what it is used on daily. The code is `pathlib`,
`subprocess` and `sqlite3` with no platform-specific calls, so Windows should
work; XDG variables fall back to `~/.config` and `~/.local/share` there, which
is not the Windows convention. `GITFOOT_HOME` sets both explicitly. Reports
welcome.
