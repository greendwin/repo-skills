from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    Baseline,
    InstalledSkill,
    ProviderRegistry,
    save_provider_registry,
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
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .build()
        )
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files != hashes["tdd"]


class TestUpdateAdvancesBaseline:
    def test_advances_commit_so_status_is_synced(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="old",
            source_content="# tdd v2",
            installed_content="# tdd v1",
        ).build()
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "newcommit"

        status = assert_invoke("status")
        assert "outdated" not in status.output.lower()

    def test_up_to_date_skill_advances_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="old",
            source_content="# tdd",
            installed_content="# tdd",
        ).build()
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up-to-date")
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "newcommit"

        status = assert_invoke("status")
        assert "outdated" not in status.output.lower()

    def test_unresolvable_commit_reports_failed_and_does_not_advance(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="old",
                source_content="# tdd v2",
                installed_content="# tdd v1",
            )
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "failed", "no commit found")
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        # no resolvable commit: baseline left entirely untouched
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]
        # resolution fails before any copy: install dir keeps the original
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text() == "# tdd v1"

    def test_skipped_skill_leaves_baseline_untouched(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="old",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                user_edited="# user edit",
            )
            .build()
        )
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"
        _fake_git.ancestors[("old", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]
        assert manifest.skills["tdd"].detached is False

        status = assert_invoke("status")
        assert_words_in_message(status.output, "modified", "outdated")

    def test_unmodified_outdated_skill_is_never_detached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="old",
            source_content="# tdd",
            installed_content="# tdd",
        ).build()
        _fake_git.branch_commits[("skills/tdd", "main")] = "new456"
        # old baseline commit is unreachable from the pinned branch tip
        _fake_git.ancestors[("old", "main")] = False

        result = assert_invoke("update")

        assert "detached" not in result.output.lower()
        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "new456"

    def test_unverified_latest_commit_reports_failed_and_does_not_advance(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="old",
                source_content="# tdd v2",
                installed_content="# tdd v1",
            )
            .build()
        )
        _fake_git.branch_commits[("skills/tdd", "main")] = "new456"
        # latest commit exists but its content cannot be verified
        _fake_git.verified["skills/tdd"] = False

        result = assert_invoke("update")

        assert_words_in_message(result.output, "tdd", "failed", "content mismatch")
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        # verification error propagates: baseline left entirely untouched
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]
        assert manifest.skills["tdd"].detached is False
        # source working tree (dirty) must not be copied into the install dir
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text() == "# tdd v1"

    def test_empty_provider_registry_leaves_baseline_untouched(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="old",
                source_content="# tdd",
                installed_content="# tdd",
            )
            .build()
        )
        # no providers at all: nothing to copy, nothing to compare
        save_provider_registry(ProviderRegistry())
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        # an empty registry must never advance the baseline to the "" sentinel
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]

    def test_multi_provider_skipped_leaves_baseline_untouched(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="old",
                source_content="# tdd v2",
                installed_content="# tdd v1",
                user_edited="# user edit",
            )
            .build()
        )
        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        # cursor copy is in sync (matches source); claude copy is user-edited
        fs.create_file(cursor_dir / "tdd" / "SKILL.md", contents="# tdd v2")
        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"
        _fake_git.ancestors[("old", "main")] = True

        assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]


class TestUpdateSkipsModified:
    def test_skips_when_installed_copy_was_edited(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd v2", installed_content="# tdd v1"
        ).build()
        (Path(INSTALL_DIR) / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text() == "# user edit"


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
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text() == "# tdd v1"


class TestUpdateUpToDate:
    def test_reports_up_to_date_when_source_matches(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd", installed_content="# tdd", commit="abc"
        ).build()
        _fake_git.branch_commits[("skills/tdd", "main")] = "abc"

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up-to-date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd", source_content="# tdd", installed_content="# tdd", commit="abc"
        ).build()
        _fake_git.branch_commits[("skills/tdd", "main")] = "abc"

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
            .add_source("other-project", Path(OTHER_REPO_ROOT))
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
                source_root=Path(OTHER_REPO_ROOT),
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
            .add_source("other-project", Path(OTHER_REPO_ROOT))
            .add_skill("tdd", commit="abc")
            .build()
        )

        assert_invoke("update")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(Path(OTHER_REPO_ROOT)).pulled is False

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
                source_root=Path(OTHER_REPO_ROOT),
            )
            .build()
        )

        assert_invoke("update", "--source", "my-project")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(Path(OTHER_REPO_ROOT)).pulled is False


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
        _fake_git.branch_commits[("skills/tdd", "develop")] = "abc"
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

    @pytest.mark.parametrize(
        "wrong_branch",
        [
            pytest.param(False, id="correct-branch"),
            pytest.param(True, id="wrong-branch"),
        ],
    )
    def test_dirty_repo_is_reported_not_fatal(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
        wrong_branch: bool,
    ) -> None:
        _fake_git.clean = False
        if wrong_branch:
            _fake_git.branch = "other"
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill(
                "tdd",
                commit="abc",
                source_content="# tdd v2",
                installed_content="# tdd v1",
            )
            .build()
        )

        result = assert_invoke("update", "--offline")

        assert_status_line(result.output, "Pulling my-project", "failed")
        assert_words_in_message(result.output, "uncommitted changes")
        assert_words_in_message(
            result.output, "tdd", "source", "my-project", "unavailable"
        )

        # source failed to sync: install dir and baseline stay untouched
        installed = (Path(INSTALL_DIR) / "tdd" / "SKILL.md").read_text()
        assert installed == "# tdd v1"
        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files == hashes["tdd"]
        assert manifest.skills["tdd"].baseline.commit == "abc"

    def test_errors_when_skill_not_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill("tdd", commit="abc").build()

        result = assert_invoke("update", "nope", "--offline", expect_error=True)

        assert_words_in_message(result.message, "not installed")

    @pytest.mark.usefixtures("fs", "git_repo")
    def test_shows_message_when_no_skills_installed(self) -> None:
        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "no skills installed")


class TestUpdateAll:
    def test_updates_all_installed_skills(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
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
        _fake_git.branch_commits[("skills/tdd", "main")] = "c-tdd"
        _fake_git.branch_commits[("skills/review", "main")] = "c-review"

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
