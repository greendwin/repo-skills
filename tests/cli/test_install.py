from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    SourceConfig,
    load_skill_manifest,
    load_source_registry,
    save_source_config,
    save_source_registry,
)
from tests.cli.helper import (
    INSTALL_DIR,
    SKILLS_DIR,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
    install_fake_git,
    register_provider,
    register_source,
    uninstall_fake_git,
)

OTHER_REPO_ROOT = Path("/repos/other-project")
OTHER_SKILLS_DIR = OTHER_REPO_ROOT / "skills"


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo(commits={"tdd": "abc1234"})
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def _add_second_source(fs: FakeFilesystem) -> None:
    fs.create_dir(OTHER_REPO_ROOT / ".git")
    registry = load_source_registry()
    registry.register_source("other-project", OTHER_REPO_ROOT)
    save_source_registry(registry)

    cfg = SourceConfig(name="other-project", skills_dir="skills", branch="")
    save_source_config(cfg, OTHER_REPO_ROOT)


class TestInstall:
    def test_copies_skill_to_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        skill_dir = create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        fs.create_file(skill_dir / "tests.python.md", contents="# Python tests")

        assert_invoke("install", "tdd", "--offline")

        assert (INSTALL_DIR / "tdd" / "SKILL.md").exists()
        assert (INSTALL_DIR / "tdd" / "tests.python.md").exists()

    def test_records_source_commit_hashes_in_manifest(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        assert_invoke("install", "tdd", "--offline")

        manifest = load_skill_manifest()
        assert "tdd" in manifest.skills
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.commit == "abc1234"
        assert len(entry.files) > 0
        assert all(v.startswith("sha256:") for v in entry.files.values())

    def test_auto_selects_single_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd", "my-project")


class TestInstallMultipleSkills:
    @pytest.fixture(autouse=True)
    def _fake_git(self) -> Generator[FakeGitRepo]:
        fake = FakeGitRepo(commits={"tdd": "abc1234", "review": "def5678"})
        install_fake_git(fake)
        yield fake
        uninstall_fake_git()

    def test_installs_multiple_skills(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        create_repo_skill(fs, "review", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "review", "--offline")

        assert (INSTALL_DIR / "tdd" / "SKILL.md").exists()
        assert (INSTALL_DIR / "review" / "SKILL.md").exists()
        manifest = load_skill_manifest()
        assert "tdd" in manifest.skills
        assert "review" in manifest.skills
        assert_words_in_message(result.output, "installed", "tdd", "review")

    def test_fails_fast_on_missing_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke(
            "install", "tdd", "missing", "--offline", expect_error=True
        )

        assert_words_in_message(result.exception.message, "missing", "not found")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").exists()

    def test_pulls_source_only_once(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        create_repo_skill(fs, "review", root=SKILLS_DIR)

        assert_invoke("install", "tdd", "review")

        assert _fake_git.pulled is True


class TestInstallSourceResolution:
    def test_errors_when_no_sources(self, fs: FakeFilesystem, git_repo: Path) -> None:
        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "no sources")

    def test_auto_resolves_when_skill_in_one_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _add_second_source(fs)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd", "my-project")

    def test_errors_when_skill_in_multiple_sources(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _add_second_source(fs)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        create_repo_skill(fs, "tdd", root=OTHER_SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple sources", "--source"
        )

    def test_selects_source_with_flag(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        registry = load_source_registry()
        registry.register_source("other", Path("/repos/other"))
        save_source_registry(registry)

        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--source", "my-project", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    def test_selects_source_with_short_flag(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        registry = load_source_registry()
        registry.register_source("other", Path("/repos/other"))
        save_source_registry(registry)

        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "-s", "my-project", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    def test_errors_when_source_not_found(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)

        result = assert_invoke(
            "install", "tdd", "--source", "nope", "--offline", expect_error=True
        )

        assert_words_in_message(result.exception.message, "not found")


class TestInstallMultiProvider:
    def test_installs_to_all_providers(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

        assert_invoke("install", "tdd", "--offline")

        assert (INSTALL_DIR / "tdd" / "SKILL.md").exists()
        assert (cursor_dir / "tdd" / "SKILL.md").exists()


class TestInstallCollision:
    def test_errors_when_skill_already_exists(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        fs.create_dir(INSTALL_DIR / "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "already exists", "--force")

    def test_force_overwrites_existing(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)
        fs.create_dir(INSTALL_DIR / "tdd")
        fs.create_file(INSTALL_DIR / "tdd" / "old.md", contents="old")

        result = assert_invoke("install", "tdd", "--offline", "--force")

        assert_words_in_message(result.output, "installed", "tdd")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").exists()
        assert not (INSTALL_DIR / "tdd" / "old.md").exists()


class TestInstallGitValidation:
    def test_auto_switches_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")
        assert _fake_git.branch == "main"

    def test_succeeds_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "develop"
        register_source(git_repo, branch="develop")
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    def test_allows_dirty_repo_on_correct_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        assert_invoke("install", "tdd", "--offline")

    def test_errors_when_dirty_and_wrong_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _fake_git.branch = "other"
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_skill_not_in_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        fs.create_dir(SKILLS_DIR)

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    def test_pulls_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        assert_invoke("install", "tdd")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd", root=SKILLS_DIR)

        assert_invoke("install", "tdd", "--offline")

        assert _fake_git.pulled is False
