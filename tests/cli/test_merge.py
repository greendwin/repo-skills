from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
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
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_fake_git,
    install_skill,
    register_source,
    save_manifest,
    uninstall_fake_git,
)

COMMIT = "abc1234"
CURSOR_DIR = Path("/home/user/.cursor/skills")


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo(commits={"tdd": COMMIT})
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def _setup_diverged_skill(fs: FakeFilesystem, git_repo: Path) -> None:
    register_source(git_repo)
    create_source_skill(fs, "tdd", content="# original")
    hashes = install_skill(fs, "tdd", content="# original")
    save_manifest({"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)})
    (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")


class TestMergeStart:
    def test_creates_branch_and_starts_rebase(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "--continue")
        assert _fake_git.created_branches["skill-merge/claude/tdd"] == COMMIT
        assert _fake_git.branch == "skill-merge/claude/tdd"
        assert _fake_git.rebased_onto == "main"

    def test_auto_detects_diverged_provider(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)}
        )
        ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(CURSOR_DIR))
            }
        ).save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited in claude")

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == COMMIT
        assert_words_in_message(result.output, "--continue")


class TestMergeProviderResolution:
    def test_errors_when_multiple_providers_diverged(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)}
        )
        ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(CURSOR_DIR))
            }
        ).save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited in claude")
        (CURSOR_DIR / "tdd" / "SKILL.md").write_text("# edited in cursor")

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple providers", "--from"
        )

    def test_selects_provider_with_from_flag(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)}
        )
        ProviderRegistry(
            providers={
                "cursor": ProviderConfig(name="cursor", install_dir=str(CURSOR_DIR))
            }
        ).save(SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE)

        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited in claude")
        (CURSOR_DIR / "tdd" / "SKILL.md").write_text("# edited in cursor")

        result = assert_invoke("merge", "tdd", "--from", "cursor", "--offline")

        assert _fake_git.created_branches["skill-merge/cursor/tdd"] == COMMIT
        assert_words_in_message(result.output, "--continue")

    def test_errors_when_no_provider_diverged(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "nothing to merge")


class TestMergeValidation:
    def test_errors_when_commit_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# edited")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "no base commit")

    def test_errors_when_skill_not_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")

    def test_errors_when_repo_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_pulls_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.pulled is False

    def test_auto_checkouts_main_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        assert "skill-merge/claude/tdd" in _fake_git.created_branches

    def test_auto_commit_message(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.committed_messages == ["chore: merge tdd from claude"]

    def test_copies_provider_files_to_source(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        source_skill = git_repo / "skills" / "tdd" / "SKILL.md"
        assert source_skill.read_text() == "# edited by user"
