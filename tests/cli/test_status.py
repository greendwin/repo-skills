from __future__ import annotations

from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    Baseline,
    ConfigState,
    InstalledSkill,
    SourceConfig,
    SourceRegistry,
    default_config_path,
    load_source_config,
    save_source_config,
    save_source_registry,
)
from repo_skills.config._provider_registry import PROVIDERS_REGISTRY_FILE
from repo_skills.config._skill_manifest import SKILL_MANIFEST_FILE
from repo_skills.config._source_registry import SOURCES_REGISTRY_FILE
from tests.cli.helper import (
    INSTALL_DIR,
    OTHER_REPO_ROOT,
    SOURCE_REPO_ROOT,
    FakeGitRepo,
    SkillSetup,
    assert_invoke,
    assert_words_in_message,
    install_skill,
    register_provider,
    register_source,
    save_manifest,
    write_broken_source,
)


def install_two_sources(fs: FakeFilesystem, git_repo: Path) -> None:
    SkillSetup(fs, git_repo).add_skill(
        "tdd", source_name="my-project", commit="abc"
    ).add_skill(
        "review",
        source_name="other-project",
        source_root=OTHER_REPO_ROOT,
        commit="def",
    ).build()


def assert_single_blank_before(lines: list[str], index: int) -> None:
    assert lines[index - 1] == ""
    assert lines[index - 2] != ""


def assert_no_double_blank(lines: list[str]) -> None:
    assert not any(lines[i] == "" and lines[i + 1] == "" for i in range(len(lines) - 1))


def source_header_indices(lines: list[str]) -> list[int]:
    return [i for i, line in enumerate(lines) if line.startswith("Source")]


def untracked_header_index(lines: list[str]) -> int:
    return next(i for i, line in enumerate(lines) if line.startswith("Untracked"))


class TestStatusSynced:
    def test_shows_synced_skill(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "my-project", "synced")


class TestStatusModified:
    def test_shows_modified_when_content_changed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                )
            }
        )
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "modified")


class TestStatusMissing:
    @pytest.mark.usefixtures("fs")
    def test_shows_missing_when_not_on_disk(self, git_repo: Path) -> None:
        register_source(git_repo)
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(
                        commit="abc123",
                        files={"SKILL.md": "sha256:aaa"},
                    ),
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "missing")


class TestStatusGrouping:
    def test_groups_skills_by_source(self, fs: FakeFilesystem, git_repo: Path) -> None:
        install_two_sources(fs, git_repo)

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        source_lines = [
            line.strip()
            for line in lines
            if "project" in line.lower()
            and "synced" not in line.lower()
            and "modified" not in line.lower()
        ]
        assert len(source_lines) == 2


