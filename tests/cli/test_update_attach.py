from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

import repo_skills.cli._update_attach as attach_mod
from repo_skills.config import (
    Baseline,
    InstalledSkill,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    load_source_registry,
    save_source_config,
    save_source_registry,
)
from tests.cli.helper import (
    INSTALL_DIR,
    OTHER_REPO_ROOT,
    OTHER_SKILLS_DIR,
    SKILLS_DIR,
    FakeGitRepo,
    FakeGitRepoManager,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    create_source_skill,
    install_skill,
    load_manifest,
    register_provider,
    register_source,
    save_manifest,
)


@pytest.fixture()
def two_sources(fs: FakeFilesystem, git_repo: Path) -> None:
    (
        SkillSetup(fs, git_repo)
        .add_source("my-project")
        .add_source("other-project", OTHER_REPO_ROOT)
        .build()
    )


class TestUpdateAttach:
    def test_exact_match_untracked_is_attached_and_updated(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "Attached skill tdd", "matched source my-project"
        )

        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert entry.source == "my-project"
        assert entry.detached is False
        assert entry.baseline is not None
        assert entry.baseline.commit == "commit-tdd"
        assert entry.baseline.files == compute_file_hashes(INSTALL_DIR / "tdd")

    def test_same_skill_in_two_providers_attaches_once(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        cursor_dir = Path("/home/user/.cursor/skills")
        register_provider("cursor", str(cursor_dir))
        install_skill(fs, "tdd", content="# tdd", install_dir=cursor_dir)
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert result.output.count("Attached skill tdd") == 1
        manifest = load_manifest()
        assert list(manifest.skills) == ["tdd"]

    def test_exact_match_untracked_is_attached_and_reports_up_to_date(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "Updating tdd", "up-to-date")

        manifest = load_manifest()
        entry = manifest.skills["tdd"]
        assert entry.baseline is not None
        assert entry.baseline.commit == "commit-tdd"
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_exact_match_with_verify_failure_is_not_attached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.verified["skills/tdd"] = False

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_exact_match_with_unresolved_commit_is_not_attached(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_skill_vanished_from_source_post_pull_is_not_attached(
        self,
        fs: FakeFilesystem,
        git_repo: Path,
        _fake_git: FakeGitRepo,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        _fake_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        _fake_git.ancestors[("commit-tdd", "main")] = True

        real_compute = compute_file_hashes

        def _drift(path: Path) -> dict[str, str]:
            if str(path).startswith(str(SKILLS_DIR / "tdd")):
                return {"SKILL.md": "drifted"}
            return real_compute(path)

        monkeypatch.setattr(attach_mod, "compute_file_hashes", _drift)

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_detached_entry_matching_source_is_not_re_attached(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd")
        hashes = install_skill(fs, "tdd", content="# tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )
        _fake_git.ancestors[("abc123", "main")] = True

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert list(manifest.skills) == ["tdd"]
        assert manifest.skills["tdd"].detached is False

    def test_modified_untracked_is_not_attached_and_untouched(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        create_source_skill(fs, "tdd", content="# tdd v2")
        install_skill(fs, "tdd", content="# user copy")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# user copy"


@pytest.mark.usefixtures("two_sources")
class TestUpdateAttachAmbiguity:
    def test_multi_source_exact_match_is_skipped_with_note(
        self, fs: FakeFilesystem
    ) -> None:
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "tdd", content="# tdd", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})

        result = assert_invoke("update", "--offline")

        assert "Attached skill tdd" not in result.output
        assert_words_in_message(result.output, "tdd", "multiple sources")
        manifest = load_manifest()
        assert "tdd" not in manifest.skills
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd"

    def test_source_flag_disambiguates_multi_source_match(
        self, fs: FakeFilesystem, git_repo: Path, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "tdd", content="# tdd", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        save_manifest({})
        my_git = fake_git_manager.make(git_repo)
        my_git.branch_commits[("skills/tdd", "main")] = "commit-tdd"
        my_git.ancestors[("commit-tdd", "main")] = True

        result = assert_invoke("update", "--offline", "-s", "my-project")

        assert_words_in_message(
            result.output, "Attached skill tdd", "matched source my-project"
        )
        manifest = load_manifest()
        assert manifest.skills["tdd"].source == "my-project"


@pytest.mark.usefixtures("two_sources")
class TestUpdateAttachFilter:
    def test_source_flag_excludes_other_source_candidate(
        self, fs: FakeFilesystem
    ) -> None:
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})

        result = assert_invoke("update", "--offline", "-s", "my-project")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills

    def test_source_flag_attaches_untracked_match_instead_of_noop(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "--offline", "-s", "other-project")

        assert "no skills installed from source" not in result.output.lower()
        assert_words_in_message(
            result.output, "Attached skill review", "matched source other-project"
        )
        assert_words_in_message(result.output, "Updating review")
        manifest = load_manifest()
        assert manifest.skills["review"].source == "other-project"

    def test_attach_candidate_source_is_pulled(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest({})

        assert_invoke("update", "-s", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is True

    def test_source_flag_does_not_pull_or_attach_other_source_match(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc", files={}),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "-s", "my-project")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills
        assert other_git.pulled is False

    def test_eligible_attach_sources_limited_to_requested_sources(
        self, fs: FakeFilesystem
    ) -> None:
        """_eligible_attach_sources only returns explicitly requested sources,
        not other sources that happen to own tracked skills."""
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        source_registry = load_source_registry()

        eligible = attach_mod.eligible_attach_sources(
            source_registry,
            source_names=["my-project"],
        )

        assert "my-project" in eligible
        assert "other-project" not in eligible

    def test_name_filter_does_not_attach_unrelated_untracked_match(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit="abc", files=compute_file_hashes(INSTALL_DIR / "tdd")
                    ),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "tdd", "--offline")

        assert "Attached skill review" not in result.output
        manifest = load_manifest()
        assert "review" not in manifest.skills

    def test_name_membership_candidate_source_is_pulled_for_post_pull_check(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "review", content="# review v2", root=OTHER_SKILLS_DIR)
        install_skill(fs, "review", content="# review v1")
        save_manifest({})

        assert_invoke("update", "-s", "other-project")

        assert fake_git_manager.make(OTHER_REPO_ROOT).pulled is True


@pytest.mark.usefixtures("two_sources")
class TestUpdateAttachNoFilter:
    def test_plain_update_attaches_match_from_untracked_only_source(
        self, fs: FakeFilesystem, fake_git_manager: FakeGitRepoManager
    ) -> None:
        create_source_skill(fs, "tdd", content="# tdd", root=SKILLS_DIR)
        create_source_skill(fs, "review", content="# review", root=OTHER_SKILLS_DIR)
        install_skill(fs, "tdd", content="# tdd")
        install_skill(fs, "review", content="# review")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit="abc", files=compute_file_hashes(INSTALL_DIR / "tdd")
                    ),
                )
            }
        )
        other_git = fake_git_manager.make(OTHER_REPO_ROOT)
        other_git.branch_commits[("skills/review", "main")] = "commit-review"
        other_git.ancestors[("commit-review", "main")] = True

        result = assert_invoke("update", "--offline")

        assert_words_in_message(
            result.output, "Attached skill review", "matched source other-project"
        )
        manifest = load_manifest()
        assert manifest.skills["review"].source == "other-project"


class TestUpdateBrokenSource:
    def test_broken_source_warns_and_valid_skill_still_updates(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        broken_root = Path("/repos/broken-project")
        fs.create_dir(broken_root / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("broken-project", broken_root)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dir="skills", branch=""), git_repo
        )

        create_source_skill(fs, "tdd", content="# tdd v2", root=SKILLS_DIR)
        h1 = install_skill(fs, "tdd", content="# tdd v1")
        install_skill(fs, "untracked-skill", content="# untracked")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="old", files=h1)
                )
            }
        )

        result = assert_invoke("update", "--offline")

        assert_words_in_message(result.output, "warning", "broken-project")
        assert_words_in_message(result.output, "tdd", "updated")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"
