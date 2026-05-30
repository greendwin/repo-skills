from __future__ import annotations

import subprocess
from pathlib import Path

from rich.markup import escape

from repo_skills.console import console, fmt_command, fmt_ident, fmt_path
from repo_skills.errors import AppError, FileNotInCommitError
from repo_skills.git import GitRepo


def _git_error(args: tuple[str, ...], output: str, repo_path: Path) -> AppError:
    cmd = " ".join(["git", *args])

    props = {"repo": fmt_path(repo_path)}

    branch_cmd = ["git", "branch", "--show-current"]
    console.debug_cmd(branch_cmd, repo_path)
    try:
        result = subprocess.run(
            branch_cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        branch = result.stdout.strip()
        console.debug_output(result.stdout.strip(), result.stderr.strip())
        if branch:
            props["branch"] = fmt_ident(branch)
    except subprocess.CalledProcessError as exc:
        console.debug_output("", (exc.stderr or "").strip())

    if output:
        props[""] = f"[dim]{escape(output)}[/dim]"

    return AppError(
        f"Git command failed: {fmt_command(cmd)}",
        props=props,
    )


class RealGitRepo:
    def __init__(self, repo_path: Path) -> None:
        self._path = repo_path

    @property
    def root(self) -> Path:
        return self._path

    def _run(self, *args: str) -> str:
        cmd = ["git", *args]
        console.debug_cmd(cmd, self._path)
        try:
            result = subprocess.run(
                cmd,
                cwd=self._path,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            output = (exc.stderr or exc.stdout or "").strip()
            console.debug_output("", output)
            raise _git_error(args, output, self._path) from exc

        console.debug_output(result.stdout.strip(), result.stderr.strip())
        return result.stdout.strip()

    def _run_bytes(self, *args: str) -> bytes:
        cmd = ["git", *args]
        console.debug_cmd(cmd, self._path)
        try:
            result = subprocess.run(
                cmd,
                cwd=self._path,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
            console.debug_output("", stderr)
            raise _git_error(args, stderr, self._path) from exc

        stderr = result.stderr.decode(errors="replace").strip() if result.stderr else ""
        console.debug_output("", stderr)
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

    def log_commits(self, path: str, max_count: int) -> list[str]:
        output = self._run("log", f"--max-count={max_count}", "--format=%H", "--", path)
        if not output:
            return []
        return output.splitlines()

    def get_file_at_commit(self, commit: str, path: str) -> bytes:
        try:
            return self._run_bytes("show", f"{commit}:{path}")
        except AppError as exc:
            if "not exist" in exc.message:
                raise FileNotInCommitError(commit, path) from exc
            raise

    def create_branch(self, name: str, from_commit: str) -> None:
        self._run("checkout", "-b", name, from_commit)

    def create_orphan_branch(self, name: str) -> None:
        self._run("checkout", "--orphan", name)
        try:
            self._run("rm", "-rf", ".")
        except AppError:
            pass

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

    def rebase_root(self, onto: str) -> bool:
        try:
            self._run("rebase", "--root", "--onto", onto)
        except AppError:
            if self._in_rebase():
                return False
            raise
        return True

    def is_rebasing(self) -> bool:
        return self._in_rebase()

    def rebase_continue(self) -> None:
        self._run("rebase", "--continue")

    def rebase_abort(self) -> None:
        self._run("rebase", "--abort")

    def merge(self, branch: str) -> bool:
        try:
            self._run("merge", branch)
        except AppError:
            if self._in_merge():
                return False
            raise
        return True

    def is_merging(self) -> bool:
        return self._in_merge()

    def merge_abort(self) -> None:
        self._run("merge", "--abort")

    def fast_forward(self, branch: str) -> None:
        self._run("merge", "--ff-only", branch)

    def delete_branch(self, name: str) -> None:
        self._run("branch", "-d", name)

    def list_branches(self, pattern: str) -> list[str]:
        try:
            output = self._run("branch", "--list", pattern)
        except AppError:
            return []
        return [
            line.strip().lstrip("* ") for line in output.splitlines() if line.strip()
        ]

    def get_commit_message(self, commit: str) -> str:
        return self._run("log", "-1", "--format=%s", commit)

    def is_ancestor(self, commit: str, branch: str) -> bool:
        try:
            self._run("merge-base", "--is-ancestor", commit, branch)
        except AppError:
            return False
        return True

    def commit_exists_in_any_branch(self, commit: str) -> bool:
        try:
            output = self._run("branch", "--contains", commit)
        except AppError:
            return False
        return output != ""

    def _in_rebase(self) -> bool:
        try:
            self._run("rev-parse", "--verify", "REBASE_HEAD")
            return True
        except AppError:
            return False

    def _in_merge(self) -> bool:
        return (self._path / ".git" / "MERGE_HEAD").exists()

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
