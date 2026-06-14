from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import (
    INSTALL_DIR,
    FakeGitRepo,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    install_skill,
    register_provider,
)


class TestUpdatePerProviderOutput:
    def test_mixed_status_shows_per_provider_lines(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            latest_commit="c-tdd",
        ).build()

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# user edit", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        lines = result.output.splitlines()
        claude_lines = [line for line in lines if "claude" in line]
        cursor_lines = [line for line in lines if "cursor" in line]
        assert len(claude_lines) == 1
        assert len(cursor_lines) == 1
        assert_words_in_message(claude_lines[0], "claude", "updated")
        assert_words_in_message(cursor_lines[0], "cursor", "skipped")

    def test_all_providers_updated_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            latest_commit="c-tdd",
        ).build()

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd v1", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_all_providers_skipped_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            latest_commit="c-tdd",
        ).build()
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")
        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# user edit", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "skipped")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_all_providers_up_to_date_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd",
            installed_content="# tdd",
            commit="abc",
            latest_commit="abc",
        ).build()

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd", install_dir=cursor_dir)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "up-to-date")
        assert "claude" not in result.output.lower()
        assert "cursor" not in result.output.lower()

    def test_single_provider_shows_single_line(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            latest_commit="c-tdd",
        ).build()

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "updated")
        assert "claude" not in result.output.lower()

    def test_per_provider_lines_with_recovered(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        # claude copy matches source (up-to-date); cursor is absent (fresh install).
        # Both providers are in sync, so the formerly-detached skill recovers.
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            source_content="# tdd",
            installed_content="# tdd",
            commit="abc123",
            detached=True,
        ).build()

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

        _fake_git.branch_commits[("skills/tdd", "main")] = "newcommit"

        result = assert_invoke("update", "--offline")

        lines = result.output.splitlines()
        claude_lines = [line for line in lines if "claude" in line]
        cursor_lines = [line for line in lines if "cursor" in line]
        assert len(claude_lines) == 1
        assert len(cursor_lines) == 1
        assert_words_in_message(claude_lines[0], "claude", "up-to-date")
        assert_words_in_message(cursor_lines[0], "cursor", "updated")
        assert_words_in_message(result.output, "recovered")
