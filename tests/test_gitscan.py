"""Discovery, repository identity, and commit attribution.

Attribution is the reason this rewrite exists. The previous version collected
every author email seen in recent history and used that set as its "filter", so
in any shared repository a colleague's commits were counted as the user's own.
The tests below pin the opposite behaviour: only configured emails count, and an
empty set of configured emails counts nothing at all.
"""

from __future__ import annotations

import threading

import pytest
from conftest import COLLEAGUE, ME, plain_dir

from gitfoot import gitscan
from gitfoot.gitscan import FIELD_SEP, RECORD_SEP

# -- attribution ---------------------------------------------------------


def read(repo, emails, since=None):
    return gitscan.read_commits(repo.found(), emails, since)


def test_only_configured_emails_are_counted(repo):
    mine = [
        repo.commit("2026-07-01", ME, files={"a.txt": "1\n"}),
        repo.commit("2026-07-02", ME, files={"a.txt": "1\n2\n"}),
    ]
    repo.commit("2026-07-01", COLLEAGUE, files={"b.txt": "x\n"})
    repo.commit("2026-07-03", COLLEAGUE, files={"b.txt": "x\ny\n"})

    result = read(repo, {ME})

    assert result.error is None
    assert sorted(c.sha for c in result.commits) == sorted(mine)
    assert {c.email for c in result.commits} == {ME}


def test_an_empty_email_set_matches_nothing_rather_than_everything(repo):
    repo.commit("2026-07-01", ME, files={"a.txt": "1\n"})
    repo.commit("2026-07-01", COLLEAGUE, files={"b.txt": "x\n"})

    assert read(repo, set()).commits == []
    assert list(gitscan.parse_log(f"{RECORD_SEP}abc{FIELD_SEP}2026-07-01{FIELD_SEP}{ME}", set())) == []


def test_email_matching_ignores_case_in_both_directions(repo):
    upper = repo.commit("2026-07-01", "ME@Example.COM", files={"a.txt": "1\n"})
    lower = repo.commit("2026-07-02", "me@example.com", files={"a.txt": "1\n2\n"})

    from_lower_config = read(repo, {"me@example.com"}).commits
    from_upper_config = read(repo, {"Me@EXAMPLE.com"}).commits

    assert sorted(c.sha for c in from_lower_config) == sorted([upper, lower])
    assert sorted(c.sha for c in from_upper_config) == sorted([upper, lower])


def test_a_near_miss_email_is_not_counted(repo):
    repo.commit("2026-07-01", "me@example.com.br", files={"a.txt": "1\n"})
    repo.commit("2026-07-01", "notme@example.com", files={"b.txt": "1\n"})

    assert read(repo, {ME}).commits == []


def test_merge_commits_are_excluded(repo):
    first = repo.commit("2026-07-01", ME, files={"a.txt": "1\n"})
    repo.branch("feature")
    branch_work = repo.commit("2026-07-02", ME, files={"feature.txt": "f\n"})
    repo.checkout("main")
    trunk_work = repo.commit("2026-07-02", ME, files={"trunk.txt": "t\n"})
    merge_sha = repo.merge("feature", "2026-07-03")

    shas = {c.sha for c in read(repo, {ME}).commits}

    assert shas == {first, branch_work, trunk_work}
    assert merge_sha not in shas


def test_commits_on_unmerged_branches_still_count(repo):
    trunk = repo.commit("2026-07-01", ME, files={"a.txt": "1\n"})
    repo.branch("side")
    side = repo.commit("2026-07-02", ME, files={"side.txt": "s\n"})
    repo.checkout("main")

    assert {c.sha for c in read(repo, {ME}).commits} == {trunk, side}


def test_binary_files_count_as_files_but_contribute_no_line_counts(repo):
    repo.commit(
        "2026-07-01",
        ME,
        files={"text.txt": "a\nb\nc\n"},
        binary={"blob.bin": b"\x00\x01\x02\xff\xfe"},
    )

    (only,) = read(repo, {ME}).commits

    assert only.files == 2
    assert only.insertions == 3
    assert only.deletions == 0


