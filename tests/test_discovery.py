from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.discovery import (
    DetectKind,
    DetectResult,
    detect_skills_dir,
    find_repo_skills_dir,
    has_any_skill,
    normalize_repo_dir,
    path_within,
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


def test_path_within_equal_to_root(fs: FakeFilesystem) -> None:
    fs.create_dir("/projects/repo")

    assert path_within(Path("/projects/repo"), Path("/projects/repo")) is True


def test_path_within_nested_under_root(fs: FakeFilesystem) -> None:
    fs.create_dir("/projects/repo/skills/tdd")

    assert (
        path_within(Path("/projects/repo/skills/tdd"), Path("/projects/repo")) is True
    )


def test_path_within_escaping_sibling(fs: FakeFilesystem) -> None:
    fs.create_dir("/projects/repo")
    fs.create_dir("/projects/sibling")

    assert (
        path_within(Path("/projects/repo/../sibling"), Path("/projects/repo")) is False
    )


def test_path_within_prefix_sibling_is_not_inside(fs: FakeFilesystem) -> None:
    fs.create_dir("/projects/repo")
    fs.create_dir("/projects/repo-2")

    assert path_within(Path("/projects/repo-2"), Path("/projects/repo")) is False


def test_path_within_symlink_is_not_followed(fs: FakeFilesystem) -> None:
    # containment is lexical: a symlink that physically points outside the root
    # is still inside it, because its path text stays under the root and the
    # link target is never resolved
    root = Path("/projects/repo")
    fs.create_dir(root)
    fs.create_dir("/outside/escape")
    fs.create_symlink("/projects/repo/link", "/outside/escape")

    assert path_within(Path("/projects/repo/link"), root) is True


def test_path_within_absolute_outside_is_false(fs: FakeFilesystem) -> None:
    fs.create_dir("/projects/repo")
    fs.create_dir("/other/place")

    assert path_within(Path("/other/place"), Path("/projects/repo")) is False


def test_path_within_collapses_dotdot_lexically() -> None:
    # ``..`` is collapsed textually (no filesystem access), so a traversal that
    # lands back under the root counts as inside even for non-existent paths
    assert (
        path_within(Path("/projects/repo/skills/../other"), Path("/projects/repo"))
        is True
    )


def test_path_within_relative_inputs_normalized_against_base() -> None:
    # relative inputs are normalized lexically against their own text, never the
    # process CWD, so containment stays predictable
    assert path_within(Path("repo/skills"), Path("repo")) is True
    assert path_within(Path("repo/../sibling"), Path("repo")) is False


def test_normalize_repo_dir_accepts_symlinked_dir_targeting_outside(
    fs: FakeFilesystem,
) -> None:
    # a skills dir reached through an in-repo symlink whose target lives outside
    # the repo is still accepted: containment is lexical, so the link is not
    # followed and its path stays within the repo
    git_root = Path("/projects/repo")
    fs.create_dir(git_root)
    fs.create_dir("/outside/skills")
    fs.create_symlink("/projects/repo/skills", "/outside/skills")

    result = normalize_repo_dir(git_root, "skills")

    assert result == Path("/projects/repo/skills")


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
