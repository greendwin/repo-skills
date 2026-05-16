from pyfakefs.fake_filesystem import FakeFilesystem

from skill_cli.manifest import Manifest, SkillEntry
from tests.helper import (
    INSTALL_DIR,
    MANIFEST_PATH,
    REPO_SKILLS_DIR,
    assert_invoke,
    create_repo_skill,
)


def test_update_single_skill_copies_repo_content(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(REPO_SKILLS_DIR / "tdd" / "extra.md", contents="new content")
    # Installed matches repo (no local edits)
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "extra.md", contents="new content")

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
        "--commit",
        "new456",
    )

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "new456"


def test_update_skips_unchanged_same_commit(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(
        repo_path="/repo",
        skills={"tdd": SkillEntry(commit="abc123")},
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
        "--commit",
        "abc123",
    )

    assert "up to date" in result.output


def test_update_aborts_on_conflict(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    # Installed has different content (user edited)
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
        "--commit",
        "new456",
        exit_code=1,
    )

    assert "Conflict" in result.output
    assert "peek --diff" in result.output
    assert "merge" in result.output


def test_update_all_updates_every_installed_skill(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    create_repo_skill(fs, "grill-me")
    # Installed matches repo
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
        "--commit",
        "new789",
    )

    assert "Updated 'tdd'" in result.output
    assert "Updated 'grill-me'" in result.output

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "new789"
    assert manifest.skills["grill-me"].commit == "new789"


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
        exit_code=1,
    )

    assert "not installed" in result.output


def test_update_works_when_skill_not_in_manifest(
    fs: FakeFilesystem,
) -> None:
    create_repo_skill(fs, "tdd")
    # Installed on disk but no manifest entry
    fs.create_file(INSTALL_DIR / "tdd" / "SKILL.md", contents="# tdd")

    manifest = Manifest(repo_path="/repo", skills={})
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
        "--commit",
        "new456",
    )

    manifest = Manifest.load(MANIFEST_PATH)
    assert manifest.skills["tdd"].commit == "new456"


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
        "--commit",
        "new789",
    )

    assert "Updated 'tdd'" in result.output
    assert "Updated 'grill-me'" in result.output