def test_commit_messages_containing_separators_do_not_break_parsing(repo):
    nasty = f"subject\twith tab\nbody | pipe {RECORD_SEP} record {FIELD_SEP} field\n"
    sha = repo.commit("2026-07-01", ME, files={"a.txt": "1\n"}, message=nasty)

    commits = read(repo, {ME}).commits

    assert [c.sha for c in commits] == [sha]
    assert commits[0].day == "2026-07-01"
    assert commits[0].insertions == 1


def test_the_recorded_day_is_the_author_date(repo):
    repo.commit("2026-02-11", ME, files={"a.txt": "1\n"})

    (only,) = read(repo, {ME}).commits

    assert only.day == "2026-02-11"


def test_line_counts_are_summed_across_the_files_of_one_commit(repo):
    repo.commit("2026-07-01", ME, files={"a.txt": "1\n2\n3\n", "b.txt": "x\ny\n"})
    repo.commit("2026-07-02", ME, files={"a.txt": "1\n", "b.txt": "x\ny\nz\n"})

    latest = max(read(repo, {ME}).commits, key=lambda c: c.day)

    assert latest.files == 2
    assert latest.insertions == 1  # one line added to b.txt
    assert latest.deletions == 2  # two lines removed from a.txt


def test_an_empty_commit_is_recorded_with_zero_changes(repo):
    repo.commit("2026-07-01", ME, message="empty", allow_empty=True)

    (only,) = read(repo, {ME}).commits

    assert (only.files, only.insertions, only.deletions) == (0, 0, 0)


def test_since_limits_how_far_back_history_is_read(repo):
    repo.commit("2026-01-05", ME, files={"a.txt": "1\n"})
    recent = repo.commit("2026-07-05", ME, files={"a.txt": "1\n2\n"})

    result = read(repo, {ME}, since="2026-06-01")

    assert [c.sha for c in result.commits] == [recent]


def test_an_empty_repository_is_not_an_error(repo):
    result = read(repo, {ME})

    assert result.error is None
    assert result.commits == []


def test_a_directory_that_is_not_a_repository_is_reported_not_raised(tmp_path):
    result = gitscan.read_commits(plain_dir(tmp_path / "not-a-repo"), {ME})

    assert result.commits == []
    assert result.error  # a message, not an exception


def test_a_missing_directory_is_reported_not_raised(tmp_path):
    ghost = gitscan.Found(path=tmp_path / "gone", key="path:gone", name="gone")

    result = gitscan.read_commits(ghost, {ME})

    assert result.commits == []
    assert result.error


# -- parse_log, without a repository -------------------------------------


def record(sha: str, day: str, email: str, body: str = "") -> str:
    head = f"{RECORD_SEP}{sha}{FIELD_SEP}{day}{FIELD_SEP}{email}"
    return head + ("\n" + body if body else "")


def test_parse_log_skips_records_whose_header_is_malformed():
    good = record("aaa", "2026-07-01", ME, "1\t0\ta.txt")
    truncated = f"{RECORD_SEP}bbb{FIELD_SEP}2026-07-01"  # missing the email field
    extra = f"{RECORD_SEP}ccc{FIELD_SEP}2026-07-01{FIELD_SEP}{ME}{FIELD_SEP}surplus"

    parsed = list(gitscan.parse_log(good + truncated + extra, {ME}))

    assert [c.sha for c in parsed] == ["aaa"]


def test_parse_log_ignores_body_lines_that_are_not_numstat():
    body = "\n".join(["", "not a numstat line", "3\t1\tsrc/app.py", ""])

    (only,) = gitscan.parse_log(record("aaa", "2026-07-01", ME, body), {ME})

    assert (only.files, only.insertions, only.deletions) == (1, 3, 1)


def test_parse_log_handles_paths_containing_tabs():
    body = "2\t1\tdir/odd\tname.txt"

    (only,) = gitscan.parse_log(record("aaa", "2026-07-01", ME, body), {ME})

    assert (only.files, only.insertions, only.deletions) == (1, 2, 1)


def test_parse_log_of_empty_output_yields_nothing():
    assert list(gitscan.parse_log("", {ME})) == []
    assert list(gitscan.parse_log("\n\n", {ME})) == []


# -- repository identity -------------------------------------------------

