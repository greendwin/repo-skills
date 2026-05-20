from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    PROVIDERS_REGISTRY_FILE,
    SKILL_MANIFEST_FILE,
    SOURCES_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SkillManifest,
    SourceEntry,
    SourceRegistry,
    compute_file_hashes,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_CONFIG_DIR,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    install_fake_git,
    uninstall_fake_git,
)


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo()
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def _register_source(fs: FakeFilesystem, git_repo: Path) -> None:
    registry = SourceRegistry(sources={"my-project": SourceEntry(path=str(git_repo))})
    registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)


def _install_skill(
    fs: FakeFilesystem,
    name: str,
    source: str = "my-project",
    *,
    install_dir: Path = INSTALL_DIR,
    content: str = "# skill",
) -> dict[str, str]:
    skill_dir = install_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=content)
    return compute_file_hashes(skill_dir)


def _save_manifest(skills: dict[str, SkillEntry]) -> None:
    manifest = SkillManifest(skills=skills)
    manifest.save(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)


class TestStatusSynced:
    def test_shows_synced_skill(self, fs: FakeFilesystem, git_repo: Path) -> None:
        _register_source(fs, git_repo)
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc123", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "my-project", "synced")


class TestStatusModified:
    def test_shows_modified_when_content_changed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc123", files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "modified")


class TestStatusMissing:
    def test_shows_missing_when_not_on_disk(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        _save_manifest(
            {
                "tdd": SkillEntry(
                    source="my-project",
                    commit="abc123",
                    files={"SKILL.md": "sha256:aaa"},
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "missing")


class TestStatusGrouping:
    def test_groups_skills_by_source(self, fs: FakeFilesystem, git_repo: Path) -> None:
        _register_source(fs, git_repo)
        other_source = Path("/repos/other-project")
        fs.create_dir(other_source / ".git")
        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        registry.sources["other-project"] = SourceEntry(path=str(other_source))
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

        h1 = _install_skill(fs, "tdd")
        h2 = _install_skill(fs, "review")
        _save_manifest(
            {
                "tdd": SkillEntry(source="my-project", commit="abc", files=h1),
                "review": SkillEntry(source="other-project", commit="def", files=h2),
            }
        )

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        source_lines = [
            line.strip()
            for line in lines
            if "project" in line.lower()
            and "synced" not in line.lower()
            and "modified" not in line.lower()
        ]
        assert len(source_lines) == 2


class TestStatusMultiProvider:
    def test_shows_status_per_provider(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _register_source(fs, git_repo)
        hashes = _install_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        _install_skill(fs, "tdd", install_dir=cursor_dir)

        provider_registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(cursor_dir))
            }
        )
        provider_registry.save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "claude", "synced")
        assert_words_in_message(result.output, "cursor", "synced")


class TestStatusEmpty:
    def test_shows_no_skills_message(self, fs: FakeFilesystem, git_repo: Path) -> None:
        result = assert_invoke("status")

        assert_words_in_message(result.output, "no skills installed")


class TestStatusSync:
    def test_sync_pulls_source_repos(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _register_source(fs, git_repo)
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status", "--sync")

        assert _fake_git.pulled is True

    def test_no_pull_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _register_source(fs, git_repo)
        hashes = _install_skill(fs, "tdd")
        _save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status")

        assert _fake_git.pulled is False
