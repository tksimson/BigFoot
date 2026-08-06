"""Output: layout arithmetic, capability fallbacks, and the end-to-end CLI.

The dashboard is the product. Most of what can go wrong with it is arithmetic
that no exception will ever report: a line two characters too wide, a month
label one column out, an escape sequence left open at the end of a row. These
tests read the text the way a terminal would.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from datetime import date, timedelta

import pytest
from conftest import ME

from gitfoot import cli, render, stats, term
from gitfoot.store import Commit, Store

TODAY = date(2026, 8, 5)  # a Wednesday


@pytest.fixture
def snapshot(tmp_path):
    """A realistic year: several repositories, weekends quieter, gaps."""
    store = Store(tmp_path / "b.db")
    repos = [store.upsert_repo(f"k{i}", n, f"/w/{n}") for i, n in enumerate(("api", "web", "notes"))]
    n = 0
    for offset in range(360):
        day = TODAY - timedelta(days=offset)
        for _ in range((offset * 7) % 5):
            n += 1
            store.add_commits(
                repos[n % 3],
                [Commit(f"{n:040x}", day.isoformat(), ME, n % 40, n % 9, 1)],
            )
    return stats.snapshot(store, weeks=52, today=TODAY)


def plain(width: int = 80) -> term.Terminal:
    return term.Terminal(color=False, unicode=True, width=width, stream=io.StringIO())


# -- layout arithmetic ---------------------------------------------------


@pytest.mark.parametrize("width", [40, 46, 55, 60, 72, 80, 100, 200])
@pytest.mark.parametrize("weeks", [1, 4, 13, 26, 52, 104])
def test_no_line_is_wider_than_the_terminal(snapshot, width, weeks):
    out = render.dashboard(snapshot, plain(width), weeks=weeks)

    too_wide = [ln for ln in out.splitlines() if term.visible_len(ln) > width]
    assert too_wide == []


@pytest.mark.parametrize("width", [40, 60, 80, 120])
def test_no_line_carries_trailing_whitespace(snapshot, width):
    out = render.dashboard(snapshot, plain(width), weeks=26)

    assert [ln for ln in out.splitlines() if ln != ln.rstrip()] == []


def test_the_calendar_always_has_seven_weekday_rows(snapshot):
    out = render.heatmap(snapshot.grid, plain(80), weeks=26)

    # A month label row, then one row per weekday whether or not it is labelled.
    assert len(out.splitlines()) == 8


def test_month_labels_sit_above_the_week_they_name(snapshot):
    term_ = plain(100)
    lines = render.heatmap(snapshot.grid, term_, weeks=26).splitlines()
    labels, first_row = lines[0], lines[1]

    # Both rows start at the same origin, so a label's column index is the
    # offset of the week it belongs to. Off-by-one here is the single most
    # common way a terminal heatmap looks amateurish.
    assert labels.startswith(" " * render.GRID_ORIGIN)
    assert first_row.startswith(" " * len(render.INDENT))
    assert term.visible_len(labels) <= term.visible_len(first_row) + render.MONTH_OVERHANG


def test_the_current_month_is_labelled(snapshot):
    """It overflows the last column, and was being dropped for that reason."""
    labels = render.heatmap(snapshot.grid, plain(100), weeks=52).splitlines()[0]

    assert TODAY.strftime("%b") in labels


def test_totals_describe_the_window_that_is_drawn(snapshot):
    wide = render.legend(snapshot, plain(100), weeks=52)
    narrow = render.legend(snapshot, plain(100), weeks=4)

    assert "52 weeks" in wide and "4 weeks" in narrow
    assert _first_number(wide) > _first_number(narrow)


def _first_number(text: str) -> int:
    for word in text.replace(",", "").split():
        if word.isdigit():
            return int(word)
    raise AssertionError(f"no number in {text!r}")


# -- capability fallbacks ------------------------------------------------


def test_colour_off_emits_no_escape_sequences(snapshot):
    out = render.dashboard(snapshot, plain(80), weeks=26)

    assert "\x1b" not in out


def test_colour_on_closes_every_sequence_it_opens(snapshot):
    """An unbalanced escape leaves the user's shell painted after the command."""
    coloured = term.Terminal(color=True, depth=term.Depth.TRUECOLOR, width=80, stream=io.StringIO())

    out = render.dashboard(snapshot, coloured, weeks=26)

    opens = out.count("\x1b[") - out.count(term.RESET)
    assert opens == out.count(term.RESET), "styling opened and closed an unequal number of times"
    for line in out.splitlines():
        assert "\x1b" not in line or line.endswith(term.RESET) or term.RESET in line


def test_ascii_mode_emits_no_characters_the_terminal_cannot_encode(snapshot):
    ascii_term = term.Terminal(color=False, unicode=False, width=80, stream=io.StringIO())

    out = render.dashboard(ascii_term and snapshot, ascii_term, weeks=26)

    out.encode("ascii")  # raises if a single non-ASCII glyph slipped through


def test_no_color_env_beats_force_color():
    both = {"NO_COLOR": "1", "FORCE_COLOR": "1", "TERM": "xterm-256color"}

    assert term.Terminal(env=both, stream=io.StringIO()).color is False


def test_an_explicit_choice_beats_the_environment():
    hostile = {"NO_COLOR": "1"}

    assert term.Terminal(color=True, env=hostile, stream=io.StringIO()).color is True


