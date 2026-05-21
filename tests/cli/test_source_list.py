from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import SOURCES_REGISTRY_FILE, SourceEntry, SourceRegistry
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
    register_source,
)


class TestSourceList:
    def test_shows_registered_sources(self, git_repo: Path) -> None:
        registry = SourceRegistry(
            sources={
                "alpha": SourceEntry(path="/repos/alpha"),
                "beta": SourceEntry(path="/repos/beta"),
            }
        )
        registry.save(SOURCE_CONFIG_DIR / SOURCES_REGISTRY_FILE)

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "alpha", "/repos/alpha")
        assert_words_in_message(result.output, "beta", "/repos/beta")

    def test_shows_message_when_empty(self, git_repo: Path) -> None:
        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "no sources")


class TestSourceListBranch:
    def test_shows_pinned_branch(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo, name="my-project", branch="develop")

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "my-project", "develop")

    def test_omits_branch_when_not_pinned(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo, name="my-project", branch="")

        result = assert_invoke("source", "list")

        assert "branch" not in result.output.lower()
