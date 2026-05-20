from __future__ import annotations

from pathlib import Path

from repo_skills.config import ProviderConfig, ProviderRegistry
from tests.cli.helper import (
    SOURCE_CONFIG_DIR,
    assert_invoke,
    assert_words_in_message,
)

PROVIDERS_FILE = SOURCE_CONFIG_DIR / "providers.json"


class TestProviderAdd:
    def test_adds_new_provider(self, git_repo: Path) -> None:
        result = assert_invoke(
            "provider", "add", "cursor", "--install-dir", "/home/user/.cursor/skills"
        )

        registry = ProviderRegistry.load(PROVIDERS_FILE)
        assert "cursor" in registry.providers
        assert registry.providers["cursor"].install_dir == "/home/user/.cursor/skills"
        assert_words_in_message(result.output, "added", "cursor")

    def test_error_when_duplicate_name(self, git_repo: Path) -> None:
        registry = ProviderRegistry(
            providers={
                "cursor": ProviderConfig(
                    name="cursor", install_dir="/home/user/.cursor/skills"
                )
            }
        )
        registry.save(PROVIDERS_FILE)

        result = assert_invoke(
            "provider",
            "add",
            "cursor",
            "--install-dir",
            "/other/path",
            expect_error=True,
        )

        assert_words_in_message(result.exception.message, "already exists")

    def test_error_when_adding_builtin_name(self, git_repo: Path) -> None:
        result = assert_invoke(
            "provider",
            "add",
            "claude",
            "--install-dir",
            "/some/path",
            expect_error=True,
        )

        assert_words_in_message(result.exception.message, "already exists")
