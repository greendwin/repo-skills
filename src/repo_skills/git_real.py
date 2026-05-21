from __future__ import annotations

import subprocess
from pathlib import Path

from rich.markup import escape

from repo_skills.errors import AppError
from repo_skills.git import GitRepo


def _git_error(args: tuple[str, ...], output: str, repo_path: Path) -> AppError:
    cmd = " ".join(["git", *args])
    msg = f"git command failed: [cyan]{cmd}[/cyan]"
    msg += f"\n  repo: [cyan]{repo_path}[/cyan]"
    try:
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        if branch:
            msg += f"\n  branch: [cyan]{branch}[/cyan]"
    except subprocess.CalledProcessError:
        pass

    if output:
        msg += f"\n[dim]{escape(output)}[/dim]"
    return AppError(msg)


class RealGitRepo:
    def __init__(self, repo_path: Path) -> None:
        self._path = repo_path

    @property
    def path(self) -> Path:
        return self._path

    def _run(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self._path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip()
            raise _git_error(args, output, self._path) from exc

        return result.stdout.strip()

    def _run_bytes(self, *args: str) -> bytes:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self._path,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
            raise _git_error(args, stderr, self._path) from exc

        return result.stdout

    def pull(self) -> None:
        try:
            self._run("pull")
        except AppError as exc:
            if "no tracking information" not in exc.message:
                raise
            branch = self.current_branch()
            self._run("pull", "origin", branch)

    def get_main_branch(self) -> str:
        try:
            ref = self._run("symbolic-ref", "refs/remotes/origin/HEAD")
            return ref.removeprefix("refs/remotes/origin/")
        except AppError:
            return "main"

    def current_branch(self) -> str:
        return self._run("branch", "--show-current")

    def is_clean(self) -> bool:
        return self._run("status", "--porcelain") == ""

    def get_skill_commit(self, skill_name: str) -> str:
        return self._run("log", "-1", "--format=%H", "--", f"skills/{skill_name}")

    def create_branch(self, name: str, from_commit: str) -> None:
        self._run("checkout", "-b", name, from_commit)

    def checkout(self, branch: str) -> None:
        self._run("checkout", branch)

    def commit_all(self, message: str) -> None:
        self._run("add", "-A")
        self._run("commit", "-m", message)

    def rebase(self, onto: str) -> bool:
        try:
            self._run("rebase", onto)
        except AppError:
            if self._in_rebase():
                return False
            raise
        return True

    def _in_rebase(self) -> bool:
        try:
            self._run("rev-parse", "--verify", "REBASE_HEAD")
            return True
        except AppError:
            return False

    def verify_commit_content(self, commit: str, skill_name: str) -> bool:
        skill_path = f"skills/{skill_name}"
        listing = self._run("ls-tree", "-r", "--name-only", commit, skill_path)
        if not listing:
            return False

        committed_files = listing.splitlines()
        working_dir = self._path / skill_path

        for rel_path in committed_files:
            local_file = self._path / rel_path
            if not local_file.exists():
                return False

            committed_content = self._run_bytes("show", f"{commit}:{rel_path}")
            if local_file.read_bytes() != committed_content:
                return False

        local_files = {
            str(f.relative_to(self._path))
            for f in working_dir.rglob("*")
            if f.is_file()
        }
        if local_files != set(committed_files):
            return False

        return True


def _check_implements_protocol(_: GitRepo) -> None:
    pass


_check_implements_protocol(RealGitRepo(Path(".")))
