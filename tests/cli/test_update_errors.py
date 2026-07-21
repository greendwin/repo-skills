from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._update as update_mod
from repo_skills.config import (
    Baseline,
    InstalledSkill,
    compute_file_hashes,
)
from tests.cli.helper import (
    INSTALL_DIR,
    FakeGitRepo,
    FakeGitRepoManager,
    SkillSetup,
    assert_invoke,
    assert_status_line,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_source,
    save_manifest,
)

SOURCE_A_ROOT = "/repos/source-a"
SOURCE_B_ROOT = "/repos/source-b"


class TestUpdateErrorMessages:
    def test_source_not_in_registry_is_skipped_source_unavailable(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        source = register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source=source.name, baseline=Baseline(commit="abc", files=hashes)
                ),
                "orphan": InstalledSkill(
                    source="unknown-source",
                    baseline=Baseline(commit="abc"),
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "orphan", "source", "unknown-source", "unavailable"
        )

        manifest = load_manifest()
        assert "orphan" in manifest.skills

    def test_skill_removed_from_source_shows_specific_error(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        # TODO: we should use `SourceConfig` from `register_source` instead of
        #       hardcoding "my-project" everywhere
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                ),
                "gone": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc")
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "error: skill removed from source")

        manifest = load_manifest()
        assert "gone" in manifest.skills


