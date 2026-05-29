from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._deps as deps_mod
from repo_skills.config import (
    InstalledSkill,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.errors import AppError
from tests.cli.helper import (
    INSTALL_DIR,
    SKILLS_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_fake_git,
    install_skill,
    load_manifest,
    register_provider,
    register_source,
    save_manifest,
    uninstall_fake_git,
)

COMMIT = "abc1234"
CURSOR_DIR = Path("/home/user/.cursor/skills")
OTHER_REPO_ROOT = Path("/repos/other-project")


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo(
        commits={"tdd": COMMIT},
        ancestors={(COMMIT, "main"): True},
    )
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def _setup_diverged_skill(
    fs: FakeFilesystem, git_repo: Path, *, branch: str = ""
) -> None:
    register_source(git_repo, branch=branch)
    create_source_skill(fs, "tdd", content="# original")
    hashes = install_skill(fs, "tdd", content="# original")
    save_manifest(
        {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
    )
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
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        register_provider("cursor", str(CURSOR_DIR))

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
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        register_provider("cursor", str(CURSOR_DIR))

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
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        register_provider("cursor", str(CURSOR_DIR))

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
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "synced", "nothing to merge")

    def test_errors_when_multiple_providers_have_untracked_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        register_provider("cursor", str(CURSOR_DIR))

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple providers", "--from"
        )

    def test_from_flag_selects_provider_for_untracked_skill(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        register_provider("cursor", str(CURSOR_DIR))
        (CURSOR_DIR / "tdd" / "SKILL.md").write_text("# edited in cursor")

        result = assert_invoke("merge", "tdd", "--offline", "--from", "cursor")

        assert_words_in_message(result.output, "merge", "complete")


class TestBaseCommitSearch:
    def test_exact_hash_match(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("merge", "tdd", "--offline")

        assert "skill-merge/claude/tdd" in _fake_git.orphan_branches
        assert _fake_git.rebase_root_onto == "main"
        assert_words_in_message(result.output, "merge", "complete")

    def test_search_base_ignores_stored_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.commit_messages = {"bbb222": "feat: add tdd skill"}

        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "bbb222"
        assert_words_in_message(result.output, "merge", "complete")

    def test_search_base_reports_found_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = (
            b"# totally different\nline2\nline3"
        )
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.commit_messages = {
            "aaa111": "fix: update tdd",
            "bbb222": "feat: add tdd skill",
        }

        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert "bbb222" in result.output
        assert "exact match" in result.output
        assert "feat: add tdd skill" in result.output

    def test_search_base_reports_distance_for_closest(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = b"# original-ish"
        _fake_git.commit_messages = {"aaa111": "chore: tweak tdd"}

        result = assert_invoke("merge", "tdd", "--offline")

        assert "aaa111" in result.output
        assert "distance:" in result.output
        assert "chore: tweak tdd" in result.output

    def test_search_base_skips_commit_with_missing_file(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        # First commit is missing the file (no entry in files_at_commit),
        # second commit has the exact match.
        _fake_git.commit_logs["skills/tdd"] = ["aaa111", "bbb222"]
        # aaa111 has no file entry -> FileNotInCommitError
        _fake_git.files_at_commit[("bbb222", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.commit_messages = {
            "aaa111": "broken commit",
            "bbb222": "feat: add tdd skill",
        }

        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "bbb222"
        assert_words_in_message(result.output, "merge", "complete")

    def test_search_base_propagates_unexpected_error(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111"]
        # Inject a generic AppError by using a custom side effect
        _orig = _fake_git.get_file_at_commit

        def _boom(commit: str, path: str) -> bytes:
            if commit == "aaa111":
                raise AppError("unexpected git failure")
            return _orig(commit, path)

        _fake_git.get_file_at_commit = _boom  # type: ignore[method-assign]

        result = assert_invoke(
            "merge", "tdd", "--search-base", "--offline", expect_error=True
        )

        assert "unexpected git failure" in result.exception.message


class TestCommitReachability:
    def test_commit_on_other_branch_errors_with_search_base_hint(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.ancestors[(COMMIT, "main")] = False
        _fake_git.reachable_commits.add(COMMIT)

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert "--search-base" in result.exception.message

    def test_dangling_commit_auto_searches(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.ancestors[(COMMIT, "main")] = False

        _fake_git.commit_logs["skills/tdd"] = ["found111"]
        _fake_git.files_at_commit[("found111", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.commit_messages = {"found111": "feat: add tdd"}

        result = assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "found111"
        assert "dangling" in result.output.lower()
        assert_words_in_message(result.output, "merge", "complete")

    def test_search_base_bypasses_reachability(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.ancestors[(COMMIT, "main")] = False
        _fake_git.reachable_commits.add(COMMIT)

        _fake_git.commit_logs["skills/tdd"] = ["found111"]
        _fake_git.files_at_commit[("found111", "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.commit_messages = {"found111": "feat: add tdd"}

        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "found111"
        assert_words_in_message(result.output, "merge", "complete")


class TestResolveBaseCommit:
    def test_search_base_orphan_announces_rebase(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        """When --search-base finds no base commit, output mentions rebase."""
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        # No commit_logs -> _find_base_commit returns None
        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert "skill-merge/claude/tdd" in _fake_git.orphan_branches
        assert_words_in_message(result.output, "no", "base", "commit", "rebase")
        assert_words_in_message(result.output, "merge", "complete")

    def test_search_base_distance_escapes_markup(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        """Distance message must escape rich markup in commit messages."""
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/tdd"] = ["aaa111"]
        _fake_git.files_at_commit[("aaa111", "skills/tdd/SKILL.md")] = b"# original-ish"
        _fake_git.commit_messages = {"aaa111": "fix [red]broken[/red] thing"}

        result = assert_invoke("merge", "tdd", "--offline")

        # Markup tags must appear literally, not be interpreted by rich
        assert "[red]" in result.output
        assert "[/red]" in result.output

    def test_search_base_with_category_subfolder(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        """Base-commit search works when skill is under a category subfolder."""
        register_source(git_repo)
        create_source_skill(
            fs, "tdd", content="# original", root=SKILLS_DIR / "testing"
        )
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        _fake_git.commit_logs["skills/testing/tdd"] = ["cat111"]
        _fake_git.files_at_commit[("cat111", "skills/testing/tdd/SKILL.md")] = (
            b"# original"
        )
        _fake_git.commit_messages = {"cat111": "feat: add tdd skill"}

        result = assert_invoke("merge", "tdd", "--search-base", "--offline")

        assert _fake_git.created_branches["skill-merge/claude/tdd"] == "cat111"
        assert "cat111" in result.output
        assert "exact match" in result.output


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

    def test_registers_non_diverged_mergeable_skill(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        _fake_git.commits["tdd"] = "source-commit-abc"

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "synced")
        manifest = load_manifest()
        assert "tdd" in manifest.skills
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.commit == "source-commit-abc"
        assert entry.files == compute_file_hashes(INSTALL_DIR / "tdd")

    def test_diverged_mergeable_has_correct_manifest_after_merge(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")
        _fake_git.commits["tdd"] = "merged-commit-xyz"

        assert_invoke("merge", "tdd", "--offline")

        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.commit == "merged-commit-xyz"
        assert entry.files == compute_file_hashes(INSTALL_DIR / "tdd")
        assert not entry.detached

    def test_diverged_mergeable_copies_to_source(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        assert_invoke("merge", "tdd", "--offline")

        source_skill = git_repo / "skills" / "tdd" / "SKILL.md"
        assert source_skill.read_text() == "# edited by user"

    def test_non_diverged_mergeable_does_not_create_merge_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original")

        assert_invoke("merge", "tdd", "--offline")

        assert _fake_git.created_branches == {}
        assert _fake_git.orphan_branches == []
        assert _fake_git.committed_messages == []

    def test_reattaches_detached_skill_when_all_in_sync(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", commit=COMMIT, files=hashes, detached=True
                )
            }
        )
        _fake_git.commits["tdd"] = "reattached-commit"

        result = assert_invoke("merge", "tdd", "--offline")

        assert_words_in_message(result.output, "synced")
        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert not entry.detached
        assert entry.commit == "reattached-commit"

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

    def test_untracked_errors_when_multiple_sources_without_flag(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        other_repo = OTHER_REPO_ROOT
        fs.create_dir(other_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", other_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), other_repo
        )
        create_source_skill(fs, "tdd", content="# original")
        create_source_skill(fs, "tdd", content="# original", root=other_repo / "skills")
        install_skill(fs, "tdd", content="# original")

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple sources", "--source"
        )

    def test_untracked_falls_through_to_orphan_when_source_lacks_skill(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "tdd", content="# from provider")

        result = assert_invoke("merge", "tdd", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "merge", "complete")
        source_skill = git_repo / "skills" / "tdd" / "SKILL.md"
        assert source_skill.read_text() == "# from provider"

    def test_untracked_selects_source_with_flag(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        other_repo = OTHER_REPO_ROOT
        fs.create_dir(other_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", other_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), other_repo
        )
        create_source_skill(fs, "tdd", content="# original")
        create_source_skill(fs, "tdd", content="# original", root=other_repo / "skills")
        install_skill(fs, "tdd", content="# original")
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("merge", "tdd", "--offline", "--source", "my-project")

        assert_words_in_message(result.output, "merge", "complete")


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
        fs.create_dir(other_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", other_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), other_repo
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
        fs.create_dir(other_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", other_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), other_repo
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

    def test_errors_when_multiple_providers_have_orphan_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "my-new-skill", content="# brand new")
        install_skill(fs, "my-new-skill", content="# brand new", install_dir=CURSOR_DIR)
        register_provider("cursor", str(CURSOR_DIR))

        result = assert_invoke("merge", "my-new-skill", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple providers", "--from"
        )

    def test_from_flag_selects_provider_for_orphan_skill(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        install_skill(fs, "my-new-skill", content="# from claude")
        install_skill(
            fs, "my-new-skill", content="# from cursor", install_dir=CURSOR_DIR
        )
        register_provider("cursor", str(CURSOR_DIR))

        result = assert_invoke("merge", "my-new-skill", "--offline", "--from", "cursor")

        assert_words_in_message(result.output, "merge", "complete")
        source_skill = git_repo / "skills" / "my-new-skill" / "SKILL.md"
        assert source_skill.read_text() == "# from cursor"


class TestMergeValidation:

    def test_errors_when_same_merge_already_in_progress(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)
        _fake_git.branches = ["skill-merge/claude/tdd"]

        result = assert_invoke(
            "merge", "tdd", "--offline", "--from", "claude", expect_error=True
        )

        assert_words_in_message(
            result.exception.message, "merge already in progress", "--continue"
        )

    def test_errors_when_same_merge_in_progress_auto_provider(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)
        _fake_git.branches = ["skill-merge/claude/tdd"]

        result = assert_invoke("merge", "tdd", "--offline", expect_error=True)

        assert_words_in_message(
            result.exception.message, "merge already in progress", "--continue"
        )

    def test_allows_merge_when_different_merge_in_progress(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_diverged_skill(fs, git_repo)
        _fake_git.branches = ["skill-merge/claude/other-skill"]

        assert_invoke("merge", "tdd", "--offline")

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
        _fake_git.ancestors[(COMMIT, "develop")] = True
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
    save_manifest(
        {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
    )
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
        assert_words_in_message(result.exception.message, "skills merge")

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
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
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


def _install_multi_git(repos: dict[Path, FakeGitRepo]) -> None:
    def factory(path: Path) -> FakeGitRepo:
        path_str = str(path)
        for root, fake in repos.items():
            if path_str == str(root):
                return fake
        raise AssertionError(f"No fake git for {path}")

    deps_mod._git_repo_factory = factory


class TestDetectMergeRepo:
    def test_continue_prefers_cwd_source_over_manifest_order(
        self,
        fs: FakeFilesystem,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fs.create_dir(SOURCE_REPO_ROOT / ".git")
        fs.create_dir(OTHER_REPO_ROOT / ".git")

        cwd_git = FakeGitRepo(
            root=OTHER_REPO_ROOT,
            branch="skill-merge/claude/review",
            commits={"review": "merged-commit"},
        )
        other_git = FakeGitRepo(root=SOURCE_REPO_ROOT)
        _install_multi_git({OTHER_REPO_ROOT: cwd_git, SOURCE_REPO_ROOT: other_git})

        monkeypatch.chdir(OTHER_REPO_ROOT)

        registry = SourceRegistry()
        registry.register_source("my-project", SOURCE_REPO_ROOT)
        registry.register_source("other-project", OTHER_REPO_ROOT)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), SOURCE_REPO_ROOT
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), OTHER_REPO_ROOT
        )

        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {
                "tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes),
            }
        )
        create_source_skill(
            fs, "review", content="# merged", root=OTHER_REPO_ROOT / "skills"
        )
        hashes_review = install_skill(fs, "review", content="# original")
        manifest = load_manifest()
        manifest.register_skill(
            "review",
            source_name="other-project",
            commit="rev123",
            files=hashes_review,
        )
        save_skill_manifest(manifest)

        result = assert_invoke("merge", "--continue")

        assert cwd_git.ff_targets == ["skill-merge/claude/review"]
        assert_words_in_message(result.output, "merge", "complete")

    def test_continue_scans_sources_when_cwd_outside(
        self,
        fs: FakeFilesystem,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fs.create_dir(SOURCE_REPO_ROOT / ".git")
        fs.create_dir("/somewhere/else")

        source_git = FakeGitRepo(
            root=SOURCE_REPO_ROOT,
            branch="skill-merge/claude/tdd",
            commits={"tdd": "merged-commit"},
        )
        _install_multi_git({SOURCE_REPO_ROOT: source_git})

        monkeypatch.chdir("/somewhere/else")

        register_source(SOURCE_REPO_ROOT, name="my-project")
        create_source_skill(fs, "tdd", content="# merged")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "--continue")

        assert source_git.ff_targets == ["skill-merge/claude/tdd"]
        assert_words_in_message(result.output, "merge", "complete")

    def test_continue_errors_when_multiple_sources_have_merge_branches(
        self,
        fs: FakeFilesystem,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fs.create_dir(SOURCE_REPO_ROOT / ".git")
        fs.create_dir(OTHER_REPO_ROOT / ".git")
        fs.create_dir("/somewhere/else")

        git_a = FakeGitRepo(
            root=SOURCE_REPO_ROOT,
            branches=["skill-merge/claude/tdd"],
        )
        git_b = FakeGitRepo(
            root=OTHER_REPO_ROOT,
            branches=["skill-merge/claude/review"],
        )
        _install_multi_git({SOURCE_REPO_ROOT: git_a, OTHER_REPO_ROOT: git_b})

        monkeypatch.chdir("/somewhere/else")

        registry = SourceRegistry()
        registry.register_source("my-project", SOURCE_REPO_ROOT)
        registry.register_source("other-project", OTHER_REPO_ROOT)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), SOURCE_REPO_ROOT
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), OTHER_REPO_ROOT
        )

        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "--continue", expect_error=True)

        assert_words_in_message(result.exception.message, "multiple source repos")

    def test_continue_cwd_disambiguates_multiple_merge_repos(
        self,
        fs: FakeFilesystem,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        fs.create_dir(SOURCE_REPO_ROOT / ".git")
        fs.create_dir(OTHER_REPO_ROOT / ".git")

        cwd_git = FakeGitRepo(
            root=SOURCE_REPO_ROOT,
            branch="skill-merge/claude/tdd",
            commits={"tdd": "merged-commit"},
        )
        other_git = FakeGitRepo(
            root=OTHER_REPO_ROOT,
            branches=["skill-merge/claude/review"],
        )
        _install_multi_git({SOURCE_REPO_ROOT: cwd_git, OTHER_REPO_ROOT: other_git})

        monkeypatch.chdir(SOURCE_REPO_ROOT)

        registry = SourceRegistry()
        registry.register_source("my-project", SOURCE_REPO_ROOT)
        registry.register_source("other-project", OTHER_REPO_ROOT)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills"), SOURCE_REPO_ROOT
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dir="skills"), OTHER_REPO_ROOT
        )

        create_source_skill(fs, "tdd", content="# merged")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=COMMIT, files=hashes)}
        )

        result = assert_invoke("merge", "--continue")

        assert cwd_git.ff_targets == ["skill-merge/claude/tdd"]
        assert_words_in_message(result.output, "merge", "complete")
