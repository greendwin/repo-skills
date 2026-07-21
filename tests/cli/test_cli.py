import pytest

import repo_skills.cli._app as app_mod
from tests.cli.helper import InvokeResult, NoopResult, assert_invoke


def test_version_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    # mock metadata lookup: real package metadata is masked under fake fs
    monkeypatch.setattr(app_mod, "version", lambda _: "9.9.9")
    result = assert_invoke("--version")
    assert isinstance(result, NoopResult)
    assert "9.9.9" in result.output


def test_help_lists_all_commands() -> None:
    result = assert_invoke("--help")
    assert isinstance(result, InvokeResult)
    for cmd in ("install", "update", "uninstall", "source"):
        assert cmd in result.output
