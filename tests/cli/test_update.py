from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    Baseline,
    InstalledSkill,
)
from tests.cli.helper import (
    INSTALL_DIR,
    OTHER_REPO_ROOT,
    FakeGitRepo,
    FakeGitRepoManager,
    SkillSetup,
    assert_invoke,
    assert_status_line,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_provider,
    register_source,
    save_manifest,
)


class TestUpdateSynced:
    def test_overwrites_synced_skill_with_new_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files != hashes["tdd"]


class TestUpdateSkipsModified:
    def test_skips_when_installed_copy_was_edited(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd v2", installed_content="# tdd v1"
        ).build()
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# user edit"


class TestUpdateSkipsNoBaseline:
    def test_skips_when_baseline_is_none_and_files_on_disk(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            has_baseline=False,
        ).build()

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v1"


class TestUpdateUpToDate:
    def test_reports_up_to_date_when_source_matches(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd", installed_content="# tdd", commit="abc"
        ).build()

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up-to-date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd", installed_content="# tdd", commit="abc"
        ).build()

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (cursor_dir / "tdd" / "SKILL.md").exists()


class TestUpdatePull:
    def test_pulls_sources_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        assert_invoke("update")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        assert_invoke("update", "--offline")

        assert _fake_git.pulled is False

    def test_pull_done_message_on_normal_update(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update")

        assert_words_in_message(result.output, "Pulling", "done")

    def test_pull_announcement_terminated_before_online_pull(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update")

        assert_status_line(result.output, "Pulling my-project")
        assert_status_line(result.output, "Pulling my-project", "done")

    def test_pull_skipped_message_when_offline(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling", "skipped")

    def test_pull_announcement_stays_inline_when_offline(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "--offline")

        assert_status_line(result.output, "Pulling my-project", "skipped")
        assert_status_line(result.output, "Pulling my-project", present=False)

    def test_each_owning_source_gets_own_pull_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", commit="abc")
            .add_skill(
                "review",
                commit="abc",
                source_name="other-project",
                source_root=git_repo,
            )
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling my-project")
        assert_words_in_message(result.output, "Pulling other-project")

    def test_idle_source_is_not_pulled(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_source("other-project", OTHER_REPO_ROOT)
            .add_skill("tdd", commit="abc")
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling my-project")
        assert "Pulling other-project" not in result.output

    def test_source_flag_pulls_only_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
            )
            .build()
        )

        result = assert_invoke("update", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "Pulling my-project")
        assert "Pulling other-project" not in result.output

    def test_only_owning_source_repo_is_pulled(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_source("other-project", OTHER_REPO_ROOT)
            .add_skill("tdd", commit="abc")
            .build()
        )

        assert_invoke("update")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False

    def test_source_flag_pulls_only_selected_source_repo(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
                source_name="other-project",
                source_root=OTHER_REPO_ROOT,
            )
            .build()
        )

        assert_invoke("update", "--source", "my-project")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False


class TestUpdateValidation:
    def test_auto_switches_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        assert_invoke("update", "--offline")

        assert _fake_git.branch == "main"

    def test_succeeds_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "develop"
        register_source(git_repo, branch="develop")
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up-to-date")

    def test_deny_dirty_repo_on_correct_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "--offline", expect_error=True)
        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_dirty_and_wrong_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _fake_git.branch = "other"
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "--offline", expect_error=True)
        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_skill_not_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "nope", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")

    @pytest.mark.usefixtures("fs", "git_repo")
    def test_shows_message_when_no_skills_installed(self) -> None:
        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "no skills installed")


class TestUpdateAll:
    def test_updates_all_installed_skills(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
            )
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateProgressLines:
    def test_progress_lines_appear_per_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
            )
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd")
        assert_words_in_message(result.output, "Updating review")
