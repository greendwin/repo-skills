from __future__ import annotations

import subprocess
from pathlib import Path

from repo_skills._git import GitRepo


class RealGitRepo:
    def __init__(self, repo_path: Path) -> None:
        self._path = repo_path

    def _run(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self._path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def pull(self) -> None:
        self._run("pull")

    def get_main_branch(self) -> str:
        try:
            ref = self._run("symbolic-ref", "refs/remotes/origin/HEAD")
            return ref.removeprefix("refs/remotes/origin/")
        except subprocess.CalledProcessError:
            return "main"

    def current_branch(self) -> str:
        return self._run("branch", "--show-current")

    def is_clean(self) -> bool:
        return self._run("status", "--porcelain") == ""

    def get_skill_commit(self, skill_name: str) -> str:
        return self._run("log", "-1", "--format=%H", "--", f"skills/{skill_name}")

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

            committed_content = subprocess.run(
                ["git", "show", f"{commit}:{rel_path}"],
                cwd=self._path,
                capture_output=True,
                check=True,
            ).stdout
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
