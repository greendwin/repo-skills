from __future__ import annotations

from cli_error import CliError

from repo_skills.cli._app import app
from tests.cli.helper import assert_invoke


@app.command(name="__test-app-error", hidden=True)
def _raise_app_error() -> None:
    raise CliError("something went wrong")


def test_app_error_exit_code() -> None:
    result = assert_invoke("__test-app-error", expect_error=True)
    assert result.message == "something went wrong"
