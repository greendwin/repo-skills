from __future__ import annotations

from pathlib import Path

from repo_skills.config import SourceEntry, SourceRegistry
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
)


class TestSourceList:
    def test_shows_registered_sources(self, git_repo: Path) -> None:
        registry = SourceRegistry(
            sources={
                "alpha": SourceEntry(path="/repos/alpha"),
                "beta": SourceEntry(path="/repos/beta"),
            }
        )
        registry.save(SOURCE_CONFIG_DIR / "sources.json")

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "alpha", "/repos/alpha")
        assert_words_in_message(result.output, "beta", "/repos/beta")

    def test_shows_message_when_empty(self, git_repo: Path) -> None:
        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "no sources")
