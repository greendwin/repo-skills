from __future__ import annotations

import pytest
from cli_error import CliError

from repo_skills.git import ensure_on_branch
from tests.cli.helper import FakeGitRepo


class TestEnsureOnBranch:
    def test_allows_dirty_on_correct_branch(self) -> None:
        git = FakeGitRepo(branch="main", clean=False)
        ensure_on_branch(git, "main", require_clean=False)
        assert git.branch == "main"

    def test_raises_when_dirty_on_wrong_branch_no_checkout(self) -> None:
        git = FakeGitRepo(branch="other", clean=False)
        with pytest.raises(CliError, match="uncommitted changes"):
            ensure_on_branch(git, "main")
        assert git.branch == "other"

    def test_switches_when_clean_and_wrong_branch(self) -> None:
        git = FakeGitRepo(branch="other", clean=True)
        ensure_on_branch(git, "main")
        assert git.branch == "main"

    def test_no_checkout_when_clean_and_correct_branch(self) -> None:
        git = FakeGitRepo(branch="main", clean=True)
        ensure_on_branch(git, "main")
        assert git.branch == "main"

    def test_pulls_when_pull_is_true(self) -> None:
        git = FakeGitRepo(branch="main", clean=True)
        ensure_on_branch(git, "main", pull=True)
        assert git.pulled

    def test_no_pull_by_default(self) -> None:
        git = FakeGitRepo(branch="main", clean=True)
        ensure_on_branch(git, "main")
        assert not git.pulled

    def test_raises_when_dirty_on_correct_branch_with_require_clean(self) -> None:
        git = FakeGitRepo(branch="main", clean=False)
        with pytest.raises(CliError, match="uncommitted changes"):
            ensure_on_branch(git, "main")

    def test_pulls_after_switching_branch(self) -> None:
        git = FakeGitRepo(branch="other", clean=True)
        ensure_on_branch(git, "main", pull=True)
        assert git.branch == "main"
        assert git.pulled
