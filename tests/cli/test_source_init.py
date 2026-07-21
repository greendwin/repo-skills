from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    REPO_SKILLS_DIR,
    ConfigState,
    InstalledSkill,
    SourceBrokenError,
    default_config_path,
    load_source_config,
    load_source_registry,
    save_source_registry,
)
from repo_skills.config._source_registry import SOURCES_REGISTRY_FILE
from tests.cli.helper import (
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    assert_invoke,
    assert_words_in_message,
    create_repo_skill,
    load_manifest,
    save_manifest,
)


def _make_ambiguous_repo(fs: FakeFilesystem, git_repo: Path) -> None:
    """Populate ``git_repo`` so skills straddle the repo root (ambiguous detection).

    Two skills under distinct top-level dirs share no common dir below the root,
    which is exactly what makes auto-detection refuse to guess.
    """
    create_repo_skill(fs, "tdd", root=git_repo / "claude")
    create_repo_skill(fs, "review", root=git_repo / "copilot")


def _help_command_names(output: str) -> set[str]:
    """Extract the command-name column from a Typer ``--help`` Commands panel.

    Rich renders commands in a bordered panel; a command row places its name in a
    fixed left column right after ``│ `` while wrapped description lines indent
    their text further. Anchoring to that column (a non-space immediately after
    the border) avoids matching description prose or substrings elsewhere.
    """
    names: set[str] = set()
    in_commands = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("╭─") and "Commands" in stripped:
            in_commands = True
            continue
        if in_commands and stripped.startswith("╰"):
            break
        if in_commands and stripped.startswith("│"):
            row = stripped[1:]
            if row.startswith(" ") and not row[1:2].isspace():
                names.add(row.split()[0])
    return names


class TestSourceInitFreshRepo:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dirs == ["skills"]
        assert source_cfg.branch == "main"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(SOURCE_REPO_ROOT)

        assert_words_in_message(result.output, "initialized", "source", "my-project")

        gitignore = git_repo / REPO_SKILLS_DIR / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()


class TestSourceInitBrokenConfig:
    def test_malformed_config_aborts_without_overwriting(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        config_path = git_repo / REPO_SKILLS_DIR / "source.json"
        fs.create_file(config_path, contents="{not valid json")
        before = config_path.read_bytes()

        result = assert_invoke("source", "init", expect_error=True)

        assert isinstance(result.exception, SourceBrokenError)
        assert config_path.read_bytes() == before
        assert "initialized" not in result.output.lower()
        assert "broken" in result.output.lower()


class TestSourceInitPopulatedRepo:
    def test_detects_existing_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills")

        assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["skills"]
        assert not (git_repo / "skills" / ".gitkeep").exists()


class TestSourceInitBranch:
    def test_init_with_branch_flag(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = ["develop"]
        assert_invoke("source", "init", "--branch", "develop")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.branch == "develop"

    @pytest.mark.usefixtures("git_repo")
    def test_branch_flag_errors_when_branch_missing(
        self, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = []
        result = assert_invoke(
            "source", "init", "--branch", "no-such", expect_error=True
        )
        assert_words_in_message(result.message, "no-such", "not found")

    def test_reinit_preserves_existing_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _fake_git.branches = ["develop"]
        assert_invoke("source", "init", "--branch", "develop")

        _fake_git.branch = "feature/xyz"
        assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.branch == "develop"

    def test_reinit_with_branch_updates_pin(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "init")

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "init", "--branch", "release")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")
        assert "branch:" in result.output.lower()
        assert "main" in result.output
        assert "release" in result.output


class TestSourceInitNameOverride:
    def test_name_flag_overrides_derived_name(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init", "--name", "custom-name")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "custom-name"

        registry = load_source_registry()
        assert "custom-name" in registry.sources
        assert "my-project" not in registry.sources

        assert_words_in_message(result.output, "initialized", "source", "custom-name")


@pytest.mark.usefixtures("git_repo")
class TestSourceInitIdempotent:
    def test_already_initialized_is_not_error(self) -> None:
        assert_invoke("source", "init")
        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "already initialized", "my-project")

    def test_already_initialized_with_matching_name(self) -> None:
        assert_invoke("source", "init", "--name", "custom")
        result = assert_invoke("source", "init", "--name", "custom")

        assert_words_in_message(result.output, "already initialized", "custom")

    def test_reinit_re_registers_removed_source(self) -> None:
        assert_invoke("source", "init")

        registry = load_source_registry()
        registry.unregister_source("my-project")
        save_source_registry(registry)

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "registered", "my-project")

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(SOURCE_REPO_ROOT)

    def test_re_register_with_branch_change(self, _fake_git: FakeGitRepo) -> None:
        assert_invoke("source", "init")

        registry = load_source_registry()
        registry.unregister_source("my-project")
        save_source_registry(registry)

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "init", "--branch", "release")

        assert_words_in_message(result.output, "registered", "my-project")
        assert "branch:" in result.output.lower()
        assert "release" in result.output