class TestStatusBlankLineSeparation:
    def test_one_blank_line_between_sources(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        install_two_sources(fs, git_repo)

        result = assert_invoke("status")

        lines = result.output.split("\n")
        header_indices = source_header_indices(lines)
        assert len(header_indices) == 2
        # exactly one blank line precedes the second source header
        assert_single_blank_before(lines, header_indices[1])
        # no leading blank line at the very top
        assert lines[0].startswith("Source")

    def test_one_blank_line_before_untracked_after_sources(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        lines = result.output.split("\n")
        untracked_index = untracked_header_index(lines)
        assert_single_blank_before(lines, untracked_index)

    def test_no_leading_blank_when_only_untracked(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        lines = result.output.split("\n")
        assert lines[0].startswith("Untracked")

    def test_combined_sources_and_untracked_layout(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        install_two_sources(fs, git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        lines = result.output.split("\n")
        # first source has no leading blank line at the top
        assert lines[0].startswith("Source")
        # exactly two source headers with one blank line before the second
        header_indices = source_header_indices(lines)
        assert len(header_indices) == 2
        assert_single_blank_before(lines, header_indices[1])
        # exactly one blank line precedes the untracked header
        untracked_index = untracked_header_index(lines)
        assert_single_blank_before(lines, untracked_index)
        # no two consecutive blank lines appear anywhere
        assert_no_double_blank(lines)


class TestStatusMultiProvider:
    def test_shows_status_per_provider(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        install_skill(fs, "tdd", install_dir=cursor_dir)

        register_provider("cursor", str(cursor_dir))

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "claude, cursor", "synced")

    def test_provider_column_aligns_when_providers_comma_joined(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        hashes_tdd = install_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        install_skill(fs, "tdd", install_dir=cursor_dir)
        register_provider("cursor", str(cursor_dir))

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc", files=hashes_tdd),
                )
            }
        )

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        skill_lines = [line for line in lines if line.startswith("  ")]

        # all skill rows must have the status keyword at the same column
        status_positions = []
        for line in skill_lines:
            for keyword in ("synced", "available"):
                idx = line.lower().find(keyword)
                if idx != -1:
                    status_positions.append(idx)
                    break

        assert len(status_positions) >= 2
        assert len(set(status_positions)) == 1, (
            f"Status columns are misaligned: {status_positions}\n"
            f"Lines: {skill_lines}"
        )

    def test_shows_separate_lines_when_statuses_differ(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")

        cursor_dir = Path("/home/user/.cursor/skills")
        install_skill(fs, "tdd", install_dir=cursor_dir)

        register_provider("cursor", str(cursor_dir))

        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        # modify the cursor copy so statuses diverge
        (cursor_dir / "tdd" / "SKILL.md").write_text("# edited by user")

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        tdd_lines = [line for line in lines if "tdd" in line.lower()]
        assert len(tdd_lines) == 2
        assert_words_in_message(result.output, "claude", "synced")
        assert_words_in_message(result.output, "cursor", "modified")


def _create_source_skill(
    fs: FakeFilesystem, name: str, git_root: Path = SOURCE_REPO_ROOT
) -> None:
    loaded = load_source_config(git_root)
    assert loaded.state is ConfigState.OK
    source_cfg = loaded.cfg
    skill_dir = git_root / source_cfg.skills_dirs[0] / name
    fs.create_file(skill_dir / "SKILL.md", contents=f"# {name}")


def _init_source_config(
    fs: FakeFilesystem, git_root: Path = SOURCE_REPO_ROOT, skills_dir: str = "skills"
) -> None:
    cfg = SourceConfig(name=git_root.name, skills_dirs=[skills_dir])
    save_source_config(cfg, git_root)


class TestStatusAvailable:
    def test_shows_available_skill(self, fs: FakeFilesystem, git_repo: Path) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "my-project", "review", "available")


class TestStatusAvailableExcludesInstalled:
    def test_installed_skill_not_shown_as_available(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "tdd", git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "synced")
        assert "available" not in result.output.lower()


class TestStatusMultiDir:
    def test_distinct_skills_from_every_pinned_dir_render(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        cfg = SourceConfig(name=git_repo.name, skills_dirs=["claude/skills", "copilot"])
        save_source_config(cfg, git_repo)

        fs.create_file(git_repo / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(git_repo / "copilot/review/SKILL.md", contents="# review")

        result = assert_invoke("status")

        # the multi-dir merge surfaces a distinct skill from each pinned dir
        assert_words_in_message(result.output, "tdd", "available")
        assert_words_in_message(result.output, "review", "available")
        assert "Warning:" not in result.output


class TestStatusCollision:
    def test_collided_skill_dropped_others_render(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        cfg = SourceConfig(name=git_repo.name, skills_dirs=["claude/skills", "copilot"])
        save_source_config(cfg, git_repo)

        fs.create_file(git_repo / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(git_repo / "copilot/tdd/SKILL.md", contents="# tdd")
        fs.create_file(git_repo / "copilot/review/SKILL.md", contents="# review")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "my-project", "review", "available")
        assert "Warning:" in result.output
        assert "Error:" not in result.output
        # tdd is excluded from the source: it must not appear as an available row
        skill_rows = [
            line for line in result.output.splitlines() if "available" in line.lower()
        ]
        assert all("tdd" not in row for row in skill_rows)
        # the warning survives the full CLI render: it names the colliding skill
        # and lists both colliding rel-paths
        warning_line = next(
            line for line in result.output.splitlines() if "Warning" in line
        )
        assert "tdd" in warning_line
        assert "claude/skills/tdd" in warning_line
        assert "copilot/tdd" in warning_line


class TestStatusEmpty:
    @pytest.mark.usefixtures("fs", "git_repo")
    def test_shows_no_skills_message(self) -> None:
        result = assert_invoke("status")

        assert_words_in_message(result.output, "no skills found")


class TestStatusZeroSkillSource:
    @pytest.mark.usefixtures("fs")
    def test_registered_source_without_skills_shows_placeholder(
        self, git_repo: Path
    ) -> None:
        register_source(git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "my-project")
        lines = result.output.split("\n")
        assert any(line.strip() == "(no skills)" for line in lines)
        assert "no skills found" not in result.output.lower()

    @pytest.mark.usefixtures("fs")
    def test_zero_skill_source_renders_header_and_placeholder_line(
        self, git_repo: Path
    ) -> None:
        register_source(git_repo)

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        assert lines[0].startswith("Source")
        # the placeholder is a separate dim line under the header
        assert any(line.strip() == "(no skills)" for line in lines[1:])

    def test_source_with_installed_skill_has_no_placeholder(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc", files=hashes),
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "synced")
        assert "(no skills)" not in result.output

    def test_source_with_available_skill_has_no_placeholder(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "available")
        assert "(no skills)" not in result.output

    @pytest.mark.usefixtures("git_repo")
    def test_broken_zero_skill_source_has_no_placeholder(
        self, fs: FakeFilesystem
    ) -> None:
        broken_path = Path("/repos/broken-project")
        fs.create_dir(broken_path / ".git")
        registry = SourceRegistry()
        registry.register_source("broken-project", broken_path)
        save_source_registry(registry)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "broken-project", "broken")
        assert "(no skills)" not in result.output

    @pytest.mark.usefixtures("git_repo")
    def test_unregistered_installed_source_still_shows_skills(
        self, fs: FakeFilesystem
    ) -> None:
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="gone-project",
                    baseline=Baseline(commit="abc", files=hashes),
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "gone-project", "tdd", "synced")
        assert "(no skills)" not in result.output

    def test_zero_skill_source_plus_untracked_layout(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        lines = result.output.split("\n")
        assert lines[0].startswith("Source")
        # the zero-skill source renders its placeholder
        assert any(line.strip() == "(no skills)" for line in lines)
        # exactly one blank line precedes the untracked header
        untracked_index = untracked_header_index(lines)
        assert_single_blank_before(lines, untracked_index)
        # no two consecutive blank lines anywhere
        assert_no_double_blank(lines)

    def test_zero_skill_source_mixed_with_populated_source(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        # populated source sorts before the empty one, so the placeholder must
        # land under the second (empty) header, not the first
        populated_repo = git_repo
        empty_repo = OTHER_REPO_ROOT
        fs.create_dir(empty_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("aaa-project", populated_repo)
        registry.register_source("zzz-project", empty_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="aaa-project", skills_dirs=["skills"]), populated_repo
        )
        save_source_config(
            SourceConfig(name="zzz-project", skills_dirs=["skills"]), empty_repo
        )
        fs.create_file(
            populated_repo / "skills" / "review" / "SKILL.md", contents="# review"
        )

        result = assert_invoke("status")

        lines = result.output.split("\n")
        # the populated section shows its available skill row
        assert_words_in_message(result.output, "review", "available")
        # the placeholder appears exactly once
        assert result.output.count("(no skills)") == 1
        # it sits under the empty (second) source header, not the populated one
        header_indices = source_header_indices(lines)
        assert len(header_indices) == 2
        placeholder_index = next(
            i for i, line in enumerate(lines) if line.strip() == "(no skills)"
        )
        assert placeholder_index > header_indices[1]
        # one blank line before the second header, no double blanks
        assert_single_blank_before(lines, header_indices[1])
        assert_no_double_blank(lines)

    def test_zero_skill_source_preserves_section_spacing(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        other_repo = OTHER_REPO_ROOT
        fs.create_dir(other_repo / ".git")
        registry = SourceRegistry()
        registry.register_source("my-project", git_repo)
        registry.register_source("other-project", other_repo)
        save_source_registry(registry)
        save_source_config(
            SourceConfig(name="my-project", skills_dirs=["skills"]), git_repo
        )
        save_source_config(
            SourceConfig(name="other-project", skills_dirs=["skills"]), other_repo
        )

        result = assert_invoke("status")

        lines = result.output.split("\n")
        header_indices = source_header_indices(lines)
        assert len(header_indices) == 2
        # exactly one blank line precedes the second source header
        assert_single_blank_before(lines, header_indices[1])
        # both zero-skill sources still render their placeholder
        assert result.output.count("(no skills)") == 2
        # no two consecutive blank lines anywhere
        assert_no_double_blank(lines)


class TestStatusSourceNotFound:
    @pytest.mark.usefixtures("fs", "git_repo")
    def test_shows_warning_for_missing_source_repo(self) -> None:
        registry = SourceRegistry()
        registry.register_source("gone-project", Path("/repos/gone-project"))
        save_source_registry(registry)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "gone-project", "broken")


class TestStatusBrokenSource:
    @pytest.mark.usefixtures("git_repo")
    def test_shows_broken_for_source_without_config(self, fs: FakeFilesystem) -> None:
        broken_path = Path("/repos/broken-project")
        fs.create_dir(broken_path / ".git")

        registry = SourceRegistry()
        registry.register_source("broken-project", broken_path)
        save_source_registry(registry)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "broken-project", "broken")

    @pytest.mark.usefixtures("git_repo")
    def test_broken_source_label_uses_parentheses(self, fs: FakeFilesystem) -> None:
        broken_path = Path("/repos/broken-project")
        fs.create_dir(broken_path / ".git")

        registry = SourceRegistry()
        registry.register_source("broken-project", broken_path)
        save_source_registry(registry)

        result = assert_invoke("status")

        assert "(broken)" in result.output.lower()

    @pytest.mark.usefixtures("git_repo")
    def test_broken_source_shows_installed_skills(self, fs: FakeFilesystem) -> None:
        broken_path = Path("/repos/broken-project")
        fs.create_dir(broken_path / ".git")

        registry = SourceRegistry()
        registry.register_source("broken-project", broken_path)
        save_source_registry(registry)

        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="broken-project",
                    baseline=Baseline(commit="abc", files=hashes),
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "broken-project", "broken")
        assert_words_in_message(result.output, "tdd", "synced")

    @pytest.mark.usefixtures("git_repo")
    def test_shows_broken_for_malformed_source_config(self, fs: FakeFilesystem) -> None:
        write_broken_source(fs)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "broken-project", "broken")
        assert "(broken)" in result.output.lower()
        assert_words_in_message(result.output, "warning", "broken config file")

    def test_malformed_source_config_warns_exactly_once(
        self, fs: FakeFilesystem
    ) -> None:
        write_broken_source(fs)

        result = assert_invoke("status")

        assert result.output.lower().count("broken config file") == 1
        assert "(broken)" in result.output.lower()


class TestStatusOrphan:
    def test_shows_orphan_for_untracked_skill(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "untracked", "mystery", "orphan")


class TestStatusUntrackedHint:
    def test_available_skill_shows_mergeable_with_provider(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "claude", "mergeable")
        assert "untracked in" not in result.output.lower()

    def test_available_skill_without_untracked_shows_empty_provider(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "available")
        assert "untracked in" not in result.output.lower()

    def test_available_skill_shows_multiple_providers_comma_joined(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        cursor_dir = Path("/home/user/.cursor/skills")
        fs.create_file(cursor_dir / "review" / "SKILL.md", contents="# review cursor")
        register_provider("cursor", str(cursor_dir))

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "claude, cursor", "mergeable")
        assert "untracked in" not in result.output.lower()


class TestStatusMergeable:
    def test_mergeable_not_shown_in_untracked_section(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "claude", "mergeable")


class TestStatusUntrackedOrdering:
    def test_untracked_section_hidden_when_only_mergeables(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        fs.create_file(INSTALL_DIR / "review" / "SKILL.md", contents="# review local")

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        section_headers = [
            line.strip().lower() for line in lines if not line.startswith("  ")
        ]
        assert "untracked" not in section_headers

    def test_orphans_sorted_alphabetically(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "zeta-orphan" / "SKILL.md", contents="# zeta")
        fs.create_file(INSTALL_DIR / "alpha-orphan" / "SKILL.md", contents="# alpha")

        result = assert_invoke("status")

        lines = result.output.strip().split("\n")
        untracked_lines = []
        in_untracked = False
        for line in lines:
            if "untracked" in line.lower():
                in_untracked = True
                continue
            if in_untracked and line.strip():
                untracked_lines.append(line.strip())

        assert len(untracked_lines) == 2
        assert "alpha-orphan" in untracked_lines[0]
        assert "zeta-orphan" in untracked_lines[1]


class TestStatusOrphanMultiProvider:
    def test_orphans_with_multiple_providers_comma_joined(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        fs.create_file(INSTALL_DIR / "mystery" / "SKILL.md", contents="# mystery")

        cursor_dir = Path("/home/user/.cursor/skills")
        fs.create_file(cursor_dir / "mystery" / "SKILL.md", contents="# mystery cursor")
        register_provider("cursor", str(cursor_dir))

        result = assert_invoke("status")

        assert_words_in_message(result.output, "mystery", "claude, cursor", "orphan")


class TestStatusDetached:
    def test_detached_skill_not_shown_as_installed(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )

        result = assert_invoke("status")

        assert "synced" not in result.output.lower()
        assert "modified" not in result.output.lower()
        assert "missing" not in result.output.lower()

    def test_detached_skill_with_source_shown_as_mergeable(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "tdd", git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "mergeable")

    def test_detached_skill_without_source_shown_as_orphan(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project",
                    baseline=Baseline(commit="abc123", files=hashes),
                    detached=True,
                )
            }
        )

        result = assert_invoke("status")

        assert_words_in_message(result.output, "untracked", "tdd", "orphan")


class TestStatusBranchSwitch:
    def test_switches_to_pinned_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="release")
        _fake_git.branch = "feature-x"
        _create_source_skill(fs, "review", git_repo)

        assert_invoke("status")

        assert _fake_git.branch == "release"

    def test_stays_on_correct_branch(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="main")
        _fake_git.branch = "main"
        _create_source_skill(fs, "review", git_repo)

        assert_invoke("status")

        assert _fake_git.branch == "main"

    def test_dirty_repo_on_correct_branch_does_not_block_status(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="main")
        _fake_git.branch = "main"
        _fake_git.clean = False
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "available")

    def test_dirty_repo_needing_branch_switch_does_not_crash(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="release")
        _fake_git.branch = "feature-x"
        _fake_git.clean = False
        _create_source_skill(fs, "review", git_repo)

        result = assert_invoke("status")

        assert_words_in_message(result.output, "review", "available")
        assert_words_in_message(result.output, "dirty", "feature-x", "release")

    @pytest.mark.usefixtures("fs")
    def test_dirty_repo_wrong_branch_missing_skill_not_shown(
        self, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="release")
        _fake_git.branch = "feature-x"
        _fake_git.clean = False

        result = assert_invoke("status")

        assert "available" not in result.output.lower()


class TestStatusSync:
    def test_sync_pulls_source_repos(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("status", "--sync")

        assert _fake_git.pulled is True

    def test_sync_switches_branch_and_pulls(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo, branch="release")
        _fake_git.branch = "feature-x"
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("status", "--sync")

        assert _fake_git.branch == "release"
        assert _fake_git.pulled is True

    def test_no_pull_by_default(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="my-project", baseline=Baseline(commit="abc", files=hashes)
                )
            }
        )

        assert_invoke("status")

        assert _fake_git.pulled is False


