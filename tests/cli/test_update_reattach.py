from __future__ import annotations

from pathlib import Path

from pyfakefs.fake_filesystem import FakeFilesystem

from tests.cli.helper import (
    INSTALL_DIR,
    FakeGitRepo,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    load_manifest,
    register_provider,
)


class TestUpdateSafeReattach:
    def test_detached_skill_reattaches_to_older_matching_commit(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# tdd edited",
        ).build()
        # baseline commit fell off the pinned branch
        _fake_git.ancestors[("abc123", "main")] = False
        # an older reachable commit holds exactly the on-disk (edited) content
        _fake_git.commit_logs["skills/tdd"] = ["newer", "older"]
        _fake_git.files_at_commit[("older", "skills/tdd/SKILL.md")] = b"# tdd edited"
        # the latest verified commit the reattached baseline advances to
        _fake_git.branch_commits[("skills/tdd", "main")] = "latest"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "latest"
        assert_words_in_message(result.output, "tdd", "recovered")
        # install overwritten to the latest source content
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"

        status = assert_invoke("status")
        assert "detached" not in status.output.lower()
        assert "untracked" not in status.output.lower()

    def test_detached_skill_with_no_matching_commit_stays_untracked(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            detached=True,
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# tdd edited",
        ).build()
        # history exists but none of its commits hold the on-disk content
        _fake_git.commit_logs["skills/tdd"] = ["newer", "older"]
        _fake_git.files_at_commit[("older", "skills/tdd/SKILL.md")] = b"# other"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert_words_in_message(result.output, "tdd", "untracked")
        assert "recovered" not in result.output.lower()
        # install left byte-untouched
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd edited"

    def test_absent_second_provider_does_not_poison_reattach(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        # provider A holds an edited, detached copy matching an older commit;
        # provider B has no copy at all (its install dir is absent)
        register_provider("other", "/home/user/.other/skills")
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# tdd edited",
        ).build()
        _fake_git.ancestors[("abc123", "main")] = False
        _fake_git.commit_logs["skills/tdd"] = ["newer", "older"]
        _fake_git.files_at_commit[("older", "skills/tdd/SKILL.md")] = b"# tdd edited"
        _fake_git.branch_commits[("skills/tdd", "main")] = "latest"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "latest"
        assert_words_in_message(result.output, "tdd", "recovered")
        # both providers overwritten to the latest source content
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd v2"
        assert Path("/home/user/.other/skills/tdd/SKILL.md").read_text() == "# tdd v2"

    def test_no_existing_install_dirs_skip_reattach(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        # detached skill whose only provider install dir does not exist
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            detached=True,
            source_content="# tdd v2",
            installed_content="# tdd v1",
        ).build()
        # remove the installed copy so no provider dir exists on disk
        overwrite = INSTALL_DIR / "tdd" / "SKILL.md"
        overwrite.unlink()
        (INSTALL_DIR / "tdd").rmdir()
        _fake_git.commit_logs["skills/tdd"] = ["older"]
        _fake_git.files_at_commit[("older", "skills/tdd/SKILL.md")] = b"# tdd v1"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "abc123"
        assert "recovered" not in result.output.lower()

    def test_detached_skill_matching_latest_commit_recovers(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        # installed content matches the LATEST reachable commit's content
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            detached=True,
            source_content="# tdd latest",
            installed_content="# tdd v1",
            user_edited="# tdd latest",
        ).build()
        _fake_git.commit_logs["skills/tdd"] = ["latest", "older"]
        _fake_git.files_at_commit[("latest", "skills/tdd/SKILL.md")] = b"# tdd latest"
        _fake_git.branch_commits[("skills/tdd", "main")] = "latest"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is False
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "latest"
        assert_words_in_message(result.output, "tdd", "recovered")
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd latest"

        status = assert_invoke("status")
        assert "detached" not in status.output.lower()
        assert "untracked" not in status.output.lower()

    def test_providers_with_divergent_copies_skip_reattach(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_provider("other", "/home/user/.other/skills")
        SkillSetup(fs, git_repo).add_skill(
            "tdd",
            commit="abc123",
            detached=True,
            source_content="# tdd v2",
            installed_content="# tdd v1",
            user_edited="# tdd edited",
        ).build()
        # second provider holds a byte-different copy of the same skill
        fs.create_file(
            Path("/home/user/.other/skills/tdd/SKILL.md"), contents="# tdd DIFFERENT"
        )
        # a commit DOES match the primary copy, but copies disagree
        _fake_git.commit_logs["skills/tdd"] = ["older"]
        _fake_git.files_at_commit[("older", "skills/tdd/SKILL.md")] = b"# tdd edited"

        result = assert_invoke("update", "--offline")

        manifest = load_manifest()
        assert manifest.skills["tdd"].detached is True
        assert "recovered" not in result.output.lower()
        assert_words_in_message(result.output, "untracked")
        assert "failed" not in result.output.lower()
        # both on-disk copies left byte-unchanged: divergence guard skipped them
        assert (INSTALL_DIR / "tdd" / "SKILL.md").read_text() == "# tdd edited"
        assert (
            Path("/home/user/.other/skills/tdd/SKILL.md").read_text()
            == "# tdd DIFFERENT"
        )
