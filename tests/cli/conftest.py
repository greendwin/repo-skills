from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import SOURCE_REPO_ROOT


@pytest.fixture()
def git_repo(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")
    fs.create_dir(SOURCE_REPO_ROOT / ".git")
    monkeypatch.chdir(SOURCE_REPO_ROOT)
    return SOURCE_REPO_ROOT
