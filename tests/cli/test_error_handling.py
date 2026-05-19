from __future__ import annotations

from repo_skills.cli._app import app
from repo_skills.errors import AppError
from tests.cli.helper import assert_invoke


@app.command(name="__test-app-error", hidden=True)
def _raise_app_error() -> None:
    raise AppError("something went wrong")


def test_app_error_exit_code() -> None:
    result = assert_invoke("__test-app-error", expect_error=True)
    assert result.exception.message == "something went wrong"