class TestStatusBrokenManifest:
    def test_broken_manifest_shows_warning(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        manifest_path = default_config_path(SKILL_MANIFEST_FILE)
        manifest_path.write_text("")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "warning", "broken config file")

    def test_broken_manifest_continues_showing_sources(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        manifest_path = default_config_path(SKILL_MANIFEST_FILE)
        manifest_path.write_text("")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "my-project", "review")


class TestStatusBrokenSourceRegistry:
    @pytest.mark.usefixtures("fs", "git_repo")
    def test_broken_source_registry_shows_warning(self) -> None:
        source_path = default_config_path(SOURCES_REGISTRY_FILE)
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("{{{invalid json")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "warning", "broken config file")


class TestStatusBrokenProviderRegistry:
    def test_broken_provider_registry_shows_warning(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "review", git_repo)
        provider_path = default_config_path(PROVIDERS_REGISTRY_FILE)
        provider_path.write_text("{{{invalid json")

        result = assert_invoke("status")

        assert_words_in_message(result.output, "warning", "broken config file")


def _setup_installed_skill(
    fs: FakeFilesystem,
    git_repo: Path,
    commit: str = "old123",
    *,
    create_in_source: bool = True,
) -> dict[str, str]:
    register_source(git_repo)
    _init_source_config(fs, git_repo)
    if create_in_source:
        _create_source_skill(fs, "tdd", git_repo)
    hashes = install_skill(fs, "tdd")
    save_manifest(
        {
            "tdd": InstalledSkill(
                source="my-project",
                baseline=Baseline(commit=commit, files=hashes),
            )
        }
    )
    return hashes