@pytest.mark.usefixtures("git_repo")
class TestSourceInitRename:
    def test_rename_updates_config_and_registry(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")
        result = assert_invoke("source", "init", "--name", "new-name")

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "old-name" in result.output
        assert "new-name" in result.output

        loaded = load_source_config(Path(SOURCE_REPO_ROOT))
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "new-name"

        registry = load_source_registry()
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources
        assert registry.sources["new-name"].repo_root == Path(SOURCE_REPO_ROOT)

    def test_rename_with_branch_change_shows_both(self, _fake_git: FakeGitRepo) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        _fake_git.branches = ["develop"]
        result = assert_invoke(
            "source", "init", "--name", "new-name", "--branch", "develop"
        )

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "branch:" in result.output.lower()
        assert "old-name" in result.output
        assert "new-name" in result.output
        assert "develop" in result.output

    def test_rename_updates_installed_skills_in_manifest(self) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        save_manifest(
            {
                "tdd": InstalledSkill(source="old-name"),
                "review": InstalledSkill(source="old-name"),
                "deploy": InstalledSkill(source="other-source"),
            }
        )

        result = assert_invoke("source", "init", "--name", "new-name")
        assert_words_in_message(result.output, "updated", "new-name")

        updated = load_manifest()
        assert updated.skills["tdd"].source == "new-name"
        assert updated.skills["review"].source == "new-name"
        assert updated.skills["deploy"].source == "other-source"


class TestTopLevelInit:
    def test_creates_source_config_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dirs == ["skills"]
        assert source_cfg.branch == "main"

        assert (git_repo / "skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources
        assert registry.sources["my-project"].repo_root == Path(SOURCE_REPO_ROOT)

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    def test_init_is_visible_in_top_level_help(self) -> None:
        result = assert_invoke("--help")
        assert "init" in _help_command_names(result.output)


class TestSourceConfig:
    def test_fresh_repo_creates_and_registers(self, git_repo: Path) -> None:
        result = assert_invoke("source", "config")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "my-project"

        registry = load_source_registry()
        assert "my-project" in registry.sources

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    def test_existing_source_edits_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "config")

        _fake_git.branches = ["release"]
        result = assert_invoke("source", "config", "--branch", "release")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")

    @pytest.mark.usefixtures("git_repo")
    def test_config_is_visible_in_source_help(self) -> None:
        result = assert_invoke("source", "--help")
        assert "config" in _help_command_names(result.output)


class TestSourceInitAlias:
    def test_hidden_alias_still_works(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "my-project"

        assert_words_in_message(result.output, "initialized", "source", "my-project")

    @pytest.mark.usefixtures("git_repo")
    def test_init_is_hidden_from_source_help(self) -> None:
        result = assert_invoke("source", "--help")
        assert "init" not in _help_command_names(result.output)


class TestSourceInitErrors:
    def test_not_in_git_repo(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fs.create_dir("/not-a-repo")
        monkeypatch.chdir("/not-a-repo")

        result = assert_invoke("source", "init", expect_error=True)
        assert_words_in_message(result.message, "git")


class TestSourceInitAutoDetect:
    def test_detects_skills_in_subdirectory(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "my-skills")
        create_repo_skill(fs, "review", root=git_repo / "my-skills")

        assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["my-skills"]

    def test_detects_skills_with_categories(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "skills" / "dev")
        create_repo_skill(fs, "deploy", root=git_repo / "skills" / "ops")

        assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["skills"]


class TestSourceInitSkillsDir:
    def test_fresh_init_with_skills_dir_uses_it_and_skips_bootstrap(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        result = assert_invoke("source", "init", "--skills-dir", "my-skills")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "my-project"
        assert source_cfg.skills_dirs == ["my-skills"]
        assert source_cfg.branch == "main"

        assert not (git_repo / "skills").exists()
        assert not (git_repo / "my-skills" / ".gitkeep").exists()

        registry = load_source_registry()
        assert "my-project" in registry.sources

        gitignore = git_repo / REPO_SKILLS_DIR / ".gitignore"
        assert gitignore.exists()
        assert "*" in gitignore.read_text()

        assert_words_in_message(result.output, "initialized", "my-project")

    def test_multiple_skills_dirs_stored_verbatim(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "a")
        fs.create_dir(git_repo / "b")

        assert_invoke("source", "init", "--skills-dir", "a", "--skills-dir", "b")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["a", "b"]

    def test_duplicate_skills_dir_collapsed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "a")

        assert_invoke("source", "init", "--skills-dir", "a", "--skills-dir", "a")

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["a"]

    def test_skills_dir_dup_after_normalization_collapsed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "a")

        assert_invoke("source", "init", "--skills-dir", "a", "--skills-dir", "./a")

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["a"]

    def test_nested_skills_dir_collapsed_child_after_parent(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "top" / "group")

        result = assert_invoke(
            "source",
            "init",
            "--skills-dir",
            "top",
            "--skills-dir",
            "top/group",
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["top"]
        assert_words_in_message(result.output, "top/group", "inside", "ignoring")
        # the container name is load-bearing: anchor on the trailing delimiter so a
        # substring of the dropped dir cannot stand in for the container token
        assert "is inside top;" in result.output

    def test_nested_skills_dir_collapsed_parent_after_child(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "top" / "group")

        result = assert_invoke(
            "source",
            "init",
            "--skills-dir",
            "top/group",
            "--skills-dir",
            "top",
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["top"]
        assert_words_in_message(result.output, "top/group", "inside", "ignoring")
        assert "is inside top;" in result.output

    def test_dedup_preserves_first_occurrence_order(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "a")
        fs.create_dir(git_repo / "b")

        assert_invoke(
            "source",
            "init",
            "--skills-dir",
            "b",
            "--skills-dir",
            "a",
            "--skills-dir",
            "b",
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["b", "a"]
        assert source_cfg.active_dir == "b"

    def test_exact_dup_skills_dir_dedups_silently(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "b")

        result = assert_invoke(
            "source", "init", "--skills-dir", "b", "--skills-dir", "b"
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["b"]
        # an exact repeat is not "inside itself": no nesting note must appear
        assert "inside" not in result.output
        assert "ignoring" not in result.output

    def test_skills_dir_bypasses_detection_for_nonexistent_dir(
        self, git_repo: Path
    ) -> None:
        # the dir need not exist; the first dir doubles as the merge target
        result = assert_invoke("source", "init", "--skills-dir", "not-yet-here")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["not-yet-here"]
        assert not (git_repo / "skills").exists()

        assert_words_in_message(result.output, "not-yet-here", "no skills")

    def test_skills_dir_bypasses_detection_when_repo_is_ambiguous(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _make_ambiguous_repo(fs, git_repo)

        result = assert_invoke("source", "init", "--skills-dir", "claude")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["claude"]

        # a populated explicit dir stays silent: no "no skills" note
        assert "no skills" not in result.output

    def test_skills_dir_repo_root_is_allowed(self, git_repo: Path) -> None:
        result = assert_invoke("source", "init", "--skills-dir", ".")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["."]

        assert ". currently has no skills" in result.output

    def test_skills_dir_note_targets_only_the_empty_dir(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "a")
        fs.create_dir(git_repo / "b")

        result = assert_invoke(
            "source", "init", "--skills-dir", "a", "--skills-dir", "b"
        )

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["a", "b"]

        # only the empty sibling warns; the populated dir stays silent
        assert_words_in_message(result.output, "b", "no skills")
        assert "a currently has no skills" not in result.output

    def test_skills_dir_overrides_auto_detection(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        create_repo_skill(fs, "tdd", root=git_repo / "auto-skills")
        fs.create_dir(git_repo / "chosen-skills")

        assert_invoke("source", "init", "--skills-dir", "chosen-skills")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["chosen-skills"]

    def test_skills_dir_is_normalized_before_storing(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        assert_invoke("source", "init", "--skills-dir", "./my-skills/")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["my-skills"]

    def test_reinit_with_skills_dir_updates_value_and_emits_change(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")
        fs.create_dir(git_repo / "new-skills")

        result = assert_invoke("source", "init", "--skills-dir", "new-skills")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["new-skills"]

        assert_words_in_message(
            result.output, "updated", "dirs", "skills", "new-skills"
        )

    def test_reinit_collapses_nested_skills_dirs_and_emits_change(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")
        fs.create_dir(git_repo / "parent" / "child")

        result = assert_invoke(
            "source",
            "init",
            "--skills-dir",
            "parent",
            "--skills-dir",
            "parent/child",
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["parent"]

        assert_words_in_message(result.output, "updated", "dirs", "parent")
        assert "is inside parent;" in result.output
        assert "ignoring" in result.output

    def test_reinit_without_nested_dirs_stays_silent_about_nesting(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")
        fs.create_dir(git_repo / "parent")

        first = assert_invoke("source", "init", "--skills-dir", "parent")
        # a no-op re-init with the same single dir collapses nothing
        second = assert_invoke("source", "init", "--skills-dir", "parent")

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["parent"]

        for output in (first.output, second.output):
            assert "is inside" not in output
            assert "ignoring" not in output

    def test_reinit_with_multiple_skills_dirs(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")
        fs.create_dir(git_repo / "a")
        fs.create_dir(git_repo / "b")

        assert_invoke("source", "init", "--skills-dir", "a", "--skills-dir", "b")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["a", "b"]

    def test_reinit_reordering_dirs_flips_active_dir_and_shows_real_order(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "alpha")
        fs.create_dir(git_repo / "bravo")
        assert_invoke(
            "source", "init", "--skills-dir", "alpha", "--skills-dir", "bravo"
        )

        # a pure reorder flips the active (first) dir, the merge write-back target
        result = assert_invoke(
            "source", "init", "--skills-dir", "bravo", "--skills-dir", "alpha"
        )

        loaded = load_source_config(git_repo)
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["bravo", "alpha"]
        assert source_cfg.active_dir == "bravo"

        # the change line must reflect the true before/after ordering, not render
        # both sides identically (a sorted view would print "alpha, bravo -> ...")
        assert_words_in_message(result.output, "updated", "dirs")
        dirs_line = next(line for line in result.output.splitlines() if "dirs:" in line)
        before, sep, after = dirs_line.partition("→")
        assert sep, f"expected a change arrow in dirs line: {dirs_line!r}"
        # the rendered fragment shows the true before/after ordering
        assert "alpha, bravo" in before
        assert "bravo, alpha" in after

    def test_reinit_with_empty_skills_dir_emits_no_skills_note(
        self, git_repo: Path
    ) -> None:
        assert_invoke("source", "init")

        # the dir changes from "skills" to "still-empty", so the note fires on
        # reinit when the newly-set dir lacks skills
        result = assert_invoke("source", "init", "--skills-dir", "still-empty")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["still-empty"]

        assert_words_in_message(result.output, "still-empty", "no skills")

    def test_reinit_without_skills_dir_leaves_list_untouched(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_dir(git_repo / "custom")
        assert_invoke("source", "init", "--skills-dir", "custom")

        result = assert_invoke("source", "init")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["custom"]
        assert "dirs:" not in result.output

    def test_reinit_with_name_branch_and_skills_dir_together(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        assert_invoke("source", "init", "--name", "old-name")

        fs.create_dir(git_repo / "new-skills")
        _fake_git.branches = ["develop"]

        result = assert_invoke(
            "source",
            "init",
            "--name",
            "new-name",
            "--branch",
            "develop",
            "--skills-dir",
            "new-skills",
        )

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.name == "new-name"
        assert source_cfg.branch == "develop"
        assert source_cfg.skills_dirs == ["new-skills"]

        registry = load_source_registry()
        assert "new-name" in registry.sources
        assert "old-name" not in registry.sources

        assert_words_in_message(result.output, "updated", "new-name")
        assert "name:" in result.output.lower()
        assert "branch:" in result.output.lower()
        assert "dirs:" in result.output.lower()

    def test_reinit_with_same_skills_dir_emits_no_change(self, git_repo: Path) -> None:
        assert_invoke("source", "init")

        # precondition: bootstrap created a populated-but-skill-less skills dir,
        # so the no-op reinit below can only stay silent for the right reason
        assert (git_repo / "skills" / ".gitkeep").exists()
        assert not list((git_repo / "skills").rglob("SKILL.md"))

        result = assert_invoke("source", "init", "--skills-dir", "skills")

        assert_words_in_message(result.output, "already initialized", "my-project")
        assert "dirs:" not in result.output
        # a no-op reinit with the unchanged dir must stay silent: no stale
        # "no skills" note contradicting "already initialized"
        assert "no skills" not in result.output

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["skills"]

    @pytest.mark.parametrize(
        ("skills_dir", "setup"),
        [
            pytest.param(
                "/elsewhere",
                lambda fs: fs.create_dir("/elsewhere"),
                id="absolute",
            ),
            pytest.param(
                "../sibling",
                lambda fs: fs.create_dir("/repos/sibling"),
                id="escaping",
            ),
        ],
    )
    @pytest.mark.usefixtures("git_repo")
    def test_error_escaping_skills_dir(
        self,
        fs: FakeFilesystem,
        skills_dir: str,
        setup: Callable[[FakeFilesystem], object],
    ) -> None:
        setup(fs)

        result = assert_invoke(
            "source", "init", "--skills-dir", skills_dir, expect_error=True
        )

        assert_words_in_message(result.message, "Skills dir", "escapes", skills_dir)

    def test_error_escaping_skills_dir_in_multi_dir_list(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        # each element is validated: a valid leading dir does not excuse a later
        # escaping one
        fs.create_dir(git_repo / "a")
        fs.create_dir("/repos/sibling")

        result = assert_invoke(
            "source",
            "init",
            "--skills-dir",
            "a",
            "--skills-dir",
            "../sibling",
            expect_error=True,
        )

        assert_words_in_message(result.message, "Skills dir", "escapes", "../sibling")


class TestSourceInitAmbiguous:
    def test_fresh_init_ambiguous_errors_and_writes_no_config(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _make_ambiguous_repo(fs, git_repo)

        result = assert_invoke("source", "init", expect_error=True)

        assert_words_in_message(result.message, "--skills-dir")
        assert load_source_config(git_repo).state is ConfigState.MISSING
        assert not (git_repo / REPO_SKILLS_DIR / "source.json").exists()

        # the error fires before any save, so no source leaks into the registry
        registry = load_source_registry()
        assert "my-project" not in registry.sources


VISIBLE_COMMAND_PREFIXES = [
    pytest.param(("init",), id="init"),
    pytest.param(("source", "config"), id="source-config"),
    pytest.param(("source", "init"), id="source-init-alias"),
]


class TestCommandSurface:
    """Each command surface (``init``, ``source config``, hidden ``source init``)
    shares one option declaration via ``Depends``; prove every surface reaches
    create-or-edit and accepts ``--skills-dir``.
    """

    @pytest.mark.parametrize("prefix", VISIBLE_COMMAND_PREFIXES)
    def test_fresh_create_with_skills_dir(
        self, fs: FakeFilesystem, git_repo: Path, prefix: tuple[str, ...]
    ) -> None:
        fs.create_dir(git_repo / "my-skills")

        result = assert_invoke(*prefix, "--skills-dir", "my-skills")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.skills_dirs == ["my-skills"]

        assert_words_in_message(result.output, "initialized", "my-project")

    @pytest.mark.parametrize("prefix", VISIBLE_COMMAND_PREFIXES)
    def test_edit_existing_source_updates_branch(
        self, git_repo: Path, _fake_git: FakeGitRepo, prefix: tuple[str, ...]
    ) -> None:
        assert_invoke(*prefix)

        _fake_git.branches = ["release"]
        result = assert_invoke(*prefix, "--branch", "release")

        loaded = load_source_config(git_repo)
        assert loaded.state is ConfigState.OK
        source_cfg = loaded.cfg
        assert source_cfg.branch == "release"

        assert_words_in_message(result.output, "updated", "my-project")


class TestSourceInitBrokenSourceRegistry:
    @pytest.mark.usefixtures("git_repo")
    def test_broken_registry_warns_and_initializes(self) -> None:
        source_path = default_config_path(SOURCES_REGISTRY_FILE)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("{{{invalid")

        result = assert_invoke("source", "init")

        assert_words_in_message(result.output, "warning", "broken config file")
        assert_words_in_message(result.output, "initialized", "my-project")

        registry = load_source_registry()
        assert "my-project" in registry.sources
