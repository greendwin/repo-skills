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
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_source,
    save_manifest,
)


class TestUpdateErrorMessages:
    def test_source_not_in_registry_shows_specific_error(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                ),
                "orphan": InstalledSkill(
                    source="unknown-source",
                    baseline=Baseline(commit="abc"),
                ),
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "error", "source", "unknown-source", "not found"
        )

        manifest = load_manifest()
        assert "orphan" in manifest.skills

    def test_skill_removed_from_source_shows_specific_error(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd")
        hashes = install_skill(fs, "tdd")
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
        self, fs: FakeFilesystem, git_repo: Path
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
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# user edit")

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "tdd", "skipped")
        assert_words_in_message(result.output, "review", "updated")


class TestUpdateExceptionHandling:
    def _setup_two_skills(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
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

        real_compute = compute_file_hashes

        def _bomb(path: Path) -> dict[str, str]:
            if "tdd" in str(path) and "skills/tdd" in str(path):
                raise RuntimeError("disk exploded")
            return real_compute(path)

        monkeypatch.setattr(update_mod, "compute_file_hashes", _bomb)
        return hashes["tdd"], hashes["review"]

    def test_unexpected_error_shows_message(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "error: disk exploded")
        assert_words_in_message(result.output, "review", "updated")

    def test_manifest_not_updated_for_failed_skill(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        h1, _h2 = self._setup_two_skills(fs, git_repo, monkeypatch)

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
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("--debug", "update", "--offline")

        assert "Traceback" in result.output
        assert_words_in_message(result.output, "error: disk exploded")

    def test_no_traceback_without_debug(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._setup_two_skills(fs, git_repo, monkeypatch)

        result = assert_invoke("update", "--offline")

        assert "Traceback" not in result.output
