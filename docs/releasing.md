# Releasing

PyPI accepts a version exactly once. A version that has been uploaded cannot be
replaced, and cannot be re-uploaded even after being deleted. So the cost of a
mistake here is a burnt version number, not a retry. Everything below exists to
make that hard to do by accident.

## The two things that go wrong

**A stale version.** `gitfoot/__init__.py` holds the number; `pyproject.toml`
reads it from there via `[tool.hatch.version]`. Forgetting to bump it means
`uv publish` tries to upload a version that already exists and is refused.

**A stale `dist/`.** `uv build` does *not* empty the directory first, and
`uv publish` uploads **everything it finds there**. Old artifacts from a
previous release will be offered again, and the upload fails on them. Always
`rm -rf dist` first.

`tests/test_version.py` catches the first. The `rm -rf` in the recipe below
catches the second.

## Recipe

```bash
# 1. Choose the number. MAJOR.MINOR.PATCH, semver:
#      patch  a fix, nothing new
#      minor  new behaviour, old invocations still work
#      major  something that used to work no longer does
$EDITOR gitfoot/__init__.py     # __version__ = "1.2.0"

# 2. Move CHANGELOG's [Unreleased] entries under a dated heading:
#      ## [1.2.0] - YYYY-MM-DD
$EDITOR CHANGELOG.md

# 3. The suite refuses to pass if those two disagree.
python3 -m pytest

# 4. Build clean. The rm is not optional.
rm -rf dist && uv build

# 5. Look at what you are about to publish.
ls dist/                        # exactly two files, both the new version
uvx twine check dist/*

# 6. Publish. Username __token__, password the pypi- token.
uv publish

# 7. Prove it from the outside, the way a stranger would.
uvx gitfoot@latest --version
```

Then commit, tag, and push:

```bash
git commit -am "Release 1.2.0"
git tag -a v1.2.0 -m "1.2.0"
git push origin main --tags
```

## Tokens

The first upload of a project needs an account-scoped token, because a
project-scoped one cannot exist before the project does. After that, mint a
token scoped to `gitfoot` alone and delete the account-wide one: it limits a
leaked token to this package instead of everything you own.

- Project token: <https://pypi.org/manage/project/gitfoot/settings/>
- Account tokens: <https://pypi.org/manage/account/token/>

Prefer the interactive prompt over `UV_PUBLISH_TOKEN=...`, which puts the token
in your shell history.

## If you get it wrong

You cannot overwrite. Bump the patch number and publish again; the bad version
can be yanked afterwards.

```bash
# Yank hides a release from resolvers without breaking anyone who pinned it.
# There is no CLI for it: https://pypi.org/manage/project/gitfoot/releases/
```

Deleting a release does **not** free its version number for reuse.
