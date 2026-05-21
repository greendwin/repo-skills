from __future__ import annotations

from pathlib import Path

from repo_skills.config import PROVIDERS_REGISTRY_FILE, ProviderConfig, ProviderRegistry
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
)

PROVIDERS_FILE = SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE


class TestProviderList:
    def test_shows_builtin_by_default(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude", "built-in")

    def test_shows_all_providers(self, git_repo: Path) -> None:
        registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(
                    name="cursor", install_dir="/home/user/.cursor/skills"
                )
            }
        )
        registry.save(PROVIDERS_FILE)

        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude", "built-in")
        assert_words_in_message(result.output, "cursor", "/home/user/.cursor/skills")
