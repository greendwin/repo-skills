from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from skill_cli.discovery import find_repo_skills_dir


def test_find_repo_skills_dir_from_git_root(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir("/projects/agent-skills/.git")
    fs.create_dir("/projects/agent-skills/skills/tdd")

    result = find_repo_skills_dir(cwd=Path("/projects/agent-skills"))
    assert result == Path("/projects/agent-skills/skills")


def test_find_repo_skills_dir_from_subdirectory(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir("/projects/agent-skills/.git")
    fs.create_dir("/projects/agent-skills/skills/tdd")
    fs.create_dir("/projects/agent-skills/some/nested/dir")

    result = find_repo_skills_dir(cwd=Path("/projects/agent-skills/some/nested/dir"))
    assert result == Path("/projects/agent-skills/skills")


def test_find_repo_skills_dir_returns_none_outside_repo(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir("/tmp/random")

    result = find_repo_skills_dir(cwd=Path("/tmp/random"))
    assert result is None


def test_find_repo_skills_dir_falls_back_to_manifest(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir("/tmp/random")
    fs.create_dir("/elsewhere/agent-skills/skills/tdd")

    manifest_path = Path("/home/user/.claude/skills/.skill-install.json")
    fs.create_file(
        manifest_path,
        contents='{"repo_path": "/elsewhere/agent-skills", "skills": {}}',
    )

    result = find_repo_skills_dir(
        cwd=Path("/tmp/random"),
        manifest_path=manifest_path,
    )
    assert result == Path("/elsewhere/agent-skills/skills")
