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


class TestProviderRemove:
    def test_removes_provider(self, git_repo: Path) -> None:
        reg = load_provider_registry()
        reg.register_provider("cursor", "/home/user/.cursor/skills")
        save_provider_registry(reg)

        result = assert_invoke("provider", "remove", "cursor")

        updated = load_provider_registry()
        assert "cursor" not in updated.providers
        assert_words_in_message(result.output, "removed", "cursor")

    def test_error_when_not_found(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    def test_allows_removing_claude(self, git_repo: Path) -> None:
        result = assert_invoke("provider", "remove", "claude")

        updated = load_provider_registry()
        assert "claude" not in updated.providers
        assert_words_in_message(result.output, "removed", "claude")
