from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._update as update_mod
from repo_skills.config import (
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


class TestUpdateSynced:
    def test_overwrites_synced_skill_with_new_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="old", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        manifest = load_manifest()
        assert manifest.skills["tdd"].files != hashes


class TestUpdateSkipsModified:
    def test_skips_when_installed_copy_was_edited(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        baseline = install_skill(fs, "tdd", content="# tdd v1")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="old", files=baseline)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# user edit"


class TestUpdateUpToDate:
    def test_reports_up_to_date_when_source_matches(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling", "skipped")

    def test_each_source_gets_own_pull_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", git_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills", branch=""), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills", branch=""), git_repo
        )
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Pulling my-project")
        assert_words_in_message(result.output, "Pulling other-project")


class TestUpdateValidation:
    def test_auto_switches_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")

    def test_errors_when_repo_is_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateDetached:
    def test_unreachable_commit_marks_skill_detached(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc123", files=hashes)}
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
                    source="my-project", commit="abc123", files=hashes, detached=True
                )
            }
        )
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert_words_in_message(result.output, "tdd", "recovered")

    def test_no_message_when_still_detached(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", commit="abc123", files=hashes, detached=True
                )
            }
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert "detached" not in result.output.lower()
        assert "recovered" not in result.output.lower()

    def test_no_detached_check_when_commit_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )

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
                "tdd": InstalledSkill(source="my-project", commit="abc", files=hashes),
                "orphan": InstalledSkill(
                    source="unknown-source", commit="abc", files={}
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "error: source 'unknown-source' not found"
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
                "tdd": InstalledSkill(source="my-project", commit="abc", files=hashes),
                "gone": InstalledSkill(source="my-project", commit="abc", files={}),
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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
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
        assert manifest.skills["tdd"].files == h1
        assert manifest.skills["tdd"].commit == "old"
        assert manifest.skills["review"].files != _h2

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
