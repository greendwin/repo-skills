from __future__ import annotations

import sys
from io import StringIO

import pytest
from cli_error import CliError

from repo_skills.cli._app import app
from repo_skills.console import reporter
from repo_skills.main import main


@pytest.fixture(autouse=True)
def _reset_debug() -> None:
    reporter.debug = False


@app.command(name="__test-raise-app-error", hidden=True)
def _raise_app_error() -> None:
    raise CliError("something went wrong")


@app.command(name="__test-raise-unhandled", hidden=True)
def _raise_unhandled() -> None:
    raise RuntimeError("unexpected failure")


@app.command(name="__test-raise-chained-implicit", hidden=True)
def _raise_chained_implicit() -> None:
    try:
        raise PermissionError("access denied")
    except PermissionError:
        raise RuntimeError("git pull failed")


@app.command(name="__test-raise-app-error-with-prop-and-cause", hidden=True)
def _raise_app_error_with_prop_and_cause() -> None:
    cause = PermissionError("access denied")
    raise CliError("config is broken").prop_path(
        "path", "/etc/app/config.json"
    ) from cause


class RunMain:
    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch

    def __call__(self, *args: str) -> tuple[str, int]:
        out = StringIO()
        err = StringIO()
        self.monkeypatch.setattr(sys, "argv", ["skills", *args])
        self.monkeypatch.setattr(sys, "stdout", out)
        self.monkeypatch.setattr(sys, "stderr", err)

        try:
            main()
            return out.getvalue() + err.getvalue(), 0
        except SystemExit as ex:
            return out.getvalue() + err.getvalue(), int(ex.code or 0)


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


def test_app_error_renders_props_and_cause_chain(run_main: RunMain) -> None:
    # a typed CliError's props render alongside the caused-by chain
    output, code = run_main("__test-raise-app-error-with-prop-and-cause")
    assert code == 1
    assert "config is broken" in output
    assert "/etc/app/config.json" in output
    assert "caused by:" in output
    assert "access denied" in output


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
    assert "CliError" in output


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


def test_render_error_terminates_on_cyclic_cause_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", out)

    a = RuntimeError("first")
    b = RuntimeError("second")
    a.__cause__ = b
    b.__cause__ = a

    reporter.report_error(a)

    output = out.getvalue()
    assert "Error:" in output
    assert "first" in output
    assert output.count("caused by: second") == 1
    assert output.count("caused by: first") == 0