EQUIVALENT_REMOTES = [
    "git@github.com:tksimson/GitFoot.git",
    "git@github.com:tksimson/GitFoot",
    "GIT@GitHub.com:tksimson/GitFoot.git",
    "https://github.com/tksimson/GitFoot",
    "https://github.com/tksimson/GitFoot.git",
    "https://github.com/tksimson/GitFoot/",
    "https://github.com/tksimson/GitFoot.git/",
    "ssh://git@github.com/tksimson/GitFoot.git",
    "ssh://git@github.com:22/tksimson/GitFoot.git",
    "git://github.com/tksimson/GitFoot.git",
    "https://tksimson:token@github.com/tksimson/GitFoot.git",
    "  https://github.com/tksimson/GitFoot.git  ",
]


@pytest.mark.parametrize("url", EQUIVALENT_REMOTES)
def test_every_url_form_of_one_remote_gives_one_key(url):
    # The whole key is lowercased, not just the host: two remotes for one
    # project differing only in capitalisation is common, two different
    # projects differing only in capitalisation is not.
    assert gitscan.normalize_remote(url) == "github.com/tksimson/gitfoot"


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/tksimson/GitFoot.git",  # different host
        "git@github.com:someone-else/GitFoot.git",  # different owner
        "git@github.com:tksimson/OtherProject.git",  # different repo
    ],
)
def test_different_hosts_owners_or_names_give_different_keys(url):
    assert gitscan.normalize_remote(url) != "github.com/tksimson/GitFoot"


def test_a_local_path_remote_is_keyed_by_that_path():
    assert gitscan.normalize_remote("/srv/git/api.git").startswith("path:")
    assert gitscan.normalize_remote("../sibling/api") != gitscan.normalize_remote("/srv/git/api.git")


def test_two_clones_of_one_project_collapse_to_a_single_repository(tmp_path, make_repo):
    make_repo("clone-a", remote="git@github.com:acme/api.git")
    make_repo("clone-b", remote="https://github.com/acme/api")

    found = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=4)

    assert len(found) == 1


def test_a_repository_without_a_remote_is_keyed_by_its_path(make_repo):
    repo = make_repo("solo")

    identity = repo.found()

    assert identity.key == f"path:{repo.path}"
    assert identity.name == "solo"


def test_same_named_repositories_in_different_directories_stay_separate(tmp_path, make_repo):
    make_repo("api", parent=tmp_path / "work")
    make_repo("api", parent=tmp_path / "personal")

    found = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=4)

    assert [f.name for f in found] == ["api", "api"]
    assert len({f.key for f in found}) == 2


def test_a_repository_is_named_after_its_remote_not_its_directory(make_repo):
    repo = make_repo("checkout-dir", remote="git@github.com:acme/payments.git")

    assert repo.found().name == "payments"


def test_identify_returns_nothing_for_a_plain_directory(tmp_path):
    (tmp_path / "plain").mkdir()

    assert gitscan._identify(tmp_path / "plain") is None


# -- discovery -----------------------------------------------------------


def test_descent_stops_at_a_repository_boundary(tmp_path, make_repo):
    project = make_repo("project")
    make_repo("lib", parent=project.path / "vendor")

    found = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=6)

    assert [f.name for f in found] == ["project"]


def test_ignored_directory_names_are_never_descended_into(tmp_path, make_repo):
    make_repo("pkg", parent=tmp_path / "node_modules")
    make_repo("real")

    ignored = gitscan.discover([tmp_path], ignore_dirs=["node_modules"], max_depth=6)
    unfiltered = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=6)

    assert [f.name for f in ignored] == ["real"]
    assert {f.name for f in unfiltered} == {"real", "pkg"}


def test_ignored_directory_names_are_matched_case_insensitively(tmp_path, make_repo):
    make_repo("pkg", parent=tmp_path / "node_modules")

    assert gitscan.discover([tmp_path], ignore_dirs=["NODE_MODULES"], max_depth=6) == []


@pytest.mark.parametrize(
    ("max_depth", "expected"),
    [(1, []), (2, []), (3, ["deep"]), (6, ["deep"])],
)
def test_max_depth_bounds_how_far_below_a_root_repositories_are_found(
    tmp_path, make_repo, max_depth, expected
):
    make_repo("deep", parent=tmp_path / "a" / "b")

    found = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=max_depth)

    assert [f.name for f in found] == expected


def test_a_root_that_is_itself_a_repository_is_found(tmp_path, make_repo):
    repo = make_repo("self")

    found = gitscan.discover([repo.path], ignore_dirs=[], max_depth=6)

    assert [f.name for f in found] == ["self"]


