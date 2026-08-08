"""The version is claimed in two places and must agree in both.

Publishing is the one operation this project cannot take back: PyPI accepts a
version exactly once, so a stale `__version__` costs a version number rather
than a retry. That is worth a test.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

import gitfoot

ROOT = Path(__file__).resolve().parent.parent


def changelog_versions() -> list[str]:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, flags=re.MULTILINE)


def test_the_changelog_documents_the_version_being_shipped():
    assert gitfoot.__version__ == changelog_versions()[0]


def test_the_changelog_has_no_duplicate_versions():
    found = changelog_versions()

    assert len(found) == len(set(found))


def test_every_released_version_carries_a_date():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    for line in text.splitlines():
        if line.startswith("## [") and "Unreleased" not in line:
            assert re.match(r"^## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$", line), line


def test_the_reported_version_is_the_packaged_one():
    out = subprocess.run(
        [sys.executable, "-m", "gitfoot", "--version"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=True,
    )

    assert out.stdout.strip() == f"gitfoot {gitfoot.__version__}"


def test_hatch_reads_the_version_from_where_it_is_defined():
    """A wheel built against the wrong file would publish the wrong number."""
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert config["tool"]["hatch"]["version"]["path"] == "gitfoot/__init__.py"
    assert "version" in config["project"]["dynamic"]
