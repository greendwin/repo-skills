from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    PROVIDERS_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_CONFIG_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
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
            {"tdd": SkillEntry(source="my-project", commit="old", files=hashes)}
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
            {"tdd": SkillEntry(source="my-project", commit="old", files=baseline)}
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
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        provider_registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(cursor_dir))
            }
        )
        provider_registry.save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

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
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("update", "--offline")

        assert _fake_git.pulled is False


class TestUpdateValidation:
    def test_errors_when_not_on_main_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not on main branch")
        assert_words_in_message(result.exception.message, "--any-branch")

    def test_allows_non_main_branch_with_any_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", "--any-branch")

        assert result.exit_code == 0

    def test_errors_when_repo_is_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "nope", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")

    def test_shows_message_when_no_skills_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
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
                "tdd": SkillEntry(source="my-project", commit="old", files=h1),
                "review": SkillEntry(source="my-project", commit="old", files=h2),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert_words_in_message(result.output, "review", "updated")


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
                "tdd": SkillEntry(source="my-project", commit="old", files=h1),
                "review": SkillEntry(source="my-project", commit="old", files=h2),
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")
