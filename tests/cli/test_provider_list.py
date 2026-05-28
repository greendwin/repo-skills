from __future__ import annotations

from pathlib import Path

from repo_skills.config import (
    load_provider_registry,
    save_provider_registry,
)
from tests.cli.helper import (
    assert_invoke,
    assert_words_in_message,
)


class TestProviderList:
    def test_shows_default_provider(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude")

    def test_shows_all_providers(self, git_repo: Path) -> None:
        reg = load_provider_registry()
        reg.register("cursor", "/home/user/.cursor/skills")
        save_provider_registry(reg)

        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude")
        assert_words_in_message(result.output, "cursor", "/home/user/.cursor/skills")
