from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._update as update_mod
from repo_skills.config import (
    Baseline,
    InstalledSkill,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    save_source_config,
    save_source_registry,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    FakeGitRepoManager,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_provider,
    register_source,
    save_manifest,
)

SKILLS_DIR = SOURCE_REPO_ROOT / "skills"
OTHER_REPO_ROOT = Path("/repos/other-project")
OTHER_SKILLS_DIR = OTHER_REPO_ROOT / "skills"


def _register_two_sources(
    fs: FakeFilesystem, git_repo: Path, other_root: Path = OTHER_REPO_ROOT
) -> None:
    if not (other_root / ".git").exists():
        fs.create_dir(other_root / ".git")
    registry = SourceRegistry()
    registry.register_source("my-project", git_repo)
    registry.register_source("other-project", other_root)
    save_source_registry(registry)
    save_source_config(
        SourceConfig(name="my-project", skills_dir="skills", branch=""), git_repo
    )
    save_source_config(
        SourceConfig(name="other-project", skills_dir="skills", branch=""),
        other_root,
    )


def _install_two_source_skills(fs: FakeFilesystem, git_repo: Path) -> None:
    _register_two_sources(fs, git_repo)
    create_source_skill(fs, "tdd", content="# tdd v2", root=SKILLS_DIR)
    create_source_skill(fs, "review", content="# review v2", root=OTHER_SKILLS_DIR)
    h1 = install_skill(fs, "tdd", content="# tdd v1")
    h2 = install_skill(fs, "review", content="# review v1")
    save_manifest(
        {
            "tdd": InstalledSkill(
                source="my-project", baseline=Baseline(commit="old", files=h1)
            ),
            "review": InstalledSkill(
                source="other-project", baseline=Baseline(commit="old", files=h2)
            ),
        }
    )


class TestUpdateSynced:
    def test_overwrites_synced_skill_with_new_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files != hashes


class TestUpdateSkipsModified:
    def test_skips_when_installed_copy_was_edited(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        baseline = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=baseline)
                )
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# user edit"


