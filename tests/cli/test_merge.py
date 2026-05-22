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
    SOURCE_CONFIG_FILE,
    SOURCES_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
    SkillEntry,
    SourceConfig,
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
    create_source_skill,
    install_fake_git,
    install_skill,
    load_manifest,
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


def _setup_diverged_skill(
    fs: FakeFilesystem, git_repo: Path, *, branch: str = ""
) -> None:
    register_source(git_repo, branch=branch)
    create_source_skill(fs, "tdd", content="# original")
    hashes = install_skill(fs, "tdd", content="# original")
    save_manifest({"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)})
    (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")


class TestMergeStart:
    def test_creates_branch_and_merges(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == COMMIT
        assert _fake_git.merged_branch == "skill-merge/claude/tdd"

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
        assert_words_in_message(result.output, "merge", "complete")

    def test_auto_finalizes_on_clean_merge(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.ff_targets == []
        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        installed = (INSTALL_DIR / "tdd" / "SKILL.md").read_text()
        assert installed == "# edited by user"
        manifest = load_manifest()
        assert manifest.skills["tdd"].files == compute_file_hashes(INSTALL_DIR / "tdd")
        assert_words_in_message(result.output, "merge", "complete")

    def test_prompts_continue_on_conflict(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.merge_clean = False
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "conflicts", "--continue")
        assert _fake_git.ff_targets == []
        assert _fake_git.deleted_branches == []


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
        assert_words_in_message(result.output, "merge", "complete")

    def test_reports_synced_when_no_provider_diverged(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "synced", "nothing to merge")


class TestBaseCommitSearch:
    def test_exact_hash_match(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = b"# wrong"
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original"

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "bbb222"
        assert_words_in_message(result.output, "merge", "complete")

    def test_closest_match_when_no_exact(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = (
            b"# totally different\nline2\nline3"
        )
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original-ish"

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "bbb222"
        assert_words_in_message(result.output, "merge", "complete")

    def test_closest_match_with_missing_file(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        fs.create_file(INSTALL_DIR / "tdd" / "extra.md", contents="line1\nline2\nline3")
        hashes = compute_file_hashes(INSTALL_DIR / "tdd")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.files_at_commit[("bbb222", "skills/tdd/extra.md")] = (
            b"line1\nline2\nline3"
        )

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "bbb222"
        assert_words_in_message(result.output, "merge", "complete")

    def test_orphan_branch_when_no_commits(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("merge", "tdd", "--offline")

        assert "skill-merge/claude/tdd" in _fake_git.orphan_branches
        assert _fake_git.rebase_root_onto == "main"
        assert_words_in_message(result.output, "merge", "complete")


class TestMergeUntracked:
    def test_merges_untracked_mergeable_skill(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "merge", "complete")
        manifest = load_manifest()
        assert "tdd" in manifest.skills
        assert manifest.skills["tdd"].source == "my-project"

    def test_merges_untracked_orphan_with_single_source(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "unknown-skill", content="# something")

        result = assert_invoke("merge", "unknown-skill", "--offline")

        assert_words_in_message(result.output, "merge", "complete")
        manifest = load_manifest()
        assert "unknown-skill" in manifest.skills
        assert manifest.skills["unknown-skill"].source == "my-project"


class TestMergeOrphan:
    def test_single_source_auto_picks_and_merges(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "my-new-skill", content="# brand new")

        result = assert_invoke("merge", "my-new-skill", "--offline")

        source_skill = git_repo / "skills" / "my-new-skill" / "SKILL.md"
        assert source_skill.read_text() == "# brand new"
        assert_words_in_message(result.output, "merge", "complete")
        manifest = load_manifest()
        assert "my-new-skill" in manifest.skills
        assert manifest.skills["my-new-skill"].source == "my-project"

    def test_errors_when_multiple_sources_without_flag(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        other_repo = Path("/repos/other-project")
        fs.create_dir(other_repo)
        registry = SourceRegistry(
            sources={
                "my-project": SourceEntry(path=str(git_repo)),
                "other-project": SourceEntry(path=str(other_repo)),
            }
        )
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        SourceConfig(name="my-project").save(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        SourceConfig(name="other-project").save(
            other_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        install_skill(fs, "my-new-skill", content="# brand new")

        result = assert_invoke("merge", "my-new-skill", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple sources", "--source"
        )

    def test_source_flag_selects_target(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        other_repo = Path("/repos/other-project")
        fs.create_dir(other_repo)
        registry = SourceRegistry(
            sources={
                "my-project": SourceEntry(path=str(git_repo)),
                "other-project": SourceEntry(path=str(other_repo)),
            }
        )
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)
        SourceConfig(name="my-project").save(
            git_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        SourceConfig(name="other-project").save(
            other_repo / REPO_SKILLS_DIR_NAME / SOURCE_CONFIG_FILE
        )
        install_skill(fs, "my-new-skill", content="# brand new")

        result = assert_invoke(
            "merge", "my-new-skill", "--offline", "--source", "other-project"
        )

        source_skill = other_repo / "skills" / "my-new-skill" / "SKILL.md"
        assert source_skill.read_text() == "# brand new"
        assert_words_in_message(result.output, "merge", "complete")
        manifest = load_manifest()
        assert manifest.skills["my-new-skill"].source == "other-project"

    def test_no_commit_copies_without_committing(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "my-new-skill", content="# brand new")

        assert_invoke("merge", "my-new-skill", "--offline", "--no-commit")

        source_skill = git_repo / "skills" / "my-new-skill" / "SKILL.md"
        assert source_skill.read_text() == "# brand new"
        assert _fake_git.committed_messages == []
        manifest = load_manifest()
        assert "my-new-skill" not in manifest.skills

    def test_manifest_has_correct_commit_and_hashes(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "my-new-skill", content="# brand new")
        _fake_git.commits["my-new-skill"] = "orphan-commit-123"

        assert_invoke("merge", "my-new-skill", "--offline")

        manifest = load_manifest()
        entry = manifest.skills["my-new-skill"]
        assert entry.commit == "orphan-commit-123"
        assert entry.files == compute_file_hashes(INSTALL_DIR / "my-new-skill")

    def test_errors_when_not_in_any_provider(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not installed")


class TestMergeValidation:

    def test_errors_when_merge_already_in_progress(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)
        _fake_git.branches = ["skill-merge/claude/tdd"]

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "merge already in progress", "--continue"
        )

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

    def test_auto_checkouts_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        _setup_diverged_skill(fs, git_repo, branch="develop")

        assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.merged_branch == "skill-merge/claude/tdd"

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

        assert len(_fake_git.committed_messages) == 1
        assert_words_in_message(
            _fake_git.committed_messages[0], "chore:", "merge", "tdd", "claude"
        )

    def test_copies_provider_files_to_source(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        assert_invoke("merge", "tdd", "--offline")

        source_skill = git_repo / "skills" / "tdd" / "SKILL.md"
        assert source_skill.read_text() == "# edited by user"


def _setup_merge_branch(
    fs: FakeFilesystem,
    git_repo: Path,
    fake_git: FakeGitRepo,
    *,
    branch: str = "skill-merge/claude/tdd",
    content: str = "# merged",
    source_branch: str = "",
) -> None:
    register_source(git_repo, branch=source_branch)
    hashes = install_skill(fs, "tdd", content="# original")
    save_manifest({"tdd": SkillEntry(source="my-project", commit=COMMIT, files=hashes)})
    create_source_skill(fs, "tdd", content=content)
    fake_git.branch = branch


class TestMergeContinue:
    def test_happy_path(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)

        result = assert_invoke("merge", "--continue")

        assert _fake_git.ff_targets == ["skill-merge/claude/tdd"]
        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        installed = (INSTALL_DIR / "tdd" / "SKILL.md").read_text()
        assert installed == "# merged"
        manifest = load_manifest()
        assert manifest.skills["tdd"].files == compute_file_hashes(INSTALL_DIR / "tdd")
        assert_words_in_message(result.output, "merge", "complete")

    def test_continues_rebase_when_in_progress(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.rebasing = True

        assert_invoke("merge", "--continue")

        assert _fake_git.rebasing is False

    def test_dirty_allowed_during_merge(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.merging = True
        _fake_git.clean = False

        result = assert_invoke("merge", "--continue")

        assert_words_in_message(result.output, "merge", "complete")

    def test_errors_when_multiple_merge_branches(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, branch="main")
        _fake_git.branches = [
            "skill-merge/claude/tdd",
            "skill-merge/cursor/tdd",
        ]

        result = assert_invoke("merge", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "multiple merge branches")

    def test_errors_when_no_merge_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, branch="main")

        result = assert_invoke("merge", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "no merge branch")

    def test_errors_when_repo_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.clean = False

        result = assert_invoke("merge", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "uncommitted changes")

    def test_errors_when_ff_fails(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.ff_fails = True

        result = assert_invoke("merge", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "fast-forward failed")

    def test_updates_manifest_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.commits["tdd"] = "newcommit789"

        assert_invoke("merge", "--continue")

        manifest = load_manifest()
        assert manifest.skills["tdd"].commit == "newcommit789"

    def test_dirty_allowed_during_rebase(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.rebasing = True
        _fake_git.clean = False

        result = assert_invoke("merge", "--continue")

        assert_words_in_message(result.output, "merge", "complete")

    def test_empty_merge_already_up_to_date(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, content="# original")

        result = assert_invoke("merge", "--continue")

        assert_words_in_message(result.output, "already up to date")
        assert _fake_git.deleted_branches == ["skill-merge/claude/tdd"]

    def test_auto_detects_merge_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, branch="main")
        _fake_git.branches = ["skill-merge/claude/tdd"]

        result = assert_invoke("merge", "--continue")

        assert _fake_git.ff_targets == ["skill-merge/claude/tdd"]
        assert_words_in_message(result.output, "merge", "complete")

    def test_finalize_targets_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, source_branch="develop")

        assert_invoke("merge", "--continue")

        assert _fake_git.branch == "develop"


class TestMergeNoCommit:
    def test_creates_branch_and_copies_without_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline", "--no-commit")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == COMMIT
        source_skill = git_repo / "skills" / "tdd" / "SKILL.md"
        assert source_skill.read_text() == "# edited by user"
        assert _fake_git.committed_messages == []
        assert _fake_git.rebased_onto is None
        assert _fake_git.ff_targets == []
        assert _fake_git.deleted_branches == []
        assert_words_in_message(result.output, "--continue")

    def test_short_flag(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline", "-n")

        assert _fake_git.committed_messages == []
        assert_words_in_message(result.output, "--continue")


class TestMergeRebase:
    def test_rebase_flag_uses_rebase_instead_of_merge(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline", "--rebase")

        assert _fake_git.rebased_onto == "main"
        assert _fake_git.merged_branch is None
        assert _fake_git.ff_targets == ["skill-merge/claude/tdd"]
        assert_words_in_message(result.output, "merge", "complete")

    def test_rebase_conflict_prompts_continue(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.rebase_clean = False
        _setup_diverged_skill(fs, git_repo)

        result = assert_invoke("merge", "tdd", "--offline", "--rebase")

        assert_words_in_message(result.output, "rebase", "conflicts", "--continue")
        assert _fake_git.ff_targets == []
        assert _fake_git.deleted_branches == []

    def test_rebase_orphan_ignores_flag(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": SkillEntry(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("merge", "tdd", "--offline", "--rebase")

        assert "skill-merge/claude/tdd" in _fake_git.orphan_branches
        assert _fake_git.rebase_root_onto == "main"
        assert_words_in_message(result.output, "merge", "complete")


class TestMergeAbort:
    def test_aborts_rebase_and_cleans_up(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.rebasing = True

        result = assert_invoke("merge", "--abort")

        assert _fake_git.rebasing is False
        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        assert_words_in_message(result.output, "aborted")

    def test_aborts_merge_and_cleans_up(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.merging = True

        result = assert_invoke("merge", "--abort")

        assert _fake_git.merging is False
        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        assert_words_in_message(result.output, "aborted")

    def test_errors_when_abort_and_continue(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)

        result = assert_invoke("merge", "--abort", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "--abort", "--continue")

    def test_works_when_no_rebase_in_progress(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)

        result = assert_invoke("merge", "--abort")

        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        assert_words_in_message(result.output, "aborted")

    def test_abort_targets_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, source_branch="develop")

        assert_invoke("merge", "--abort")

        assert _fake_git.branch == "develop"

    def test_errors_when_no_merge_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git, branch="main")

        result = assert_invoke("merge", "--abort", expect_error=True)

        assert_words_in_message(result.exception.message, "no merge branch")

    def test_works_when_repo_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_merge_branch(fs, git_repo, _fake_git)
        _fake_git.clean = False

        result = assert_invoke("merge", "--abort")

        assert _fake_git.branch == "main"
        assert "skill-merge/claude/tdd" in _fake_git.deleted_branches
        assert_words_in_message(result.output, "aborted")
