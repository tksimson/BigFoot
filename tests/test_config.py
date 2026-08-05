"""Paths, config round-tripping, and where author identity comes from.

Every test here runs against ``tmp_path`` with the environment monkeypatched by
the autouse fixture in ``conftest.py``: the suite must never read or write the
developer's real ``~/.config/bigfoot`` or ``~/.local/share/bigfoot``, and must
never pick up their real git identity.
"""

from __future__ import annotations

import os
import subprocess

import pytest

from bigfoot import config
from bigfoot.config import DEFAULT_IGNORE_DIRS, DEFAULT_MAX_DEPTH, Config

running_as_root = hasattr(os, "geteuid") and os.geteuid() == 0


# -- where things live ---------------------------------------------------


def test_bigfoot_home_relocates_both_config_and_data(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGFOOT_HOME", str(tmp_path / "bf"))

    assert config.config_dir() == tmp_path / "bf"
    assert config.data_dir() == tmp_path / "bf"
    assert config.config_path() == tmp_path / "bf" / "config.toml"
    assert config.db_path() == tmp_path / "bf" / "bigfoot.db"


def test_bigfoot_home_wins_over_the_xdg_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("BIGFOOT_HOME", str(tmp_path / "bf"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    assert config.config_dir() == tmp_path / "bf"
    assert config.data_dir() == tmp_path / "bf"


def test_bigfoot_home_expands_a_tilde(monkeypatch, hermetic_env):
    monkeypatch.setenv("BIGFOOT_HOME", "~/bigfoot-elsewhere")

    assert config.config_dir() == hermetic_env / "bigfoot-elsewhere"


def test_xdg_config_home_and_xdg_data_home_are_respected(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))

    assert config.config_dir() == tmp_path / "xdg-config" / "bigfoot"
    assert config.data_dir() == tmp_path / "xdg-data" / "bigfoot"


def test_without_any_environment_the_xdg_defaults_under_home_are_used(hermetic_env):
    assert config.config_dir() == hermetic_env / ".config" / "bigfoot"
    assert config.data_dir() == hermetic_env / ".local" / "share" / "bigfoot"


# -- round trip ----------------------------------------------------------


def test_saving_then_loading_preserves_every_field(tmp_path):
    target = tmp_path / "config.toml"
    original = Config(
        roots=[str(tmp_path / "dev"), str(tmp_path / "work")],
        emails=["me@example.com", "me+git@example.com"],
        ignore_dirs=["node_modules", ".venv", "target"],
        max_depth=9,
        path=target,
    )

    config.save(original)
    loaded = config.load(target)

    assert loaded.roots == original.roots
    assert loaded.emails == original.emails
    assert loaded.ignore_dirs == original.ignore_dirs
    assert loaded.max_depth == 9
    assert loaded.path == target


@pytest.mark.parametrize(
    "root",
    [
        '/home/dev/we"ird',
        "/home/dev/back\\slash",
        "/home/dev/Kraków/projekty",
        "/home/dev/ünïcode 日本語",
        "/home/dev/quote\"and\\both",
        "/home/dev/with space",
        "/home/dev/hash#comment",
    ],
)
def test_values_needing_toml_escaping_survive_the_round_trip(tmp_path, root):
    target = tmp_path / "config.toml"
    config.save(Config(roots=[root], emails=["ünïcode@exämple.com"], path=target))

    loaded = config.load(target)

    assert loaded.roots == [root]
    assert loaded.emails == ["ünïcode@exämple.com"]


def test_the_default_ignore_list_survives_the_round_trip(tmp_path):
    target = tmp_path / "config.toml"
    config.save(Config(roots=["/dev"], path=target))

    assert config.load(target).ignore_dirs == list(DEFAULT_IGNORE_DIRS)


def test_saving_creates_the_directory_and_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "deeper" / "nest" / "config.toml"

    written = config.save(Config(roots=["/dev"], path=target))

    assert written == target
    assert target.is_file()
    assert [p.name for p in target.parent.iterdir()] == ["config.toml"]


def test_saving_twice_replaces_rather_than_appends(tmp_path):
    target = tmp_path / "config.toml"
    config.save(Config(roots=["/first"], path=target))

    config.save(Config(roots=["/second"], path=target))

    assert config.load(target).roots == ["/second"]


# -- degrading to defaults -----------------------------------------------


def test_a_missing_config_file_yields_defaults(tmp_path):
    target = tmp_path / "config.toml"

    loaded = config.load(target)

    assert loaded.roots == []
    assert loaded.emails == []
    assert loaded.ignore_dirs == list(DEFAULT_IGNORE_DIRS)
    assert loaded.max_depth == DEFAULT_MAX_DEPTH
    assert loaded.path == target
    assert loaded.configured is False


@pytest.mark.parametrize(
    "body",
    [
        'roots = ["/dev"',  # unterminated array
        "roots = [/dev]",  # unquoted value
        "= nonsense",  # no key
        "[section\n",  # unterminated table header
    ],
)
def test_a_malformed_config_yields_defaults_instead_of_raising(tmp_path, body):
    target = tmp_path / "config.toml"
    target.write_text(body, encoding="utf-8")

    loaded = config.load(target)

    assert loaded.roots == []
    assert loaded.ignore_dirs == list(DEFAULT_IGNORE_DIRS)


@pytest.mark.skipif(running_as_root, reason="root can read any file")
def test_an_unreadable_config_yields_defaults_instead_of_raising(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text('roots = ["/dev"]\n', encoding="utf-8")
    target.chmod(0o000)

    try:
        loaded = config.load(target)
    finally:
        target.chmod(0o600)

    assert loaded.roots == []


def test_a_directory_where_the_config_should_be_yields_defaults(tmp_path):
    target = tmp_path / "config.toml"
    target.mkdir()

    assert config.load(target).roots == []


def test_a_config_with_invalid_utf8_yields_defaults_instead_of_raising(tmp_path):
    target = tmp_path / "config.toml"
    target.write_bytes(b'roots = ["/dev/\xff\xfe"]\n')

    assert config.load(target).roots == []


@pytest.mark.parametrize("value", ["0", "-3", '"six"', "1.5"])
def test_a_non_positive_or_non_integer_max_depth_falls_back_to_the_default(tmp_path, value):
    target = tmp_path / "config.toml"
    target.write_text(f"max_depth = {value}\n", encoding="utf-8")

    assert config.load(target).max_depth == DEFAULT_MAX_DEPTH


def test_a_boolean_max_depth_falls_back_to_the_default(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("max_depth = true\n", encoding="utf-8")

    assert config.load(target).max_depth == DEFAULT_MAX_DEPTH


def test_non_string_and_blank_entries_are_dropped_from_lists(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text(
        'roots = ["/dev", 7, "  ", "  /work  "]\nemails = "not-a-list"\n',
        encoding="utf-8",
    )

    loaded = config.load(target)

    assert loaded.roots == ["/dev", "/work"]
    assert loaded.emails == []


def test_an_empty_ignore_list_falls_back_to_the_defaults(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("ignore_dirs = []\n", encoding="utf-8")

    assert config.load(target).ignore_dirs == list(DEFAULT_IGNORE_DIRS)


# -- merging -------------------------------------------------------------


def test_with_emails_dedupes_case_insensitively_and_keeps_order():
    start = Config(emails=["Me@Example.com"])

    merged = config.with_emails(start, ["me@example.com", "second@example.com", "SECOND@example.com"])

    assert merged.emails == ["Me@Example.com", "second@example.com"]


def test_with_emails_strips_whitespace_and_drops_blanks():
    merged = config.with_emails(Config(), ["  me@example.com  ", "", "   "])

    assert merged.emails == ["me@example.com"]


def test_with_emails_leaves_the_original_untouched():
    start = Config(emails=["me@example.com"])

    config.with_emails(start, ["other@example.com"])

    assert start.emails == ["me@example.com"]


def test_with_roots_absolutises_and_dedupes(tmp_path, monkeypatch):
    (tmp_path / "dev").mkdir()
    monkeypatch.chdir(tmp_path)

    merged = config.with_roots(Config(), ["dev", str(tmp_path / "dev"), "./dev"])

    assert merged.roots == [str((tmp_path / "dev").resolve())]


def test_with_roots_expands_a_tilde(hermetic_env):
    merged = config.with_roots(Config(), ["~/code"])

    assert merged.roots == [str(hermetic_env / "code")]


def test_a_config_without_roots_is_not_yet_configured(tmp_path):
    assert Config(path=tmp_path / "c.toml").configured is False
    assert Config(roots=["/dev"], path=tmp_path / "c.toml").configured is True


def test_root_paths_expand_tildes_for_scanning(hermetic_env, tmp_path):
    cfg = Config(roots=["~/code", str(tmp_path / "work")], path=tmp_path / "c.toml")

    assert cfg.root_paths() == [hermetic_env / "code", tmp_path / "work"]


# -- identity ------------------------------------------------------------


def write_git_config(path, email: str) -> None:
    path.write_text(f"[user]\n\temail = {email}\n", encoding="utf-8")


def test_git_emails_reads_the_global_and_system_git_config(tmp_path, monkeypatch):
    write_git_config(tmp_path / "gitconfig", "global@example.com")
    write_git_config(tmp_path / "gitsystem", "system@example.com")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "gitsystem"))

    assert config.git_emails() == ["global@example.com", "system@example.com"]


def test_git_emails_is_empty_when_git_has_no_identity_configured():
    assert config.git_emails() == []


def test_git_emails_dedupes_the_same_address_seen_twice(tmp_path, monkeypatch):
    write_git_config(tmp_path / "gitconfig", "me@example.com")
    write_git_config(tmp_path / "gitsystem", "ME@Example.com")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(tmp_path / "gitsystem"))

    assert config.git_emails() == ["me@example.com"]


def test_git_emails_never_harvests_identities_from_a_repository(tmp_path, monkeypatch, make_repo):
    """Identity comes from git config only, never from who happens to have committed."""
    write_git_config(tmp_path / "gitconfig", "global@example.com")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    repo = make_repo("shared")
    repo.git("config", "user.email", "local@example.com")
    repo.commit("2026-07-01", "colleague@example.com", files={"a.txt": "1\n"})
    monkeypatch.chdir(repo.path)

    found = config.git_emails()

    assert found == ["global@example.com"]
    assert "colleague@example.com" not in found
    assert "local@example.com" not in found


def test_git_emails_is_empty_when_git_is_not_installed(monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", no_git)

    assert config.git_emails() == []
