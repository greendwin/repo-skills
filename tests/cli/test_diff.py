from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import Baseline, InstalledSkill
from tests.cli.helper import (
    INSTALL_DIR,
    SKILLS_DIR,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    register_provider,
    register_source,
    save_manifest,
)

COMMIT = "abc1234"
CURSOR_DIR = Path("/home/user/.cursor/skills")


def _setup_tracked_with_baseline(
    fs: FakeFilesystem,
    git_repo: Path,
    fake_git: FakeGitRepo,
    *,
    installed_content: str = "# edited",
    baseline_content: str = "# original",
) -> None:
    register_source(git_repo)
    create_source_skill(fs, "tdd", content="# original")
    hashes = install_skill(fs, "tdd", content=baseline_content)
    save_manifest(
        {
            "tdd": InstalledSkill(
                source="my-project",
                baseline=Baseline(commit=COMMIT, files=hashes),
            )
        }
    )
    fake_git.files_at_commit[(COMMIT, "skills/tdd/SKILL.md")] = (
        baseline_content.encode()
    )
    (INSTALL_DIR / "tdd" / "SKILL.md").write_text(installed_content)


class TestDiffTrackedBaseline:
    def test_shows_diff_when_modified(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        _setup_tracked_with_baseline(
            fs,
            git_repo,
            _fake_git,
            baseline_content="# original",
            installed_content="# edited",
        )

        result = assert_invoke("diff", "tdd")
        assert "--- a/tdd/SKILL.md" in result.output
        assert "+++ b/tdd/SKILL.md" in result.output
        assert "-# original" in result.output
        assert "+# edited" in result.output

    def test_noop_when_unmodified(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        _setup_tracked_with_baseline(
            fs,
            git_repo,
            _fake_git,
            baseline_content="# original",
            installed_content="# original",
        )

        result = assert_invoke("diff", "tdd")
        assert "no differences" in result.output.lower()


class TestDiffTrackedNoBaseline:
    def test_diffs_against_source_on_disk(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source version")
        install_skill(fs, "tdd", content="# installed version")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", "tdd")
        assert "# source version" in result.output
        assert "# installed version" in result.output


class TestDiffUntracked:
    def test_diffs_untracked_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source version")
        install_skill(fs, "tdd", content="# installed version")

        result = assert_invoke("diff", "tdd")
        assert "# source version" in result.output
        assert "# installed version" in result.output


class TestDiffFromFlag:
    def test_selects_provider_with_from_flag(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_provider("cursor", str(CURSOR_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source version")
        install_skill(fs, "tdd", content="# installed version")
        install_skill(fs, "tdd", content="# cursor version", install_dir=CURSOR_DIR)

        result = assert_invoke("diff", "tdd", "--from", "cursor")
        assert "# cursor version" in result.output
        assert "# source version" in result.output


class TestDiffNotInstalled:
    def test_error_when_not_installed(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)

        result = assert_invoke("diff", "tdd", expect_error=True)
        assert "not installed" in result.exception.message.lower()


class TestDiffMissingSource:
    def test_error_when_source_no_longer_registered(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        install_skill(fs, "tdd")
        save_manifest({"tdd": InstalledSkill(source="deleted-source", baseline=None)})

        result = assert_invoke("diff", "tdd", expect_error=True)
        assert "deleted-source" in result.exception.message
        assert "no longer registered" in result.exception.message


class TestDiffMultiFile:
    def test_diffs_multiple_files(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)

        skill_src = SKILLS_DIR / "tdd"
        fs.create_file(skill_src / "SKILL.md", contents="# source skill")
        fs.create_file(skill_src / "prompt.md", contents="# source prompt")

        skill_inst = INSTALL_DIR / "tdd"
        fs.create_file(skill_inst / "SKILL.md", contents="# installed skill")
        fs.create_file(skill_inst / "prompt.md", contents="# installed prompt")

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", "tdd")
        assert "SKILL.md" in result.output
        assert "prompt.md" in result.output
        assert "# source skill" in result.output
        assert "# installed skill" in result.output


class TestDiffDeletedFromInstalled:
    def test_file_deleted_from_installed_shows_red_diff_baseline(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit=COMMIT,
                        files={"SKILL.md": hashes["SKILL.md"], "extra.md": "abc123"},
                    ),
                )
            }
        )
        _fake_git.files_at_commit[(COMMIT, "skills/tdd/SKILL.md")] = b"# original"
        _fake_git.files_at_commit[(COMMIT, "skills/tdd/extra.md")] = b"# extra baseline"
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# original")

        result = assert_invoke("diff", "tdd")
        assert "extra.md" in result.output
        assert "-# extra baseline" in result.output

    def test_file_deleted_from_installed_shows_red_diff_source(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)

        skill_src = SKILLS_DIR / "tdd"
        fs.create_file(skill_src / "SKILL.md", contents="# source skill")
        fs.create_file(skill_src / "extra.md", contents="# source extra")

        skill_inst = INSTALL_DIR / "tdd"
        fs.create_file(skill_inst / "SKILL.md", contents="# source skill")

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", "tdd")
        assert "extra.md" in result.output
        assert "# source extra" in result.output


class TestDiffAddedToInstalled:
    def test_file_added_to_installed_shows_green_diff(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source skill")

        skill_inst = INSTALL_DIR / "tdd"
        fs.create_file(skill_inst / "SKILL.md", contents="# source skill")
        fs.create_file(skill_inst / "new_file.md", contents="# added by user")

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", "tdd")
        assert "new_file.md" in result.output
        assert "+# added by user" in result.output


class TestDiffUntrackedNoSource:
    def test_error_when_orphaned_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# real skill")
        # Install an orphaned skill that is not in the manifest and not a source skill
        install_skill(fs, "orphan", content="# orphan content")

        result = assert_invoke("diff", "orphan", expect_error=True)
        assert "cannot find source" in result.exception.message.lower()


class TestDiffSourceRepoUnavailable:
    def test_error_when_source_repo_gone_baseline(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        _setup_tracked_with_baseline(
            fs,
            git_repo,
            _fake_git,
            baseline_content="# original",
            installed_content="# edited",
        )
        fs.remove_object(str(git_repo))

        result = assert_invoke("diff", "tdd", expect_error=True)
        assert "not available" in result.exception.message.lower()

    def test_error_when_source_repo_gone_no_baseline(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source version")
        install_skill(fs, "tdd", content="# installed version")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )
        fs.remove_object(str(git_repo))

        result = assert_invoke("diff", "tdd", expect_error=True)
        assert "not available" in result.exception.message.lower()

    def test_error_when_source_repo_gone_untracked(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source version")
        install_skill(fs, "tdd", content="# installed version")
        fs.remove_object(str(git_repo))

        result = assert_invoke("diff", "tdd", expect_error=True)
        assert "not available" in result.exception.message.lower()


class TestDiffRichMarkupEscape:
    def test_rich_markup_in_content_rendered_literally(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# source")
        install_skill(fs, "tdd", content="text with [red]markup[/red]")

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", "tdd")
        assert "[red]markup[/red]" in result.output


class TestDiffAutoDetect:
    def test_auto_detects_single_modified_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        _setup_tracked_with_baseline(
            fs,
            git_repo,
            _fake_git,
            baseline_content="# original",
            installed_content="# edited",
        )

        result = assert_invoke("diff")
        assert "-# original" in result.output
        assert "+# edited" in result.output

    def test_errors_when_multiple_modified(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        create_source_skill(fs, "review", content="# original")
        hashes_tdd = install_skill(fs, "tdd", content="# original")
        hashes_review = install_skill(fs, "review", content="# original")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit=COMMIT, files=hashes_tdd),
                ),
                "review": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit=COMMIT, files=hashes_review),
                ),
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited tdd")
        (INSTALL_DIR / "review" / "SKILL.md").write_text("# edited review")

        result = assert_invoke("diff", expect_error=True)

        assert_words_in_message(
            result.exception.message, "multiple skills", "review", "tdd"
        )
        assert_words_in_message(result.exception.message, "specify skill name")

    def test_errors_when_no_modified_skills(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes = install_skill(fs, "tdd", content="# original")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit=COMMIT, files=hashes),
                )
            }
        )

        result = assert_invoke("diff", expect_error=True)

        assert_words_in_message(result.exception.message, "no modified skills")

    def test_skills_without_baseline_not_considered_modified(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# different")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=None,
                )
            }
        )

        result = assert_invoke("diff", expect_error=True)

        assert_words_in_message(result.exception.message, "no modified skills")

    def test_from_flag_scopes_auto_detect_to_provider(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
    ) -> None:
        register_provider("claude", str(INSTALL_DIR))
        register_provider("cursor", str(CURSOR_DIR))
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# original")
        hashes_tdd = install_skill(fs, "tdd", content="# original")
        install_skill(fs, "tdd", content="# original", install_dir=CURSOR_DIR)
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit=COMMIT, files=hashes_tdd),
                )
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited in claude")
        (CURSOR_DIR / "tdd" / "SKILL.md").write_text("# edited in cursor")

        result = assert_invoke("diff", "--from", "cursor")

        assert "+# edited in cursor" in result.output
        assert "# edited in claude" not in result.output
