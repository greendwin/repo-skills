from __future__ import annotations

from pathlib import Path

from repo_skills.console import reporter
from tests.cli.helper import assert_invoke


class TestDebugFlagWiring:
    def test_debug_flag_sets_reporter_debug(self, git_repo: Path) -> None:
        assert_invoke("--debug", "update", "--offline")
        assert reporter.debug is True

    def test_no_flag_leaves_reporter_debug_false(self, git_repo: Path) -> None:
        assert_invoke("update", "--offline")
        assert reporter.debug is False
