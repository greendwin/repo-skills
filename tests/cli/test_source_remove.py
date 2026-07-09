from __future__ import annotations

from pathlib import Path

import pytest

from repo_skills.config import (
    InstalledSkill,
    load_source_registry,
    save_source_registry,
)
from tests.cli.helper import (
    assert_invoke,
    assert_words_in_message,
    load_manifest,
    register_source,
    save_manifest,
)


class TestSourceRemove:
    @pytest.mark.usefixtures("fs")
    def test_removes_source_from_registry(self, git_repo: Path) -> None:
        register_source(git_repo, name="alpha")
        registry = load_source_registry()
        registry.register_source("beta", Path("/repos/beta"))
        save_source_registry(registry)

        result = assert_invoke("source", "remove", "alpha")

        updated = load_source_registry()
        assert "alpha" not in updated.sources
        assert "beta" in updated.sources

        assert_words_in_message(result.output, "removed", "alpha")

    @pytest.mark.usefixtures("git_repo")
    def test_error_when_source_not_found(self) -> None:
        result = assert_invoke("source", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.message, "not found")

    @pytest.mark.usefixtures("fs")
    def test_blocked_when_skills_installed(self, git_repo: Path) -> None:
        register_source(git_repo, name="alpha")

        save_manifest({"tdd": InstalledSkill(source="alpha")})

        result = assert_invoke("source", "remove", "alpha", expect_error=True)

        assert_words_in_message(result.message, "installed skills")

        updated = load_source_registry()
        assert "alpha" in updated.sources

    @pytest.mark.usefixtures("fs")
    def test_force_removes_source_and_clears_manifest(self, git_repo: Path) -> None:
        register_source(git_repo, name="alpha")

        save_manifest(
            {
                "tdd": InstalledSkill(source="alpha"),
                "review": InstalledSkill(source="alpha"),
            }
        )

        assert_invoke("source", "remove", "alpha", "--force")

        updated = load_source_registry()
        assert "alpha" not in updated.sources

        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert "review" not in manifest.skills

    @pytest.mark.usefixtures("fs")
    def test_force_without_installed_skills(self, git_repo: Path) -> None:
        register_source(git_repo, name="alpha")

        result = assert_invoke("source", "remove", "alpha", "--force")

        updated = load_source_registry()
        assert "alpha" not in updated.sources
        assert_words_in_message(result.output, "removed", "alpha")

    @pytest.mark.usefixtures("fs")
    def test_force_output_message(self, git_repo: Path) -> None:
        register_source(git_repo, name="alpha")

        save_manifest(
            {
                "tdd": InstalledSkill(source="alpha"),
            }
        )

        result = assert_invoke("source", "remove", "alpha", "--force")

        assert_words_in_message(result.output, "unregistered", "tdd")
        assert_words_in_message(result.output, "removed", "alpha")
