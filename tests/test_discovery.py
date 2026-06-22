from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.discovery import (
    DetectKind,
    DetectResult,
    detect_skills_dir,
    find_repo_skills_dir,
    has_any_skill,
)


def test_require_path_returns_path_for_single() -> None:
    result = DetectResult(DetectKind.SINGLE, Path("/repo/claude/skills"))
    assert result.require_path() == Path("/repo/claude/skills")


def test_require_path_raises_when_path_absent() -> None:
    result = DetectResult(DetectKind.NONE, None)
    with pytest.raises(AssertionError):
        result.require_path()


def test_detect_skills_dir_single_common_parent(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "claude/skills/grill-me/SKILL.md")
    fs.create_file(root / "claude/skills/tdd/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.SINGLE
    assert result.path == root / "claude/skills"


def test_detect_skills_dir_ambiguous(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "claude/skills/grill-me/SKILL.md")
    fs.create_file(root / "copilot/foo/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.AMBIGUOUS
    assert result.path is None


def test_detect_skills_dir_none(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "src/module.py")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.NONE
    assert result.path is None


def test_detect_skills_dir_deep_nesting(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "a/b/c/skill/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.SINGLE
    assert result.path == root / "a/b/c"


def test_detect_skills_dir_ignores_dot_dirs(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / ".hidden/skill/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.NONE
    assert result.path is None


def test_detect_skills_dir_ignores_nested_dot_dirs(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "pkg/skill/SKILL.md")
    fs.create_file(root / "pkg/.venv/lib/innerskill/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.SINGLE
    assert result.path == root / "pkg"


def test_detect_skills_dir_ignores_nested_skill_file(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "pkg/skill/SKILL.md")
    fs.create_file(root / "pkg/skill/inner/SKILL.md")

    result = detect_skills_dir(root)
    assert result.kind is DetectKind.SINGLE
    assert result.path == root / "pkg"


def test_has_any_skill_finds_nested_skill(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "a/b/c/skill/SKILL.md")

    assert has_any_skill(root) is True


def test_has_any_skill_returns_false_without_skill(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "src/module.py")

    assert has_any_skill(root) is False


def test_has_any_skill_ignores_dot_dirs(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / ".hidden/skill/SKILL.md")

    assert has_any_skill(root) is False


def test_has_any_skill_with_nested_skill_file(fs: FakeFilesystem) -> None:
    root = Path("/repo")
    fs.create_file(root / "pkg/skill/SKILL.md")
    fs.create_file(root / "pkg/skill/inner/SKILL.md")

    assert has_any_skill(root) is True


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

    manifest_path = Path("/home/user/.claude/skills/.skills-manifest.json")
    fs.create_file(
        manifest_path,
        contents='{"repo_path": "/elsewhere/agent-skills", "skills": {}}',
    )

    result = find_repo_skills_dir(
        cwd=Path("/tmp/random"),
        manifest_path=manifest_path,
    )
    assert result == Path("/elsewhere/agent-skills/skills")
