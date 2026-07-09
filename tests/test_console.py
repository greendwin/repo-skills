from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from cli_error import CliError

from repo_skills.console import reporter
from repo_skills.git_real import RealGitRepo


@pytest.fixture(autouse=True)
def _reset_debug() -> None:
    reporter.debug = False


class TestDebugCmd:
    def test_prints_command_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reporter.debug = True
        reporter.debug_cmd(["git", "status"], Path("/repo"))
        captured = capsys.readouterr()
        assert "RUN: git status" in captured.err
        assert "CWD: /repo" in captured.err

    def test_silent_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        reporter.debug_cmd(["git", "status"], Path("/repo"))
        captured = capsys.readouterr()
        assert captured.err == ""


class TestDebugOutput:
    def test_prints_stdout_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reporter.debug = True
        reporter.debug_output("main\ndev", "")
        captured = capsys.readouterr()
        assert "STDOUT:" in captured.err
        assert "main" in captured.err
        assert "dev" in captured.err

    def test_prints_stderr_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reporter.debug = True
        reporter.debug_output("", "warning: something")
        captured = capsys.readouterr()
        assert "STDERR:" in captured.err
        assert "warning: something" in captured.err

    def test_silent_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        reporter.debug_output("output", "error")
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_skips_empty_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        reporter.debug = True
        reporter.debug_output("", "")
        captured = capsys.readouterr()
        assert captured.err == ""


class TestDebugTraceback:
    def test_prints_traceback_when_enabled(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reporter.debug = True
        try:
            raise ValueError("boom")
        except ValueError:
            reporter.debug_traceback()

        captured = capsys.readouterr()
        assert "ValueError" in captured.err
        assert "boom" in captured.err

    def test_silent_when_disabled(self, capsys: pytest.CaptureFixture[str]) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            reporter.debug_traceback()
        captured = capsys.readouterr()
        assert captured.err == ""


class TestGitRealDebugIntegration:
    def test_run_prints_debug_when_enabled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        reporter.debug = True
        git = RealGitRepo(tmp_path)
        git.current_branch()
        captured = capsys.readouterr()
        assert "RUN: git branch --show-current" in captured.err
        # `main` must land in the STDOUT block, not as an incidental match,
        # so a stdout-capture regression can't pass on a stray "main"
        assert "STDOUT:" in captured.err
        assert "main" in captured.err[captured.err.index("STDOUT:") :]

    def test_run_silent_when_disabled(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "-b", "main"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        git = RealGitRepo(tmp_path)
        git.current_branch()
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_run_shows_stderr_on_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        subprocess.run(
            ["git", "init", str(tmp_path)],
            capture_output=True,
            check=True,
        )

        reporter.debug = True
        git = RealGitRepo(tmp_path)
        with pytest.raises(CliError):
            git._run("log", "--bad-flag")
        captured = capsys.readouterr()
        assert "RUN: git log --bad-flag" in captured.err
