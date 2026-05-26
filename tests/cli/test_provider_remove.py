from __future__ import annotations

from pathlib import Path

from repo_skills.config.deprecated import (
    PROVIDERS_REGISTRY_FILE,
    ProviderConfig,
    ProviderRegistry,
)
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
)

PROVIDERS_FILE = SOURCE_CONFIG_DIR / PROVIDERS_REGISTRY_FILE


class TestProviderRemove:
    def test_removes_provider(self, git_repo: Path) -> None:
        registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(
                    name="cursor", install_dir="/home/user/.cursor/skills"
                )
            }
        )
        registry.save(PROVIDERS_FILE)

        result = assert_invoke("provider", "remove", "cursor")

        updated = ProviderRegistry.load(PROVIDERS_FILE)
        assert "cursor" not in updated.providers
        assert_words_in_message(result.output, "removed", "cursor")

    def test_error_when_not_found(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    def test_error_when_removing_builtin(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "remove", "claude", expect_error=True)

        assert_words_in_message(result.exception.message, "cannot remove", "built-in")
