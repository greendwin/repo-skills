from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    SourceConfig,
    default_config_path,
    load_skill_manifest,
    load_source_registry,
    save_source_config,
    save_source_registry,
)
from repo_skills.config._skill_manifest import SKILL_MANIFEST_FILE
from tests.cli.helper import (
    INSTALL_DIR,
    OTHER_REPO_ROOT,
    OTHER_SKILLS_DIR,
    SKILLS_DIR,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
    register_provider,
    register_source,
)


@pytest.fixture()
def _fake_git_factory() -> Callable[[], FakeGitRepo]:
    return lambda: FakeGitRepo(commits={"skills/tdd": "abc1234"})


def _add_second_source(fs: FakeFilesystem) -> None:
    fs.create_dir(Path(OTHER_REPO_ROOT) / ".git")
    registry = load_source_registry()
    registry.register_source("other-project", Path(OTHER_REPO_ROOT))
    save_source_registry(registry)

    cfg = SourceConfig(name="other-project", skills_dirs=["skills"], branch="")
    save_source_config(cfg, Path(OTHER_REPO_ROOT))


class TestInstall:
    def test_copies_skill_to_provider(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        skill_dir = create_repo_skill(fs, "tdd")
        fs.create_file(skill_dir / "tests.python.md", contents="# Python tests")

        assert_invoke("install", "tdd", "--offline")

        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()
        assert (Path(INSTALL_DIR) / "tdd" / "tests.python.md").exists()

    def test_records_source_commit_hashes_in_manifest(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        assert_invoke("install", "tdd", "--offline")

        manifest = load_skill_manifest()
        assert "tdd" in manifest.skills
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.baseline is not None
        assert entry.baseline.commit == "abc1234"
        assert len(entry.baseline.files) > 0
        assert all(v.startswith("sha256:") for v in entry.baseline.files.values())

    def test_auto_selects_single_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd", "my-project")


class TestInstallMultipleSkills:
    @pytest.fixture()
    def _fake_git_factory(self) -> Callable[[], FakeGitRepo]:
        return lambda: FakeGitRepo(
            commits={"skills/tdd": "abc1234", "skills/review": "def5678"}
        )

    def test_installs_multiple_skills(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")
        create_repo_skill(fs, "review")

        result = assert_invoke("install", "tdd", "review", "--offline")

        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()
        assert (Path(INSTALL_DIR) / "review" / "SKILL.md").exists()
        manifest = load_skill_manifest()
        assert "tdd" in manifest.skills
        assert "review" in manifest.skills
        assert_words_in_message(result.output, "installed", "tdd", "review")

    def test_fails_fast_on_missing_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke(
            "install", "tdd", "missing", "--offline", expect_error=True
        )

        assert_words_in_message(result.message, "missing", "not found")
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()

    def test_pulls_source_only_once(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")
        create_repo_skill(fs, "review")

        assert_invoke("install", "tdd", "review")

        assert _fake_git.pulled is True


class TestInstallSourceResolution:
    @pytest.mark.usefixtures("fs", "git_repo")
    def test_errors_when_no_sources(self) -> None:
        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "no sources")
        assert_words_in_message(result.message, "skills init")
        assert "source init" not in result.message

    def test_auto_resolves_when_skill_in_one_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _add_second_source(fs)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd", "my-project")

    def test_errors_when_skill_in_multiple_sources(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _add_second_source(fs)
        create_repo_skill(fs, "tdd")
        create_repo_skill(fs, "tdd", root=Path(OTHER_SKILLS_DIR))

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "multiple sources", "--source")

    def test_selects_source_with_flag(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        registry = load_source_registry()
        registry.register_source("other", Path("/repos/other"))
        save_source_registry(registry)

        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--source", "my-project", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    def test_selects_source_with_short_flag(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        registry = load_source_registry()
        registry.register_source("other", Path("/repos/other"))
        save_source_registry(registry)

        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "-s", "my-project", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    @pytest.mark.usefixtures("fs")
    def test_errors_when_source_not_found(self, git_repo: Path) -> None:
        register_source(git_repo)

        result = assert_invoke(
            "install", "tdd", "--source", "nope", "--offline", expect_error=True
        )

        assert_words_in_message(result.message, "not found")


class TestInstallMultiProvider:
    def test_installs_to_all_providers(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))

        assert_invoke("install", "tdd", "--offline")

        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()
        assert (cursor_dir / "tdd" / "SKILL.md").exists()


class TestInstallCollision:
    def test_errors_when_skill_already_exists(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")
        fs.create_dir(Path(INSTALL_DIR) / "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "already exists", "--force")

    def test_force_overwrites_existing(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")
        fs.create_dir(Path(INSTALL_DIR) / "tdd")
        fs.create_file(Path(INSTALL_DIR) / "tdd" / "old.md", contents="old")

        result = assert_invoke("install", "tdd", "--offline", "--force")

        assert_words_in_message(result.output, "installed", "tdd")
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()
        assert not (Path(INSTALL_DIR) / "tdd" / "old.md").exists()


class TestInstallGitValidation:
    def test_auto_switches_when_not_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "feature/xyz"
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")
        assert _fake_git.branch == "main"

    def test_succeeds_on_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branch = "develop"
        register_source(git_repo, branch="develop")
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "installed", "tdd")

    def test_errors_when_dirty_on_correct_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "uncommitted changes")

    def test_errors_when_dirty_and_wrong_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.clean = False
        _fake_git.branch = "other"
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "uncommitted changes")

    def test_errors_when_skill_not_in_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        fs.create_dir(Path(SKILLS_DIR))

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "not found")

    def test_errors_when_content_does_not_match_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.commits["skills/tdd"] = "abc1234"
        _fake_git.verified["skills/tdd"] = False
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "content mismatch")
        # the verification fails before any copy: nothing installed or recorded
        assert not (Path(INSTALL_DIR) / "tdd").exists()
        assert "tdd" not in load_skill_manifest().skills

    def test_errors_when_source_has_no_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        # no `commits`/`branch_commits` entry: latest commit is unresolvable
        _fake_git.commits.clear()
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        result = assert_invoke("install", "tdd", "--offline", expect_error=True)

        assert_words_in_message(result.message, "no commit found")
        assert not (Path(INSTALL_DIR) / "tdd").exists()
        assert "tdd" not in load_skill_manifest().skills

    def test_pulls_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        assert_invoke("install", "tdd")

        assert _fake_git.pulled is True

    def test_skips_pull_when_offline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")

        assert_invoke("install", "tdd", "--offline")

        assert _fake_git.pulled is False


class TestInstallBrokenManifest:
    def test_broken_manifest_warns_and_installs(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_repo_skill(fs, "tdd")
        manifest_path = default_config_path(SKILL_MANIFEST_FILE)
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("")

        result = assert_invoke("install", "tdd", "--offline")

        assert_words_in_message(result.output, "warning", "broken config file")
        assert (Path(INSTALL_DIR) / "tdd" / "SKILL.md").exists()
