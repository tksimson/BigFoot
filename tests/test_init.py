"""Choosing what to scan, and naming the command that will actually run.

Both are first-run concerns, and both used to be wrong in ways you only notice
after the fact: a y/N over the whole suggested list meant a directory GitFoot
had not heard of could not be tracked at all, and every printed hint assumed a
`gitfoot` on PATH that `uvx` never installs.
"""

from __future__ import annotations

import pytest

from gitfoot import cli, render, term


def plain() -> term.Terminal:
    return term.Terminal(color=False, width=80, unicode=True)


@pytest.fixture
def answering(monkeypatch):
    """Drive the prompt with scripted replies, as a terminal would."""

    def drive(*replies: str):
        monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True, raising=False)
        remaining = iter(replies)
        monkeypatch.setattr("builtins.input", lambda _="": next(remaining))

    return drive


@pytest.fixture
def dirs(tmp_path):
    made = []
    for name in ("dev", "work", "clients"):
        path = tmp_path / name
        path.mkdir()
        made.append(str(path))
    return made


# -- picking directories -------------------------------------------------


def test_enter_accepts_everything_found(answering, dirs):
    answering("")
    entries = [(d, 3) for d in dirs]

    assert cli.ask_roots(entries) == dirs


def test_numbers_pick_a_subset(answering, dirs):
    answering("1 3")
    entries = [(d, 3) for d in dirs]

    assert cli.ask_roots(entries) == [dirs[0], dirs[2]]


def test_commas_separate_as_well_as_spaces(answering, dirs):
    answering("1,2")
    entries = [(d, 3) for d in dirs]

    assert cli.ask_roots(entries) == [dirs[0], dirs[1]]


def test_a_typed_path_is_added(answering, dirs, tmp_path):
    extra = tmp_path / "elsewhere"
    extra.mkdir()
    answering(str(extra))

    assert cli.ask_roots([(d, 3) for d in dirs]) == [str(extra)]


def test_numbers_and_paths_mix_in_one_answer(answering, dirs, tmp_path):
    """The whole point of one prompt: pick some, name others, in one line."""
    extra = tmp_path / "elsewhere"
    extra.mkdir()
    answering(f"2 {extra}")

    assert cli.ask_roots([(d, 3) for d in dirs]) == [dirs[1], str(extra)]


def test_the_same_directory_twice_is_recorded_once(answering, dirs):
    answering(f"1 {dirs[0]}")

    assert cli.ask_roots([(d, 3) for d in dirs]) == [dirs[0]]


# -- refusing what would silently produce nothing ------------------------


def test_a_mistyped_path_is_refused_and_the_question_repeated(answering, dirs, capsys):
    """A typo stored as a root is discovered much later, as a dashboard of zeros."""
    answering("/no/such/place", "1")

    chosen = cli.ask_roots([(d, 3) for d in dirs])

    assert chosen == [dirs[0]]
    assert "no such directory" in capsys.readouterr().err


def test_a_number_outside_the_list_is_refused(answering, dirs, capsys):
    answering("9", "2")

    chosen = cli.ask_roots([(d, 3) for d in dirs])

    assert chosen == [dirs[1]]
    assert "no option numbered 9" in capsys.readouterr().err


def test_a_bad_answer_reports_the_numbers_and_the_paths_apart(answering, dirs, capsys):
    answering("9 /no/such/place", "")

    cli.ask_roots([(d, 3) for d in dirs])

    err = capsys.readouterr().err
    assert "no option numbered 9" in err
    assert "no such directory: /no/such/place" in err


def test_a_file_is_not_a_directory(answering, dirs, tmp_path):
    handle = tmp_path / "notes.txt"
    handle.write_text("x")
    answering(str(handle), "1")

    assert cli.ask_roots([(d, 3) for d in dirs]) == [dirs[0]]


def test_repeated_nonsense_gives_up_rather_than_looping(answering, dirs):
    """Bounded, so a script that keeps answering wrongly cannot spin forever."""
    answering("x", "y", "z")

    assert cli.ask_roots([(d, 3) for d in dirs]) == []


def test_a_redirected_stdin_chooses_nothing(monkeypatch, dirs):
    """Consent cannot be assumed from silence, here as everywhere else."""
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False, raising=False)

    assert cli.ask_roots([(d, 3) for d in dirs]) == []


def test_end_of_input_chooses_nothing(answering, dirs, monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: True, raising=False)

    def refuse(_=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", refuse)

    assert cli.ask_roots([(d, 3) for d in dirs]) == []


# -- naming a command the reader can actually run ------------------------


def test_the_hint_says_uvx_when_gitfoot_is_not_on_path(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)

    assert cli.invocation() == "uvx gitfoot"


def test_the_hint_is_bare_when_gitfoot_is_installed(monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: "/usr/bin/gitfoot")

    assert cli.invocation() == "gitfoot"


@pytest.mark.parametrize("prefix", ["gitfoot", "uvx gitfoot"])
def test_first_run_prints_the_prefix_it_was_given(prefix):
    assert f"{prefix} init" in render.first_run(plain(), configured=False, prefix=prefix)
    assert f"{prefix} sync" in render.first_run(plain(), configured=True, prefix=prefix)


# -- showing enough to decide on -----------------------------------------


def test_the_offer_numbers_each_directory_and_counts_its_repositories():
    out = render.init_roots(plain(), [("~/dev", 10), ("~/work", 3)])

    assert "1  ~/dev" in out
    assert "10 repos" in out
    assert "2  ~/work" in out
    assert "3 repos" in out


def test_one_repository_is_not_pluralised():
    assert "1 repo" in render.init_roots(plain(), [("~/dev", 1)])
    assert "1 repos" not in render.init_roots(plain(), [("~/dev", 1)])


def test_an_empty_directory_is_shown_as_empty_rather_than_hidden():
    """Worth offering: seeing 0 is how you know not to pick it."""
    assert "0 repos" in render.init_roots(plain(), [("~/Documents/GitHub", 0)])


@pytest.mark.parametrize("width", [24, 30, 40, 60, 80, 120, 200])
@pytest.mark.parametrize("count", [1, 2, 9, 10, 40])
def test_the_offer_fits_the_terminal_it_is_printed_on(width, count):
    """A long path must lose its head, never run through the count column.

    Measured against the terminal's effective width, since anything below
    ``MIN_WIDTH`` is clamped and rendering to it is not a thing that happens.
    """
    narrow = term.Terminal(color=False, width=width, unicode=True)
    entries = [(f"~/very/long/path/to/projects/number/{n}", n * 1000) for n in range(count)]

    out = render.init_roots(narrow, entries)

    assert all(term.visible_len(line) <= narrow.width for line in out.splitlines())


def test_a_long_path_keeps_its_leaf_where_the_meaning_is():
    narrow = term.Terminal(color=False, width=44, unicode=True)

    out = render.init_roots(narrow, [("~/a/very/long/way/down/to/clients", 7)])

    assert "clients" in out
