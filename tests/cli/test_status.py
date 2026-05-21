from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    PROVIDERS_REGISTRY_FILE,
)
from repo_skills.config import REPO_SKILLS_DIR as REPO_SKILLS_DIR_NAME
from repo_skills.config import (
    SOURCE_CONFIG_FILE,
    SOURCES_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SourceConfig,
    SourceEntry,
    SourceRegistry,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_CONFIG_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    install_skill,
    register_source,
    save_manifest,
)


class TestStatusSynced:
    def test_shows_synced_skill(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc123", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "my-project", "synced")


class TestStatusModified:
    def test_shows_modified_when_content_changed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc123", files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "modified")


class TestStatusMissing:
    def test_shows_missing_when_not_on_disk(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        save_manifest(
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
        register_source(git_repo)
        other_source = Path("/repos/other-project")
        fs.create_dir(other_source / ".git")
        registry = SourceRegistry.load(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        registry.sources["other-project"] = SourceEntry(path=str(other_source))
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

        h1 = install_skill(fs, "tdd")
        h2 = install_skill(fs, "review")
        save_manifest(
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
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        install_skill(fs, "tdd", install_dir=cursor_dir)

        provider_registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(cursor_dir))
            }
        )
        provider_registry.save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "claude", "synced")
        assert_words_in_message(result.output, "cursor", "synced")


def _create_source_skill(
    fs: FakeFilesystem, name: str, git_root: Path = SOURCE_REPO_ROOT
) -> None:
    source_cfg = SourceConfig.load(git_root / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE)
    skill_dir = git_root / source_cfg.skills_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=f"# {name}")


def _init_source_config(
    fs: FakeFilesystem, git_root: Path = SOURCE_REPO_ROOT, skills_dir: str = "skills"
) -> None:
    cfg = SourceConfig(name=git_root.name, skills_dir=skills_dir)
    cfg.save(git_root / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE)


class TestStatusAvailable:
    def test_shows_available_skill(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "my-project", "review", "available")


class TestStatusAvailableExcludesInstalled:
    def test_installed_skill_not_shown_as_available(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "tdd", git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "synced")
        assert "available" not in result.output.lower()


class TestStatusEmpty:
    def test_shows_no_skills_message(self, fs: FakeFilesystem, git_repo: Path) -> None:
        result = assert_invoke("status")

        assert_words_in_message(result.output, "no skills found")


class TestStatusSourceNotFound:
    def test_shows_warning_for_missing_source_repo(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        registry = SourceRegistry(
            sources={"gone-project": SourceEntry(path="/repos/gone-project")}
        )
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "gone-project", "source not found")


class TestStatusOrphan:
    def test_shows_orphan_for_untracked_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "untracked", "mystery", "orphan")


class TestStatusMergeable:
    def test_shows_mergeable_when_source_match(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        assert_words_in_message(
            result.output, "untracked", "review", "mergeable", "my-project"
        )


class TestStatusUntrackedOrdering:
    def test_mergeable_shown_before_orphan(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "zeta-skill", git_repo)

        fs.create_file(INSTALL_DIR / "alpha-orphan" / "SKILL.md", contents="# alpha")
        fs.create_file(INSTALL_DIR / "zeta-skill" / "SKILL.md", contents="# zeta local")

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        untracked_lines = []
        in_untracked = False
        for line in lines:
            if "untracked" in line.lower():
                in_untracked = True
                continue
            if in_untracked and line.strip():
                untracked_lines.append(line.strip())

        assert len(untracked_lines) == 2
        assert "zeta-skill" in untracked_lines[0]
        assert "alpha-orphan" in untracked_lines[1]


class TestStatusSync:
    def test_sync_pulls_source_repos(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status", "--sync")

        assert _fake_git.pulled is True

    def test_no_pull_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status")

        assert _fake_git.pulled is False
