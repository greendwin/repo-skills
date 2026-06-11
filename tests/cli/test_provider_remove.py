from __future__ import annotations

import pytest

from repo_skills.config import (
    load_provider_registry,
    save_provider_registry,
)
from tests.cli.helper import (
    assert_invoke,
    assert_words_in_message,
)


class TestProviderRemove:
    @pytest.mark.usefixtures("git_repo")
    def test_removes_provider(self) -> None:
        reg = load_provider_registry()
        reg.register("cursor", "/home/user/.cursor/skills")
        save_provider_registry(reg)

        result = assert_invoke("provider", "remove", "cursor")

        updated = load_provider_registry()
        assert not updated.is_registered("cursor")
        assert_words_in_message(result.output, "removed", "cursor")

    @pytest.mark.usefixtures("git_repo")
    def test_error_when_not_found(self) -> None:
        result = assert_invoke("provider", "remove", "nonexistent", expect_error=True)

        assert_words_in_message(result.exception.message, "not found")

    @pytest.mark.usefixtures("git_repo")
    def test_allows_removing_claude(self) -> None:
        result = assert_invoke("provider", "remove", "claude")

        updated = load_provider_registry()
        assert not updated.is_registered("claude")
        assert_words_in_message(result.output, "removed", "claude")
