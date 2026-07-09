from __future__ import annotations

from pathlib import Path

import pytest

from repo_skills.config import (
    load_provider_registry,
    save_provider_registry,
)
from tests.cli.helper import (
    assert_invoke,
    assert_words_in_message,
)


class TestProviderAdd:
    @pytest.mark.usefixtures("git_repo")
    def test_adds_new_provider(self) -> None:
        result = assert_invoke(
            "provider", "add", "cursor", "--install-dir", "/home/user/.cursor/skills"
        )

        reg = load_provider_registry()
        assert reg.is_registered("cursor")
        assert reg.require("cursor").install_path == Path("/home/user/.cursor/skills")
        assert_words_in_message(result.output, "added", "cursor")

    @pytest.mark.usefixtures("git_repo")
    def test_error_when_duplicate_name(self) -> None:
        reg = load_provider_registry()
        reg.register("cursor", "/home/user/.cursor/skills")
        save_provider_registry(reg)

        result = assert_invoke(
            "provider",
            "add",
            "cursor",
            "--install-dir",
            "/other/path",
            expect_error=True,
        )

        assert_words_in_message(result.message, "already exists")

    @pytest.mark.usefixtures("git_repo")
    def test_error_when_adding_builtin_name(self) -> None:
        result = assert_invoke(
            "provider",
            "add",
            "claude",
            "--install-dir",
            "/some/path",
            expect_error=True,
        )

        assert_words_in_message(result.message, "already exists")
