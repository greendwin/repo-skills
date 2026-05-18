from collections.abc import Generator

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.manifest import Manifest, SkillEntry
from tests.helper import (
    INSTALL_DIR,
    MANIFEST_PATH,
    REPO_SKILLS_DIR,
    FakeGitRepo,
    assert_invoke,
    create_repo_skill,
    install_fake_git,
    uninstall_fake_git,
)


@pytest.fixture(autouse=True)
def _fake_git() -> Generator[FakeGitRepo]:
    fake = FakeGitRepo(commits={"tdd": "abc1234", "grill-me": "def5678"})
    install_fake_git(fake)
    yield fake
    uninstall_fake_git()


def test_update_pulls_by_default(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
    )

    assert _fake_git.pulled is True


def test_update_skips_pull_when_offline(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert _fake_git.pulled is False


def test_update_fails_if_not_on_main_branch(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.branch = "feature/xyz"
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )

    assert "Not on main branch" in result.output


def test_update_fails_if_repo_is_dirty(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.clean = False
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )

    assert "uncommitted changes" in result.output


def test_update_auto_detects_commit(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "abc1234"


def test_update_skips_when_already_at_commit(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="abc1234")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Up to date" in result.output


def test_update_aborts_on_conflict(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd modified")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "conflict" in result.output


def test_update_all_syncs_every_installed_skill(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    create_repo_skill(fs, "grill-me")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")
    fs.create_file(INSTALL_DIR / "grill-me" / "SKILL.md", contents="# grill-me")

    manifest = Manifest(
        repo_path="/repo",
        skills={
            "tdd": SkillEntry(commit="old1"),
            "grill-me": SkillEntry(commit="old2"),
        },
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Up to date 'tdd'" in result.output
    assert "Up to date 'grill-me'" in result.output

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "abc1234"
    assert manifest.skills["grill-me"].commit == "def5678"


def test_update_mismatch_does_not_break_batch(
    fs: FakeFilesystem,
    _fake_git: FakeGitRepo,
) -> None:
    _fake_git.verified["tdd"] = False
    create_repo_skill(fs, "tdd")
    create_repo_skill(fs, "grill-me")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")
    fs.create_file(INSTALL_DIR / "grill-me" / "SKILL.md", contents="# grill-me")

    manifest = Manifest(
        repo_path="/repo",
        skills={
            "tdd": SkillEntry(commit="old1"),
            "grill-me": SkillEntry(commit="old2"),
        },
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Skipped 'tdd'" in result.output
    assert "grill-me" in result.output
    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["grill-me"].commit == "def5678"
    assert manifest.skills["tdd"].commit == "old1"


def test_update_conflict_does_not_break_batch(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    create_repo_skill(fs, "grill-me")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd modified")
    fs.create_file(INSTALL_DIR / "grill-me" / "SKILL.md", contents="# grill-me")

    manifest = Manifest(
        repo_path="/repo",
        skills={
            "tdd": SkillEntry(commit="old1"),
            "grill-me": SkillEntry(commit="old2"),
        },
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Skipped 'tdd'" in result.output
    assert "conflict" in result.output
    assert "grill-me" in result.output


def test_update_fails_if_skill_not_installed(
    fs: FakeFilesystem,
) -> None:
    fs.create_dir(REPO_SKILLS_DIR)
    fs.create_dir(INSTALL_DIR)

    manifest = Manifest(repo_path="/repo", skills={})
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "nope",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
        exit_code=1,
    )

    assert "not installed" in result.output


def test_update_adds_manifest_when_files_match(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(repo_path="/repo", skills={})
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Up to date" in result.output
    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "abc1234"


def test_update_all_includes_skills_only_on_disk(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    create_repo_skill(fs, "grill-me")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")
    fs.create_file(INSTALL_DIR / "grill-me" / "SKILL.md", contents="# grill-me")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old1")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "grill-me" in result.output
    assert "tdd" in result.output
    manifest = Manifest.load(MANIFEST_PATH)
    assert "grill-me" in manifest.skills


def test_update_copies_when_directory_missing(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_dir(INSTALL_DIR)

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="old123")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Updated 'tdd'" in result.output
    with open(INSTALL_DIR / "tdd" / "SKILL.md") as f:
        assert f.read() == "# tdd"
    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "abc1234"


def test_update_report_when_nothing_updated(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="abc1234")},
    )
    manifest.save(MANIFEST_PATH)

    result = assert_invoke(
        "update",
        "tdd",
        "--repo-skills-dir",
        str(REPO_SKILLS_DIR),
        "--install-dir",
        str(INSTALL_DIR),
        "--manifest-path",
        str(MANIFEST_PATH),
        "--offline",
    )

    assert "Up to date 'tdd'" in result.output
    assert "1 up to date" in result.output
