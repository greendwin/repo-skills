from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import SourceRegistry, save_source_registry
from tests.cli.helper import (
    assert_invoke,
    assert_words_in_message,
    register_source,
)


class TestSourceList:
    @pytest.mark.usefixtures("git_repo")
    def test_shows_registered_sources(self) -> None:
        registry = SourceRegistry()
        registry.register_source("alpha", Path("/repos/alpha"))
        registry.register_source("beta", Path("/repos/beta"))
        save_source_registry(registry)

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "alpha", "/repos/alpha")
        assert_words_in_message(result.output, "beta", "/repos/beta")

    @pytest.mark.usefixtures("git_repo")
    def test_shows_message_when_empty(self) -> None:
        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "no sources")


class TestSourceListBranch:
    @pytest.mark.usefixtures("fs")
    def test_shows_pinned_branch(self, git_repo: Path) -> None:
        register_source(git_repo, name="my-project", branch="develop")

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "my-project", "develop")

    @pytest.mark.usefixtures("fs")
    def test_omits_branch_when_not_pinned(self, git_repo: Path) -> None:
        register_source(git_repo, name="my-project", branch="")

        result = assert_invoke("source", "list")

        assert "branch" not in result.output.lower()


class TestSourceListMissing:
    @pytest.mark.usefixtures("git_repo")
    def test_shows_missing_for_nonexistent_path(self) -> None:
        registry = SourceRegistry()
        registry.register_source("gone", Path("/repos/gone"))
        save_source_registry(registry)

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "gone", "(missing)")


class TestSourceListNotInited:
    @pytest.mark.usefixtures("git_repo")
    def test_shows_not_inited_when_no_config(self, fs: FakeFilesystem) -> None:
        source_path = Path("/repos/no-config")
        fs.create_dir(source_path)

        registry = SourceRegistry()
        registry.register_source("no-config", source_path)
        save_source_registry(registry)

        result = assert_invoke("source", "list")

        assert_words_in_message(result.output, "no-config", "(not-inited)")