def test_visible_len_ignores_styling():
    styled = term.Terminal(color=True, depth=term.Depth.ANSI256, stream=io.StringIO())

    painted = styled.style("hello", styled.theme.added, dim=True)

    assert painted != "hello"
    assert term.visible_len(painted) == 5


def test_padding_is_measured_in_visible_columns():
    styled = term.Terminal(color=True, depth=term.Depth.ANSI16, width=80, stream=io.StringIO())
    painted = styled.style("ab", styled.theme.added)

    assert term.visible_len(styled.ljust(painted, 10)) == 10
    assert term.visible_len(styled.rjust(painted, 10)) == 10


# -- empty states --------------------------------------------------------


def test_an_unconfigured_install_is_told_to_run_init():
    assert "gitfoot init" in render.first_run(plain(), configured=False)


def test_a_configured_but_empty_install_is_told_to_sync():
    assert "gitfoot sync" in render.first_run(plain(), configured=True)


# -- the CLI, run as a subprocess ----------------------------------------


def run(*args: str, home, expect: int | None = 0, stdin: str = "") -> str:
    """Invoke gitfoot the way a user does, in its own process."""
    result = subprocess.run(
        [sys.executable, "-m", "gitfoot", *args],
        capture_output=True,
        text=True,
        input=stdin,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(home),
            "GITFOOT_HOME": str(home / "gitfoot"),
            "COLUMNS": "80",
            "NO_COLOR": "1",
            "PYTHONPATH": str(__import__("pathlib").Path(__file__).resolve().parent.parent),
        },
    )
    if expect is not None:
        assert result.returncode == expect, f"exit {result.returncode}: {result.stderr}"
    return result.stdout


def test_the_dashboard_of_an_unconfigured_install_explains_itself(tmp_path):
    assert "gitfoot init" in run(home=tmp_path)


def test_sync_without_configuration_fails_rather_than_guessing(tmp_path):
    run("sync", home=tmp_path, expect=1)


def test_init_without_a_terminal_refuses_to_assume_consent(tmp_path):
    """Redirected stdin is not a yes. This backs the promise in the README."""
    (tmp_path / "dev").mkdir()

    run("init", home=tmp_path, expect=1)

    assert not (tmp_path / "gitfoot" / "config.toml").exists()


def test_a_full_run_reports_consistent_figures(tmp_path, make_repo):
    repo = make_repo("solo", remote="git@github.com:me/solo.git")
    repo.commit("2026-08-03", ME, files={"a.txt": "1\n"})
    repo.commit("2026-08-04", ME, files={"a.txt": "1\n2\n"})

    run("init", "--root", str(repo.path.parent), "--email", ME, "-y", home=tmp_path)
    payload = json.loads(run("--json", home=tmp_path))

    assert payload["streak"]["longest"] >= 2
    assert sum(payload["days"].values()) == 2
    assert payload["repositories"] == 1


def test_init_records_the_full_history_it_claims_to(tmp_path, make_repo):
    """`--all` used to be expressed as `--since=1970-01-01`, which git rejects
    in any timezone ahead of UTC: init reported success having read nothing."""
    repo = make_repo("solo", remote="git@github.com:me/solo.git")
    repo.commit("2020-03-01", ME, files={"a.txt": "1\n"})
    repo.commit("2026-08-03", ME, files={"a.txt": "1\n2\n"})

    run("init", "--root", str(repo.path.parent), "--email", ME, "-y", home=tmp_path)

    assert json.loads(run("--json", home=tmp_path))["streak"]["longest"] >= 1
    assert json.loads(run("repos", "--json", home=tmp_path))["repositories"][0]["commits"] == 2


def test_syncing_twice_changes_nothing(tmp_path, make_repo):
    repo = make_repo("solo", remote="git@github.com:me/solo.git")
    repo.commit("2026-08-03", ME, files={"a.txt": "1\n"})
    run("init", "--root", str(repo.path.parent), "--email", ME, "-y", home=tmp_path)

    first = json.loads(run("sync", "--json", home=tmp_path))
    second = json.loads(run("sync", "--all", "--json", home=tmp_path))

    assert first["commits_new"] == 0
    assert second["commits_new"] == 0
    assert second["commits_total"] == first["commits_total"] == 1


def test_json_is_available_before_and_after_the_subcommand(tmp_path):
    before = run("--json", "config", home=tmp_path)
    after = run("config", "--json", home=tmp_path)

    assert json.loads(before)["roots"] == json.loads(after)["roots"] == []


def test_progress_never_contaminates_stdout(tmp_path, make_repo):
    repo = make_repo("solo", remote="git@github.com:me/solo.git")
    repo.commit("2026-08-03", ME, files={"a.txt": "1\n"})
    run("init", "--root", str(repo.path.parent), "--email", ME, "-y", home=tmp_path)

    out = run("sync", "--json", home=tmp_path)

    json.loads(out)  # raises if a progress line landed on stdout


def test_the_parser_rejects_nonsense_rather_than_guessing():
    for args in (["--weeks", "0"], ["--weeks", "-1"], ["sync", "--since", "yesterday"]):
        with pytest.raises(SystemExit) as exit_info:
            cli.build_parser().parse_args(args)
        assert exit_info.value.code == 2
