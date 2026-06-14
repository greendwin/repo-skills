from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import (
    INSTALL_DIR,
    OTHER_REPO_ROOT,
    FakeGitRepoManager,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
)


class TestUpdateNamedTarget:
    def test_named_skill_updates_only_that_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke("update", "tdd", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "Updating review" not in result.output
        assert (INSTALL_DIR / "review" / "SKILL.md").read_text() == "# review v1"


class TestUpdateSourceFilter:
    def test_source_flag_narrows_to_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke("update", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "Updating review" not in result.output
        assert (INSTALL_DIR / "review" / "SKILL.md").read_text() == "# review v1"

    def test_unknown_source_errors(self, fs: FakeFilesystem, git_repo: Path) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke(
            "update", "--offline", "--source", "nope", expect_error=True
        )

        assert_words_in_message(result.exception.message, "nope", "not found")
        assert "Updating tdd" not in result.output

    def test_unknown_source_errors_even_with_valid_one(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke(
            "update",
            "--offline",
            "-s",
            "my-project",
            "-s",
            "nope",
            expect_error=True,
        )

        assert_words_in_message(result.exception.message, "nope", "not found")

    def test_name_and_source_compose_as_union(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke(
            "update", "review", "--offline", "--source", "my-project"
        )

        assert_words_in_message(result.output, "Updating review", "updated")
        assert_words_in_message(result.output, "Updating tdd", "updated")

    def test_valid_source_with_no_installed_skills_noops(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_source("other-project", OTHER_REPO_ROOT)
            .add_skill(
                "tdd",
                source_content="# tdd v1",
                installed_content="# tdd v1",
            )
            .build()
        )

        result = assert_invoke("update", "--offline", "--source", "other-project")

        assert_words_in_message(
            result.output, "no skills installed from source", "other-project"
        )

    def test_empty_filtered_update_does_not_pull(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_source("other-project", OTHER_REPO_ROOT)
            .add_skill(
                "tdd",
                source_content="# tdd v1",
                installed_content="# tdd v1",
            )
            .build()
        )

        assert_invoke("update", "--source", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False

    def test_short_flag_narrows_to_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke("update", "--offline", "-s", "other-project")

        assert_words_in_message(result.output, "Updating review", "updated")
        assert "Updating tdd" not in result.output
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v1"

    def test_multiple_sources_select_their_skills(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
                latest_commit="c-review",
            )
            .build()
        )

        result = assert_invoke(
            "update", "--offline", "-s", "my-project", "-s", "other-project"
        )

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert_words_in_message(result.output, "Updating review", "updated")


class TestUpdateMultipleNames:
    def test_multiple_named_skills_update_only_those(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                latest_commit="c-tdd",
            )
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                latest_commit="c-review",
            )
            .add_skill(
                "ship",
                source_content="# ship v2",
                installed_content="# ship v1",
                latest_commit="c-ship",
            )
            .build()
        )

        result = assert_invoke("update", "tdd", "review", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert_words_in_message(result.output, "Updating review", "updated")
        assert "Updating ship" not in result.output
        assert (INSTALL_DIR / "ship" / "SKILL.md").read_text() == "# ship v1"

    def test_unknown_among_named_skills_errors(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "tdd", "nope", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "nope", "not installed")
