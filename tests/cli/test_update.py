from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import InstalledSkill
from tests.cli.helper import (
    INSTALL_DIR,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_provider,
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
            {"tdd": InstalledSkill(source="my-project", commit="old", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="old", files=baseline)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")


class TestUpdateAutoInstallsNewProvider:
    def test_copies_to_new_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        assert_invoke("update", "--offline")

        assert _fake_git.pulled is False


class TestUpdateValidation:
    def test_errors_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline", expect_error=True)

        assert_words_in_message(result.exception.message, "not on the pinned branch")
        assert_words_in_message(result.exception.message, "source init --branch")

    def test_succeeds_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "develop"
        register_source(git_repo, branch="develop")
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "up to date")

    def test_errors_when_repo_is_dirty(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
            {"tdd": InstalledSkill(source="my-project", commit="abc", files=hashes)}
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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "updated")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateDetached:
    def test_unreachable_commit_marks_skill_detached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit="abc123", files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "detached")

    def test_previously_detached_skill_recovers(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", commit="abc123", files=hashes, detached=True
                )
            }
        )
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert_words_in_message(result.output, "tdd", "recovered")

    def test_no_message_when_still_detached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", commit="abc123", files=hashes, detached=True
                )
            }
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert "detached" not in result.output.lower()
        assert "recovered" not in result.output.lower()

    def test_no_detached_check_when_commit_is_none(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {"tdd": InstalledSkill(source="my-project", commit=None, files=hashes)}
        )

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert "detached" not in result.output.lower()


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
                "tdd": InstalledSkill(source="my-project", commit="old", files=h1),
                "review": InstalledSkill(source="my-project", commit="old", files=h2),
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")