def test_a_root_nested_inside_another_root_is_not_walked_twice(tmp_path, make_repo):
    make_repo("inner", parent=tmp_path / "dev")

    kept = gitscan._outermost([tmp_path / "dev", tmp_path])
    found = gitscan.discover([tmp_path, tmp_path / "dev"], ignore_dirs=[], max_depth=6)

    assert kept == [tmp_path.resolve()]
    assert [f.name for f in found] == ["inner"]


def test_a_nonexistent_root_is_skipped_rather_than_fatal(tmp_path, make_repo):
    make_repo("real")

    found = gitscan.discover(
        [tmp_path / "does-not-exist", tmp_path], ignore_dirs=[], max_depth=6
    )

    assert [f.name for f in found] == ["real"]
    assert gitscan._outermost([tmp_path / "nope"]) == []


def test_a_file_given_as_a_root_is_skipped(tmp_path):
    target = tmp_path / "a-file"
    target.write_text("not a directory")

    assert gitscan._outermost([target]) == []


def test_a_symlink_loop_does_not_hang_discovery(tmp_path, make_repo):
    make_repo("real")
    loop_dir = tmp_path / "loop"
    loop_dir.mkdir()
    (loop_dir / "back").symlink_to(tmp_path, target_is_directory=True)

    result: list[list] = []
    worker = threading.Thread(
        target=lambda: result.append(
            gitscan.discover([tmp_path], ignore_dirs=[], max_depth=6)
        ),
        daemon=True,
    )
    worker.start()
    worker.join(timeout=15)

    assert not worker.is_alive(), "discover() did not terminate on a symlink loop"
    assert [f.name for f in result[0]] == ["real"]


def test_discovery_results_are_sorted_by_name(tmp_path, make_repo):
    for name in ("zebra", "Alpha", "middle"):
        make_repo(name)

    found = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=6)

    assert [f.name for f in found] == ["Alpha", "middle", "zebra"]


# -- reading many repositories -------------------------------------------


def test_read_all_returns_one_result_per_repository(tmp_path, make_repo):
    first = make_repo("one")
    first.commit("2026-07-01", ME, files={"a.txt": "1\n"})
    second = make_repo("two")
    second.commit("2026-07-02", COLLEAGUE, files={"b.txt": "1\n"})

    repos = gitscan.discover([tmp_path], ignore_dirs=[], max_depth=6)
    results = gitscan.read_all(repos, {ME}, since_for=lambda _: None)

    assert len(results) == 2
    assert sum(len(r.commits) for r in results) == 1


def test_read_all_of_no_repositories_is_empty():
    assert gitscan.read_all([], {ME}, since_for=lambda _: None) == []


# -- author_counts: offered during init, never used as a filter ----------


def test_author_counts_ranks_every_author_most_prolific_first(tmp_path, make_repo):
    repo = make_repo("shared")
    for day in ("2026-07-01", "2026-07-02", "2026-07-03"):
        repo.commit(day, COLLEAGUE, files={"b.txt": day})
    repo.commit("2026-07-04", ME, files={"a.txt": "1\n"})

    counts = gitscan.author_counts(gitscan.discover([tmp_path], [], 4))

    assert counts == [(COLLEAGUE, 3), (ME, 1)]


def test_author_counts_folds_case_variants_of_one_address_together(tmp_path, make_repo):
    repo = make_repo("shared")
    repo.commit("2026-07-01", "Me@Example.COM", files={"a.txt": "1\n"})
    repo.commit("2026-07-02", "me@example.com", files={"a.txt": "1\n2\n"})

    counts = gitscan.author_counts(gitscan.discover([tmp_path], [], 4))

    assert counts == [(ME, 2)]


def test_author_counts_never_decides_attribution_on_its_own(tmp_path, make_repo):
    """Seeing an address is not the same as owning it: reading still filters."""
    repo = make_repo("shared")
    repo.commit("2026-07-01", COLLEAGUE, files={"b.txt": "x\n"})

    seen = gitscan.author_counts(gitscan.discover([tmp_path], [], 4))

    assert seen == [(COLLEAGUE, 1)]
    assert read(repo, {ME}).commits == []


def test_author_counts_of_no_repositories_is_empty():
    assert gitscan.author_counts([]) == []
