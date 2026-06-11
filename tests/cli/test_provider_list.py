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


class TestProviderList:
    @pytest.mark.usefixtures("git_repo")
    def test_shows_default_provider(self) -> None:
        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude")

    @pytest.mark.usefixtures("git_repo")
    def test_shows_all_providers(self) -> None:
        reg = load_provider_registry()
        reg.register("cursor", "/home/user/.cursor/skills")
        save_provider_registry(reg)

        result = assert_invoke("provider", "list")

        assert_words_in_message(result.output, "claude")
        assert_words_in_message(result.output, "cursor", "/home/user/.cursor/skills")