class TestUpdateSkipsNoBaseline:
    def test_skips_when_baseline_is_none_and_files_on_disk(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        install_skill(fs, "tdd", content="# tdd v1")
        save_manifest({"tdd": InstalledSkill(source="my-project", baseline=None)})

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v1"


class TestUpdateUpToDate:
    def test_reports_up_to_date_when_source_matches(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up-to-date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (cursor_dir / "tdd" / "SKILL.md").exists()


class TestUpdatePull:
    def test_pulls_sources_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("update")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("update", "--offline")

        assert _fake_git.pulled is False

    def test_pull_done_message_on_normal_update(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update")

        assert_words_in_message(result.output, "Pulling", "done")

    def test_pull_skipped_message_when_offline(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
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

        assert_words_in_message(result.output, "Pulling", "skipped")

    def test_each_owning_source_gets_own_pull_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_two_sources(fs, git_repo, other_root=git_repo)
        create_source_skill(fs, "tdd")
        create_source_skill(fs, "review")
        h1 = install_skill(fs, "tdd")
        h2 = install_skill(fs, "review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=h1)
                ),
                "review": InstalledSkill(
                    source="other-project", baseline=Baseline(commit="abc", files=h2)
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling my-project")
        assert_words_in_message(result.output, "Pulling other-project")

    def test_idle_source_is_not_pulled(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", root=SKILLS_DIR)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling my-project")
        assert "Pulling other-project" not in result.output

    def test_source_flag_pulls_only_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _install_two_source_skills(fs, git_repo)

        result = assert_invoke("update", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "Pulling my-project")
        assert "Pulling other-project" not in result.output

    def test_only_owning_source_repo_is_pulled(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", root=SKILLS_DIR)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("update")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False

    def test_source_flag_pulls_only_selected_source_repo(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _install_two_source_skills(fs, git_repo)

        assert_invoke("update", "--source", "my-project")

        assert fake_git_manager.make(git_repo).pulled is True
        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False


class TestUpdateValidation:
    def test_auto_switches_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

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
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline", expect_error=True)
        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_dirty_and_wrong_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _fake_git.branch = "other"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline", expect_error=True)
        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_skill_not_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

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
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        create_source_skill(fs, "review", content="# review v2")
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        h2 = install_skill(fs, "review", content="# review v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                ),
                "review": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h2)
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateNamedTarget:
    def test_named_skill_updates_only_that_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        create_source_skill(fs, "review", content="# review v2")
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        h2 = install_skill(fs, "review", content="# review v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                ),
                "review": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h2)
                ),
            }
        )

        result = assert_invoke("update", "tdd", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "Updating review" not in result.output
        assert (INSTALL_DIR / "review" / "SKILL.md").read_text() == "# review v1"


class TestUpdateSourceFilter:
    def test_source_flag_narrows_to_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _install_two_source_skills(fs, git_repo)

        result = assert_invoke("update", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "Updating review" not in result.output
        assert (INSTALL_DIR / "review" / "SKILL.md").read_text() == "# review v1"

    def test_unknown_source_errors(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke(
            "update", "--offline", "--source", "nope", expect_error=True
        )

        assert_words_in_message(result.exception.message, "nope", "not found")
        assert "Updating tdd" not in result.output

    def test_unknown_source_errors_even_with_valid_one(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _install_two_source_skills(fs, git_repo)

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
        _install_two_source_skills(fs, git_repo)

        result = assert_invoke(
            "update", "review", "--offline", "--source", "my-project"
        )

        # "review" is selected by name; "tdd" by its my-project source.
        assert_words_in_message(result.output, "Updating review", "updated")
        assert_words_in_message(result.output, "Updating tdd", "updated")

    def test_valid_source_with_no_installed_skills_noops(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd v1", root=SKILLS_DIR)
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline", "--source", "other-project")

        assert_words_in_message(
            result.output, "no skills installed from source", "other-project"
        )

    def test_empty_filtered_update_does_not_pull(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # No tracked targets and no name-membership candidates in the eligible
        # source: the no-op fires before any pull.
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd v1", root=SKILLS_DIR)
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        assert_invoke("update", "--source", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is False

    def test_short_flag_narrows_to_that_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _install_two_source_skills(fs, git_repo)

        result = assert_invoke("update", "--offline", "-s", "other-project")

        assert_words_in_message(result.output, "Updating review", "updated")
        assert "Updating tdd" not in result.output
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v1"

    def test_multiple_sources_select_their_skills(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _install_two_source_skills(fs, git_repo)

        result = assert_invoke(
            "update", "--offline", "-s", "my-project", "-s", "other-project"
        )

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert_words_in_message(result.output, "Updating review", "updated")


class TestUpdateMultipleNames:
    def test_multiple_named_skills_update_only_those(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        for name in ("tdd", "review", "ship"):
            create_source_skill(fs, name, content=f"# {name} v2")
        hashes = {
            name: install_skill(fs, name, content=f"# {name} v1")
            for name in ("tdd", "review", "ship")
        }
        save_manifest(
            {
                name: InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h)
                )
                for name, h in hashes.items()
            }
        )

        result = assert_invoke("update", "tdd", "review", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert_words_in_message(result.output, "Updating review", "updated")
        assert "Updating ship" not in result.output
        assert (INSTALL_DIR / "ship" / "SKILL.md").read_text() == "# ship v1"

    def test_unknown_among_named_skills_errors(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "tdd", "nope", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "nope", "not installed")


class TestUpdateDetached:
    def test_unreachable_commit_marks_skill_detached(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                )
            }
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "detached")

    def test_previously_detached_skill_recovers(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert_words_in_message(result.output, "tdd", "recovered")

    def test_non_default_source_skill_recovers(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "review", root=OTHER_SKILLS_DIR)
        hashes = install_skill(fs, "review")
        save_manifest(
            {
                "review": InstalledSkill(
                    source="other-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )
        fake_git_manager.make(OTHER_REPO_ROOT).ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["review"].detached is False
        assert_words_in_message(result.output, "review", "recovered")

    def test_still_detached_shows_untracked(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "untracked")
        assert "recovered" not in result.output.lower()

    def test_no_detached_check_when_commit_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        install_skill(fs, "tdd")
        save_manifest({"tdd": InstalledSkill(source="my-project", baseline=None)})

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert "detached" not in result.output.lower()


class TestUpdateErrorMessages:
    def test_source_not_in_registry_shows_specific_error(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                ),
                "orphan": InstalledSkill(
                    source="unknown-source",
                    baseline=Baseline(commit="abc"),
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "error", "source", "unknown-source", "not found"
        )

        manifest = load_manifest()
        assert "orphan" in manifest.skills

    def test_skill_removed_from_source_shows_specific_error(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                ),
                "gone": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc")
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "error: skill removed from source")

        manifest = load_manifest()
        assert "gone" in manifest.skills


class TestUpdateProgressLines:
    def test_progress_lines_appear_per_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        create_source_skill(fs, "review", content="# review v2")
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        h2 = install_skill(fs, "review", content="# review v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                ),
                "review": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h2)
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd")
        assert_words_in_message(result.output, "Updating review")


class TestUpdateBatchResilience:
    def test_modified_skill_does_not_block_others(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        create_source_skill(fs, "review", content="# review v2")
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        h2 = install_skill(fs, "review", content="# review v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                ),
                "review": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h2)
                ),
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateExceptionHandling:
    def _setup_two_skills(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> tuple[dict[str, str], dict[str, str]]:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        create_source_skill(fs, "review", content="# review v2")
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        h2 = install_skill(fs, "review", content="# review v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                ),
                "review": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h2)
                ),
            }
        )

        real_compute = compute_file_hashes

        def _bomb(path: Path) -> dict[str, str]:
            if "tdd" in str(path) and "skills/tdd" in str(path):
                raise RuntimeError("disk exploded")
            return real_compute(path)

        monkeypatch.setattr(update_mod, "compute_file_hashes", _bomb)
        return h1, h2

    def test_unexpected_error_shows_message(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "error: disk exploded")
        assert_words_in_message(result.output, "review", "updated")

    def test_manifest_not_updated_for_failed_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        h1, _h2 = self._setup_two_skills(fs, git_repo, monkeypatch)

        assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files == h1
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["review"].baseline is not None
        assert manifest.skills["review"].baseline.files != _h2

    def test_debug_flag_shows_traceback(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("--debug", "update", "--offline")

        assert "Traceback" in result.output
        assert_words_in_message(result.output, "error: disk exploded")

    def test_no_traceback_without_debug(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("update", "--offline")

        assert "Traceback" not in result.output


class TestUpdatePerProviderOutput:
    def test_mixed_status_shows_per_provider_lines(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# user edit", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        lines = result.output.splitlines()
        claude_lines = [line for line in lines if "claude" in line]
        cursor_lines = [line for line in lines if "cursor" in line]
        assert len(claude_lines) == 1
        assert len(cursor_lines) == 1
        assert_words_in_message(claude_lines[0], "claude", "updated")
        assert_words_in_message(cursor_lines[0], "cursor", "skipped")

    def test_all_providers_updated_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd v1", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_all_providers_skipped_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        baseline = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=baseline)
                )
            }
        )
        # Simulate user edits on both providers so both diverge from baseline
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")
        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# user edit", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "skipped")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_all_providers_up_to_date_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "up-to-date")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_single_provider_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=hashes)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "claude" not in result.output.lower()

    def test_per_provider_lines_with_recovered(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# user edit", install_dir=cursor_dir)

        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        lines = result.output.splitlines()
        claude_lines = [line for line in lines if "claude" in line]
        cursor_lines = [line for line in lines if "cursor" in line]
        assert len(claude_lines) == 1
        assert len(cursor_lines) == 1
        assert_words_in_message(claude_lines[0], "claude", "updated")
        assert_words_in_message(cursor_lines[0], "cursor", "skipped")
        assert_words_in_message(result.output, "recovered")


class TestUpdateAttach:
    def test_exact_match_untracked_is_attached_and_updated(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "Attached skill tdd", "matched source my-project"
        )

        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.detached is False
        assert entry.baseline is not None
        assert entry.baseline.commit == "commit-tdd"
        assert entry.baseline.files == compute_file_hashes(INSTALL_DIR / "tdd")

    def test_same_skill_in_two_providers_attaches_once(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd", install_dir=cursor_dir)
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert result.output.count("Attached skill tdd") == 1
        manifest = load_manifest()
        assert list(manifest.skills) == ["tdd"]

    def test_exact_match_untracked_is_attached_and_reports_up_to_date(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "up-to-date")

        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert entry.baseline is not None
        assert entry.baseline.commit == "commit-tdd"
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_exact_match_with_verify_failure_is_not_attached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.verified["skills/tdd"] = False

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_exact_match_with_unresolved_commit_is_not_attached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_skill_vanished_from_source_post_pull_is_not_attached(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The skill name-matches when the candidate is found, but the source
        # path no longer hashes equal at attach time (content drifted across the
        # pull). It must be silently left untouched, with no crash.
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        real_compute = compute_file_hashes

        def _drift(path: Path) -> dict[str, str]:
            if str(path).startswith(str(SKILLS_DIR / "tdd")):
                return {"SKILL.md": "drifted"}
            return real_compute(path)

        monkeypatch.setattr(update_mod, "compute_file_hashes", _drift)

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_detached_entry_matching_source_is_not_re_attached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert list(manifest.skills) == ["tdd"]
        assert manifest.skills["tdd"].detached is False

    def test_modified_untracked_is_not_attached_and_untouched(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        install_skill(fs, "tdd", content="# user copy")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# user copy"


class TestUpdateAttachAmbiguity:
    def test_multi_source_exact_match_is_skipped_with_note(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "tdd", content="# tdd", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        assert_words_in_message(result.output, "tdd", "multiple sources")
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_source_flag_disambiguates_multi_source_match(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "tdd", content="# tdd", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        my_git = fake_git_manager.make(git_repo)
        my_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        my_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline", "-s", "my-project")

        assert_words_in_message(
            result.output, "Attached skill tdd", "matched source my-project"
        )
        manifest = load_manifest()
        assert manifest.skills["tdd"].source == "my-project"


class TestUpdateAttachFilter:
    def test_source_flag_excludes_other_source_candidate(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})

        result = assert_invoke("update", "--offline", "-s", "my-project")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills

    def test_source_flag_attaches_untracked_match_instead_of_noop(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "--offline", "-s", "other-project")

        assert "no skills installed from source" not in result.output.lower()
        assert_words_in_message(
            result.output, "Attached skill review", "matched source other-project"
        )
        assert_words_in_message(result.output, "Updating review")
        manifest = load_manifest()
        assert manifest.skills["review"].source == "other-project"

    def test_attach_candidate_source_is_pulled(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})

        assert_invoke("update", "-s", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is True

    def test_source_flag_does_not_pull_or_attach_other_source_match(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # An untracked dir exactly matches source Y, but only X is named.
        # Attach must not expand the -s filter: Y is neither pulled nor attached.
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc", files={}),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "-s", "my-project")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills
        assert other_git.pulled is False

    def test_name_filter_does_not_attach_unrelated_untracked_match(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # Name-only filter: eligible = sources of named skills. An untracked dir
        # matching a different, unnamed source must not be attached.
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit="abc", files=compute_file_hashes(INSTALL_DIR / "tdd")
                    ),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "tdd", "--offline")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills

    def test_name_membership_candidate_source_is_pulled_for_post_pull_check(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # The source contains a skill by NAME matching the untracked dir, but the
        # pre-pull content differs. The source must still be pulled so the match
        # can be re-validated against post-pull content.
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "review", content="# review v2", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review v1")
        save_manifest({})

        assert_invoke("update", "-s", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is True


class TestUpdateBrokenSource:
    def test_broken_source_warns_and_valid_skill_still_updates(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # "broken-project" is registered but has no source config, so loading it
        # raises during eligible-source collection. The presence of an untracked
        # install dir triggers that load; the warning must fire and not crash,
        # and the valid tracked skill must still update.
        broken_root = Path("/repos/broken-project")
        fs.create_dir(broken_root / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("broken-project", broken_root)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills", branch=""), git_repo
        )

        create_source_skill(fs, "tdd", content="# tdd v2", root=SKILLS_DIR)
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        install_skill(fs, "untracked-skill", content="# untracked")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "warning", "broken-project")
        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"


class TestUpdateAttachNoFilter:
    def test_plain_update_attaches_match_from_untracked_only_source(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        # Plain update (no filters): an untracked exact-match from a registered
        # source with zero installed skills is pulled and attached.
        _register_two_sources(fs, git_repo)
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit="abc", files=compute_file_hashes(INSTALL_DIR / "tdd")
                    ),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "Attached skill review", "matched source other-project"
        )
        manifest = load_manifest()
        assert manifest.skills["review"].source == "other-project"