class TestUpdateBatchResilience:
    def test_modified_skill_does_not_block_others(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
            )
            .build()
        )
        _fake_git.branch_commits[("skills/review", "main")] = "c-review"
        (Path(INSTALL_DIR) / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdatePullFailure:
    def _setup_two_sources(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> dict[str, dict[str, str]]:
        fake_git_manager.install(FakeGitRepo(root=Path(SOURCE_A_ROOT), pull_fails=True))
        fake_b = FakeGitRepo(root=Path(SOURCE_B_ROOT))
        fake_b.branch_commits[("skills/bravo", "main")] = "c-bravo-new"
        fake_git_manager.install(fake_b)

        return (
            SkillSetup(fs, Path(SOURCE_A_ROOT))
            .add_skill(
                "alpha",
                source_name="source-a",
                source_root=Path(SOURCE_A_ROOT),
                source_content="# alpha v2",
                installed_content="# alpha v1",
            )
            .add_skill(
                "bravo",
                source_name="source-b",
                source_root=Path(SOURCE_B_ROOT),
                source_content="# bravo v2",
                installed_content="# bravo v1",
            )
            .build()
        )

    def test_pull_failure_does_not_block_other_sources(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        hashes = self._setup_two_sources(fs, fake_git_manager)

        result = assert_invoke("update")

        assert_status_line(result.output, "Pulling source-a", "failed")
        assert_words_in_message(result.output, "failed to pull")
        assert_words_in_message(result.output, "bravo", "updated")

        installed = (Path(INSTALL_DIR) / "bravo" / "SKILL.md").read_text()
        assert installed == "# bravo v2"

        manifest = load_manifest()
        bravo = manifest.skills["bravo"]
        assert bravo.baseline is not None
        refreshed = compute_file_hashes(Path(INSTALL_DIR) / "bravo")
        assert bravo.baseline.files == refreshed
        assert bravo.baseline.files != hashes["bravo"]

    def test_failed_source_skill_is_skipped_source_unavailable(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        hashes = self._setup_two_sources(fs, fake_git_manager)

        result = assert_invoke("update")

        assert_words_in_message(
            result.output, "alpha", "source", "source-a", "unavailable"
        )

        # source pull failed: install dir keeps the OLD content, not copied
        installed = (Path(INSTALL_DIR) / "alpha" / "SKILL.md").read_text()
        assert installed == "# alpha v1"

        manifest = load_manifest()
        alpha = manifest.skills["alpha"]
        assert alpha.baseline is not None
        # baseline left entirely untouched
        assert alpha.baseline.files == hashes["alpha"]

    def test_failed_source_skip_detach_reconciliation(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        fake_a = FakeGitRepo(root=Path(SOURCE_A_ROOT), pull_fails=True)
        fake_b = FakeGitRepo(root=Path(SOURCE_B_ROOT))
        fake_b.branch_commits[("skills/bravo", "main")] = "newcommit"
        fake_git_manager.install(fake_a)
        fake_git_manager.install(fake_b)

        (
            SkillSetup(fs, Path(SOURCE_A_ROOT))
            .add_skill(
                "alpha",
                source_name="source-a",
                source_root=Path(SOURCE_A_ROOT),
                commit="c-alpha",
                detached=True,
            )
            .add_skill(
                "bravo",
                source_name="source-b",
                source_root=Path(SOURCE_B_ROOT),
                commit="c-bravo",
                detached=True,
            )
            .build()
        )

        assert_invoke("update")

        manifest = load_manifest()
        assert manifest.skills["alpha"].detached is True
        assert manifest.skills["bravo"].detached is False

    def test_pull_failure_renders_cause_chain(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        fake_git_manager.install(
            FakeGitRepo(
                root=Path(SOURCE_A_ROOT),
                pull_fails=True,
                pull_cause="ssh handshake refused",
            )
        )
        fake_b = FakeGitRepo(root=Path(SOURCE_B_ROOT))
        fake_b.branch_commits[("skills/bravo", "main")] = "c-bravo-new"
        fake_git_manager.install(fake_b)

        (
            SkillSetup(fs, Path(SOURCE_A_ROOT))
            .add_skill(
                "alpha",
                source_name="source-a",
                source_root=Path(SOURCE_A_ROOT),
                source_content="# alpha v2",
                installed_content="# alpha v1",
            )
            .add_skill(
                "bravo",
                source_name="source-b",
                source_root=Path(SOURCE_B_ROOT),
                source_content="# bravo v2",
                installed_content="# bravo v1",
            )
            .build()
        )

        result = assert_invoke("update")

        assert_words_in_message(result.output, "caused by:", "ssh handshake refused")
        assert_words_in_message(result.output, "bravo", "updated")

    def test_debug_flag_shows_traceback_for_pull_failure(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        self._setup_two_sources(fs, fake_git_manager)

        result = assert_invoke("--debug", "update")

        assert "Traceback" in result.output
        assert "Error: Failed to pull from remote." in result.output.splitlines()

    def test_no_traceback_without_debug_for_pull_failure(
        self,
        fs: FakeFilesystem,
        fake_git_manager: FakeGitRepoManager,
    ) -> None:
        self._setup_two_sources(fs, fake_git_manager)

        result = assert_invoke("update")

        assert "Traceback" not in result.output


class TestUpdateExceptionHandling:
    def _setup_two_skills(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        fake_git: FakeGitRepo,
        *,
        cause: str = "",
    ) -> tuple[dict[str, str], dict[str, str]]:
        hashes = (
            SkillSetup(fs, git_repo)
            .add_skill("tdd", source_content="# tdd v2", installed_content="# tdd v1")
            .add_skill(
                "review",
                source_content="# review v2",
                installed_content="# review v1",
            )
            .build()
        )
        # both skills resolve a commit so failures come from the copy step
        fake_git.branch_commits[("skills/tdd", "main")] = "c-tdd"
        fake_git.branch_commits[("skills/review", "main")] = "c-review"

        real_compute = compute_file_hashes

        def _bomb(path: Path) -> dict[str, str]:
            if "tdd" in str(path) and "skills/tdd" in str(path):
                if cause:
                    try:
                        raise OSError(cause)
                    except OSError as inner:
                        raise RuntimeError("disk exploded") from inner
                raise RuntimeError("disk exploded")
            return real_compute(path)

        monkeypatch.setattr(update_mod, "compute_file_hashes", _bomb)
        return hashes["tdd"], hashes["review"]

    def test_unexpected_error_shows_message(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        _fake_git: FakeGitRepo,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch, _fake_git)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "error: disk exploded")
        assert_words_in_message(result.output, "review", "updated")

    def test_skill_failure_renders_cause_chain(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        _fake_git: FakeGitRepo,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch, _fake_git, cause="inode gone")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "caused by:", "inode gone")
        assert_words_in_message(result.output, "review", "updated")

    def test_manifest_not_updated_for_failed_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        _fake_git: FakeGitRepo,
    ) -> None:
        h1, _h2 = self._setup_two_skills(fs, git_repo, monkeypatch, _fake_git)

        assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.files == h1
        assert manifest.skills["tdd"].baseline.commit == "old"
        assert manifest.skills["review"].baseline is not None
        assert manifest.skills["review"].baseline.files != _h2

    def test_debug_flag_shows_traceback(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        _fake_git: FakeGitRepo,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch, _fake_git)

        result = assert_invoke("--debug", "update", "--offline")

        assert "Traceback" in result.output
        assert_words_in_message(result.output, "error: disk exploded")

    def test_no_traceback_without_debug(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        _fake_git: FakeGitRepo,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch, _fake_git)

        result = assert_invoke("update", "--offline")

        assert "Traceback" not in result.output
