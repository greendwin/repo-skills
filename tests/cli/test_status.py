from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.cli._status import UntrackedEntry, _build_untracked_lookup
from repo_skills.config import (
    SourceConfig,
    SourceRegistry,
    load_source_config,
    load_source_registry,
    save_source_config,
    save_source_registry,
)
from repo_skills.config.deprecated import (
    PROVIDERS_REGISTRY_FILE,
    ManifestSkill,
    ProviderConfig,
    ProviderRegistry,
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
            {"tdd": ManifestSkill(source="my-project", commit="abc123", files=hashes)}
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
            {"tdd": ManifestSkill(source="my-project", commit="abc123", files=hashes)}
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
                "tdd": ManifestSkill(
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
        registry = load_source_registry()
        registry.register_source("other-project", other_source)
        save_source_registry(registry)

        h1 = install_skill(fs, "tdd")
        h2 = install_skill(fs, "review")
        save_manifest(
            {
                "tdd": ManifestSkill(source="my-project", commit="abc", files=h1),
                "review": ManifestSkill(source="other-project", commit="def", files=h2),
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
            {"tdd": ManifestSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "claude", "synced")
        assert_words_in_message(result.output, "cursor", "synced")


def _create_source_skill(
    fs: FakeFilesystem, name: str, git_root: Path = SOURCE_REPO_ROOT
) -> None:
    source_cfg = load_source_config(git_root)
    assert source_cfg is not None
    skill_dir = git_root / source_cfg.skills_dir / name
    fs.create_file(skill_dir / "SKILL.md", contents=f"# {name}")


def _init_source_config(
    fs: FakeFilesystem, git_root: Path = SOURCE_REPO_ROOT, skills_dir: str = "skills"
) -> None:
    cfg = SourceConfig(name=git_root.name, skills_dir=skills_dir)
    save_source_config(cfg, git_root)


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
            {"tdd": ManifestSkill(source="my-project", commit="abc", files=hashes)}
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
        registry = SourceRegistry()
        registry.register_source("gone-project", Path("/repos/gone-project"))
        save_source_registry(registry)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "gone-project", "broken")


class TestStatusOrphan:
    def test_shows_orphan_for_untracked_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "untracked", "mystery", "orphan")


class TestStatusUntrackedHint:
    def test_available_skill_shows_untracked_hint(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        assert_words_in_message(
            result.output, "review", "mergeable", "untracked in claude"
        )

    def test_available_skill_without_untracked_shows_no_hint(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert "untracked in" not in result.output.lower()

    def test_available_skill_shows_multiple_providers_in_hint(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        cursor_dir = Path("/home/user/.cursor/skills")
        fs.create_file(cursor_dir / "review" / "SKILL.md", contents="# review cursor")
        provider_registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(cursor_dir))
            }
        )
        provider_registry.save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        result = assert_invoke("status")

        assert_words_in_message(
            result.output, "review", "mergeable", "untracked in claude, cursor"
        )


class TestStatusMergeable:
    def test_mergeable_not_shown_in_untracked_section(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        assert_words_in_message(
            result.output, "review", "mergeable", "untracked in claude"
        )


class TestStatusUntrackedOrdering:
    def test_untracked_section_hidden_when_only_mergeables(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        section_headers = [
            line.strip().lower() for line in lines if not line.startswith("  ")
        ]
        assert "untracked" not in section_headers

    def test_orphans_sorted_alphabetically(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "zeta-orphan" / "SKILL.md", contents="# zeta")
        fs.create_file(INSTALL_DIR / "alpha-orphan" / "SKILL.md", contents="# alpha")

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
        assert "alpha-orphan" in untracked_lines[0]
        assert "zeta-orphan" in untracked_lines[1]


class TestBuildUntrackedLookup:
    def test_groups_mergeable_by_skill_name(self) -> None:
        untracked = [
            UntrackedEntry("review", "claude", "my-project"),
            UntrackedEntry("review", "cursor", "my-project"),
            UntrackedEntry("mystery", "claude", ""),
        ]

        result = _build_untracked_lookup(untracked)

        assert result == {"review": ["claude", "cursor"]}

    def test_excludes_orphans(self) -> None:
        untracked = [
            UntrackedEntry("mystery", "claude", ""),
        ]

        result = _build_untracked_lookup(untracked)

        assert result == {}

    def test_empty_input(self) -> None:
        assert _build_untracked_lookup([]) == {}


class TestStatusSync:
    def test_sync_pulls_source_repos(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": ManifestSkill(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status", "--sync")

        assert _fake_git.pulled is True

    def test_no_pull_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": ManifestSkill(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("status")

        assert _fake_git.pulled is False
