from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    PROVIDERS_REGISTRY_FILE,
)
from repo_skills.config import REPO_SKILLS_DIR as REPO_SKILLS_DIR_NAME
from repo_skills.config import (
    SKILL_MANIFEST_FILE,
    SOURCE_CONFIG_FILE,
    SOURCES_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SkillManifest,
    SourceConfig,
    SourceEntry,
    SourceRegistry,
    compute_file_hashes,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_CONFIG_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    install_fake_git,
    uninstall_fake_git,
)

SKILLS_DIR = SOURCE_REPO_ROOT / "skills"


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo()
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def _register_source(fs: FakeFilesystem, git_repo: Path) -> None:
    registry = SourceRegistry(sources={"my-project": SourceEntry(path=str(git_repo))})
    registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

    cfg = SourceConfig(name="my-project", skills_dir="skills")
    cfg.save(git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE)


def _create_source_skill(
    fs: FakeFilesystem, name: str, content: str = "# skill"
) -> None:
    fs.create_file(SKILLS_DIR / name / "SKILL.md", contents=content)


def _install_skill(
    fs: FakeFilesystem,
    name: str,
    content: str = "# skill",
    *,
    install_dir: Path = INSTALL_DIR,
) -> dict[str, str]:
    skill_dir = install_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=content)
    return compute_file_hashes(skill_dir)


def _save_manifest(skills: dict[str, SkillEntry]) -> None:
    manifest = SkillManifest(skills=skills)
    manifest.save(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)


def _load_manifest() -> SkillManifest:
    return SkillManifest.load(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)


class TestUpdateSynced:
    def test_overwrites_synced_skill_with_new_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd v2")
        hashes = _install_skill(fs, "tdd", content="# tdd v1")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="old", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        manifest = _load_manifest()
        assert manifest.skills["tdd"].files != hashes


class TestUpdateSkipsModified:
    def test_skips_when_installed_copy_was_edited(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd v2")
        baseline = _install_skill(fs, "tdd", content="# tdd v1")
        _save_manifest(
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
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd")
        hashes = _install_skill(fs, "tdd", content="# tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd")
        hashes = _install_skill(fs, "tdd", content="# tdd")
        _save_manifest(
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
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("update")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("update", "--offline")

        assert _fake_git.pulled is False


class TestUpdateValidation:
    def test_errors_when_not_on_main_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not on main branch")
        assert_words_in_message(result.exception.message, "--any-branch")

    def test_allows_non_main_branch_with_any_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", "--any-branch")

        assert result.exit_code == 0

    def test_errors_when_repo_is_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_skill_not_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd")
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
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
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd v2")
        _create_source_skill(fs, "review", content="# review v2")
        h1 = _install_skill(fs, "tdd", content="# tdd v1")
        h2 = _install_skill(fs, "review", content="# review v1")
        _save_manifest(
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
        _register_source(fs, git_repo)
        _create_source_skill(fs, "tdd", content="# tdd v2")
        _create_source_skill(fs, "review", content="# review v2")
        h1 = _install_skill(fs, "tdd", content="# tdd v1")
        h2 = _install_skill(fs, "review", content="# review v1")
        _save_manifest(
            {
                "tdd": SkillEntry(source="my-project", commit="old", files=h1),
                "review": SkillEntry(source="my-project", commit="old", files=h2),
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")
