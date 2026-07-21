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
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# user edit",
        ).build()
        _fake_git.ancestors[("abc123", "main")] = False

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
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "newcommit"
        assert_words_in_message(result.output, "tdd", "recovered")

        status = assert_invoke("status")
        assert "detached" not in status.output.lower()
        assert "untracked" not in status.output.lower()

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
                source_root=Path(OTHER_REPO_ROOT),
            )
            .build()
        )
        fake_git_manager.make(Path(OTHER_REPO_ROOT)).branch_commits[
            ("skills/review", "main")
        ] = "newcommit"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["review"].detached is False
        assert manifest.skills["review"].baseline is not None
        assert manifest.skills["review"].baseline.commit == "newcommit"
        assert_words_in_message(result.output, "review", "recovered")

        status = assert_invoke("status")
        assert "detached" not in status.output.lower()
        assert "untracked" not in status.output.lower()

    def test_still_detached_shows_untracked(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            detached=True,
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# user edit",
        ).build()

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "untracked")
        assert "recovered" not in result.output.lower()

    def test_skipped_skill_with_unverifiable_commit_stays_detached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="abc123",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                user_edited="# user edit",
                latest_commit="c-tdd",
            )
            .build()
        )
        # latest commit exists but its content cannot be verified;
        # the skill is locally modified (skip path) so no commit is needed
        _fake_git.verified["skills/tdd"] = False
        _fake_git.ancestors[("abc123", "main")] = False

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "abc123"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]
        assert_words_in_message(result.output, "tdd", "detached")
        assert "failed" not in result.output.lower()

    def test_no_detached_check_when_baseline_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", has_baseline=False, latest_commit="c-tdd"
        ).build()

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert "detached" not in result.output.lower()