class TestStatusOutdated:
    def test_synced_but_outdated(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_installed_skill(fs, git_repo)
        _fake_git.branch_commits = {("skills/tdd", "main"): "new456"}

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "synced", "outdated")

    def test_modified_and_outdated(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_installed_skill(fs, git_repo)
        (INSTALL_DIR / "tdd" / "SKILL.md").write_text("# edited")
        _fake_git.branch_commits = {("skills/tdd", "main"): "new456"}

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "modified", "outdated")

    def test_no_outdated_when_commits_match(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_installed_skill(fs, git_repo, "abc123")
        _fake_git.branch_commits = {("skills/tdd", "main"): "abc123"}

        result = assert_invoke("status")

        assert_words_in_message(result.output, "tdd", "synced")
        assert "outdated" not in result.output.lower()

    def test_no_outdated_when_no_baseline(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        register_source(git_repo)
        _init_source_config(fs, git_repo)
        _create_source_skill(fs, "tdd", git_repo)
        install_skill(fs, "tdd")
        save_manifest({"tdd": InstalledSkill(source="my-project", baseline=None)})
        _fake_git.branch_commits = {("skills/tdd", "main"): "new456"}

        result = assert_invoke("status")

        assert "outdated" not in result.output.lower()

    @pytest.mark.usefixtures("git_repo")
    def test_no_outdated_when_broken_source(self, fs: FakeFilesystem) -> None:
        broken_path = Path("/repos/broken-project")
        fs.create_dir(broken_path / ".git")
        registry = SourceRegistry()
        registry.register_source("broken-project", broken_path)
        save_source_registry(registry)
        hashes = install_skill(fs, "tdd")
        save_manifest(
            {
                "tdd": InstalledSkill(
                    source="broken-project",
                    baseline=Baseline(commit="old123", files=hashes),
                )
            }
        )

        result = assert_invoke("status")

        assert "outdated" not in result.output.lower()

    def test_no_outdated_when_get_skill_commit_empty(
        self, fs: FakeFilesystem, git_repo: Path
    ) -> None:
        _setup_installed_skill(fs, git_repo)

        result = assert_invoke("status")

        assert "outdated" not in result.output.lower()

    def test_no_outdated_when_skill_removed_from_source(
        self, fs: FakeFilesystem, git_repo: Path, _fake_git: FakeGitRepo
    ) -> None:
        _setup_installed_skill(fs, git_repo, create_in_source=False)
        _fake_git.branch_commits = {("skills/tdd", "main"): "new456"}

        result = assert_invoke("status")

        assert "outdated" not in result.output.lower()
