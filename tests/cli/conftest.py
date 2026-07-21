from __future__ import annotations

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._deps as deps_mod
from repo_skills.console import reporter
from tests.cli.helper import (
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    FakeGitRepoManager,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/user")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/user/.config")


@pytest.fixture()
def git_repo(fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch) -> Path:
    fs.create_dir(Path(SOURCE_REPO_ROOT) / ".git")
    monkeypatch.chdir(Path(SOURCE_REPO_ROOT))
    return Path(SOURCE_REPO_ROOT)


@pytest.fixture()
def fake_git_manager(
    fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
) -> Generator[FakeGitRepoManager]:
    # note: import `fs` so FakeGitRepo()'s default_factory builds its root under fake fs
    mng = FakeGitRepoManager()
    monkeypatch.setattr(deps_mod, "_git_repo_factory", mng.make)
    try:
        yield mng
    finally:
        mng.uninstall_all()


@pytest.fixture()
def _fake_git_factory() -> Callable[[], FakeGitRepo]:
    # default seed; modules/classes override to seed commits/ancestors. Returns a
    # factory (not an instance) so `_fake_git` can build it AFTER fs activation.
    return FakeGitRepo


@pytest.fixture(autouse=True)
def _fake_git(
    fake_git_manager: FakeGitRepoManager,
    _fake_git_factory: Callable[[], FakeGitRepo],
) -> Generator[FakeGitRepo]:
    fake = _fake_git_factory()
    fake_git_manager.install(fake)
    yield fake


@pytest.fixture(autouse=True)
def _reset_debug() -> Generator[None]:
    yield
    reporter.debug = False
