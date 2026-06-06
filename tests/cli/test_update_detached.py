from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import (
    OTHER_REPO_ROOT,
    FakeGitRepo,
    FakeGitRepoManager,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    load_manifest,
)


class TestUpdateDetached:
    def test_unreachable_commit_marks_skill_detached(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc123").build()

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "detached")

    def test_previously_detached_skill_recovers(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", commit="abc123", detached=True
        ).build()
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert_words_in_message(result.output, "tdd", "recovered")

    def test_non_default_source_skill_recovers(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "review",
                commit="abc123",
                detached=True,
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
            )
            .build()
        )
        fake_git_manager.make(OTHER_REPO_ROOT).ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["review"].detached is False
        assert_words_in_message(result.output, "review", "recovered")

    def test_still_detached_shows_untracked(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", commit="abc123", detached=True
        ).build()

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "untracked")
        assert "recovered" not in result.output.lower()

    def test_no_detached_check_when_commit_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", has_baseline=False).build()

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert "detached" not in result.output.lower()
