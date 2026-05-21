from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import (
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    install_fake_git,
    uninstall_fake_git,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/user")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")


@pytest.fixture()
def git_repo(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> Path:
    fs.create_dir(SOURCE_REPO_ROOT / ".git")
    monkeypatch.chdir(SOURCE_REPO_ROOT)
    return SOURCE_REPO_ROOT


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo()
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()
