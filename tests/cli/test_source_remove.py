from __future__ import annotations

from pathlib import Path

from repo_skills.config import SkillEntry as ManifestSkillEntry
from repo_skills.config import (
    SkillManifest,
    SourceEntry,
    SourceRegistry,
)
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
)


class TestSourceRemove:
    def test_removes_source_from_registry(self, git_repo: Path) -> None:
        registry = SourceRegistry(
            sources={
                "alpha": SourceEntry(path="/repos/alpha"),
                "beta": SourceEntry(path="/repos/beta"),
            }
        )
        registry.save(SOURCE_CONFIG_DIR / "sources.json")

        result = assert_invoke("source", "remove", "alpha")

        updated = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        assert "alpha" not in updated.sources
        assert "beta" in updated.sources

        assert_words_in_message(result.output, "removed", "alpha")

    def test_error_when_source_not_found(self, git_repo: Path) -> None:
        result = assert_invoke("source", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    def test_blocked_when_skills_installed(self, git_repo: Path) -> None:
        registry = SourceRegistry(sources={"alpha": SourceEntry(path="/repos/alpha")})
        registry.save(SOURCE_CONFIG_DIR / "sources.json")

        manifest = SkillManifest(skills={"tdd": ManifestSkillEntry(source="alpha")})
        manifest.save(SOURCE_CONFIG_DIR / "skill-manifest.json")

        result = assert_invoke("source", "remove", "alpha", expect_error=True)

        assert_words_in_message(result.exception.message, "installed skills")

        updated = SourceRegistry.load(SOURCE_CONFIG_DIR / "sources.json")
        assert "alpha" in updated.sources
