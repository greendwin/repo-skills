from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import load_source_registry, save_source_registry
from repo_skills.config.deprecated import (
    SKILL_MANIFEST_FILE,
    ManifestSkill,
    SkillManifest,
)
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
    register_source,
)


class TestSourceRemove:
    def test_removes_source_from_registry(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo, name="alpha")
        registry = load_source_registry()
        registry.register_source("beta", Path("/repos/beta"))
        save_source_registry(registry)

        result = assert_invoke("source", "remove", "alpha")

        updated = load_source_registry()
        assert "alpha" not in updated.sources
        assert "beta" in updated.sources

        assert_words_in_message(result.output, "removed", "alpha")

    def test_error_when_source_not_found(self, git_repo: Path) -> None:
        result = assert_invoke("source", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    def test_blocked_when_skills_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo, name="alpha")

        manifest = SkillManifest(skills={"tdd": ManifestSkill(source="alpha")})
        manifest.save(SOURCE_CONFIG_DIR / SKILL_MANIFEST_FILE)

        result = assert_invoke("source", "remove", "alpha", expect_error=True)

        assert_words_in_message(result.exception.message, "installed skills")

        updated = load_source_registry()
        assert "alpha" in updated.sources
