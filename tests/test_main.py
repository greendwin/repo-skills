from __future__ import annotations

import sys
from io import StringIO

import pytest

from repo_skills.cli._app import app
from repo_skills.debug import set_debug
from repo_skills.errors import AppError
from repo_skills.main import main


@pytest.fixture(autouse=True)
def _reset_debug() -> None:
    set_debug(False)


@app.command(name="__test-raise-app-error", hidden=True)
def _raise_app_error() -> None:
    raise AppError("something went wrong")


@app.command(name="__test-raise-unhandled", hidden=True)
def _raise_unhandled() -> None:
    raise RuntimeError("unexpected failure")


@app.command(name="__test-raise-chained-implicit", hidden=True)
def _raise_chained_implicit() -> None:
    try:
        raise PermissionError("access denied")
    except PermissionError:
        raise RuntimeError("git pull failed")


class RunMain:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch

    def __call__(self, *args: str) -> tuple[str, int]:
        buf = StringIO()
        self.monkeypatch.setattr(sys, "argv", ["skills", *args])
        self.monkeypatch.setattr(sys, "stdout", buf)

        try:
            main()
            return buf.getvalue(), 0
        except SystemExit as ex:
            return buf.getvalue(), int(ex.code or 0)


@pytest.fixture
def run_main(monkeypatch: pytest.MonkeyPatch) -> RunMain:
    return RunMain(monkeypatch)


def test_app_error_prints_formatted_message(run_main: RunMain) -> None:
    output, code = run_main("__test-raise-app-error")
    assert code == 1
    assert "Error:" in output
    assert "something went wrong" in output


def test_unhandled_exception_prints_formatted_message(run_main: RunMain) -> None:
    output, code = run_main("__test-raise-unhandled")
    assert code == 1
    assert "Error:" in output
    assert "unexpected failure" in output


def test_chained_exception_shows_caused_by(run_main: RunMain) -> None:
    output, code = run_main("__test-raise-chained-implicit")
    assert code == 1
    assert "Error:" in output
    assert "git pull failed" in output
    assert "caused by:" in output
    assert "access denied" in output


def test_debug_flag_shows_traceback_for_app_error(run_main: RunMain) -> None:
    output, code = run_main("--debug", "__test-raise-app-error")
    assert code == 1
    assert "Error:" in output
    assert "something went wrong" in output
    assert "Traceback" in output
    assert "AppError" in output


def test_debug_flag_shows_traceback_for_unhandled(run_main: RunMain) -> None:
    output, code = run_main("--debug", "__test-raise-unhandled")
    assert code == 1
    assert "Error:" in output
    assert "Traceback" in output
    assert "RuntimeError" in output


def test_no_traceback_without_debug(run_main: RunMain) -> None:
    output, code = run_main("__test-raise-app-error")
    assert code == 1
    assert "Traceback" not in output


@app.command(name="__test-raise-with-brackets", hidden=True)
def _raise_with_brackets() -> None:
    raise RuntimeError("[Errno 13] Permission denied")


def test_unhandled_exception_escapes_markup(run_main: RunMain) -> None:
    output, code = run_main("__test-raise-with-brackets")
    assert code == 1
    assert "[Errno 13]" in output
