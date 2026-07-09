from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from cli_error import CliError, render_error
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    Baseline,
    ConfigState,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceBrokenError,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    default_config_path,
    load_provider_registry,
    load_skill_manifest,
    load_source,
    load_source_config,
    load_source_registry,
    read_skill_description,
    save_provider_registry,
    save_skill_manifest,
    save_source_config,
    save_source_registry,
)
from repo_skills.config._provider_registry import (
    CURRENT_VERSION as PROVIDER_CURRENT_VERSION,
)
from repo_skills.config._skill_manifest import (
    CURRENT_VERSION,
    SKILL_MANIFEST_FILE,
)
from repo_skills.config._source import SOURCE_CONFIG_PATH, _collect_source_skills
from repo_skills.utils import rel_posix, to_posix_path
from tests.cli.helper import FakeGitRepo

# -- Source.get_branch --


class TestGetBranch:
    def test_returns_config_branch_when_set(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dirs=["skills"], branch="develop"),
            skills={},
        )
        git = FakeGitRepo(main_branch="main")
        assert source.get_branch(git) == "develop"

    def test_falls_back_to_main_when_empty(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dirs=["skills"]),
            skills={},
        )
        git = FakeGitRepo(main_branch="trunk")
        assert source.get_branch(git) == "trunk"


# -- default_config_dir --


class TestDefaultConfigDir:
    @pytest.mark.usefixtures("fs")
    def test_returns_xdg_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = default_config_path()
        assert result == Path("/custom/config/repo-skills")

    @pytest.mark.usefixtures("fs")
    def test_falls_back_to_dot_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", "/home/testuser")
        result = default_config_path()
        assert result == Path("/home/testuser/.config/repo-skills")


# -- SourceConfig --


class TestSourceConfig:
    @pytest.mark.usefixtures("fs")
    def test_load_missing_yields_missing_state(self) -> None:
        result = load_source_config(Path("/nonexistent"))
        assert result.state is ConfigState.MISSING

    @pytest.mark.usefixtures("fs")
    def test_save_and_load_round_trip(self) -> None:
        repo_root = Path("/repo")
        cfg = SourceConfig(
            name="my-repo", skills_dirs=["custom/skills"], branch="develop"
        )
        save_source_config(cfg, repo_root)

        loaded = load_source_config(repo_root)
        assert loaded.state is ConfigState.OK
        assert loaded.cfg.name == "my-repo"
        assert loaded.cfg.skills_dirs == ["custom/skills"]
        assert loaded.cfg.branch == "develop"

    @pytest.mark.usefixtures("fs")
    def test_save_writes_version_and_skills_dirs_array(self) -> None:
        repo_root = Path("/repo")
        cfg = SourceConfig(name="my-repo", skills_dirs=["a", "b"], branch="develop")
        save_source_config(cfg, repo_root)

        on_disk = json.loads((repo_root / SOURCE_CONFIG_PATH).read_text())
        assert on_disk["version"] == 1
        assert on_disk["skills_dirs"] == ["a", "b"]
        assert "skills_dir" not in on_disk

        loaded = load_source_config(repo_root)
        assert loaded.state is ConfigState.OK
        assert loaded.cfg.skills_dirs == ["a", "b"]

    def test_load_legacy_without_branch_defaults_to_empty(
        self, fs: FakeFilesystem
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents='{"name": "old-repo", "skills_dir": "skills"}')
        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        assert result.cfg.branch == ""

    def test_load_legacy_migrates_to_skills_dirs(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(
            path,
            contents='{"name": "x", "skills_dir": "skills", "branch": "main"}',
        )

        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        cfg = result.cfg
        assert cfg.skills_dirs == ["skills"]
        assert cfg.name == "x"
        assert cfg.branch == "main"

        # a parseable v0 file must migrate cleanly, not be flagged as broken
        assert "broken config file" not in capsys.readouterr().out.lower()

        on_disk = json.loads(path.read_text())
        assert on_disk["version"] == 1
        assert on_disk["skills_dirs"] == ["skills"]
        assert "skills_dir" not in on_disk
        assert on_disk["name"] == "x"
        assert on_disk["branch"] == "main"

    @pytest.mark.parametrize(
        "contents",
        [
            pytest.param('{"name": "x", "branch": "main"}', id="absent-skills-dir"),
            pytest.param(
                '{"name": "x", "skills_dir": "", "branch": "m"}',
                id="empty-skills-dir",
            ),
        ],
    )
    def test_load_legacy_empty_dir_yields_empty_list(
        self, fs: FakeFilesystem, contents: str
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents=contents)

        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        assert result.cfg.skills_dirs == []

    @pytest.mark.parametrize(
        "contents",
        [
            pytest.param(
                '{"name": "x", "skills_dir": null, "branch": "m"}',
                id="null-skills-dir",
            ),
            pytest.param(
                '{"name": "x", "skills_dir": ["a", "b"], "branch": "m"}',
                id="list-skills-dir",
            ),
        ],
    )
    def test_load_legacy_non_string_dir_migrates_to_empty_list(
        self, fs: FakeFilesystem, contents: str
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents=contents)

        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        assert result.cfg.skills_dirs == []

    def test_load_legacy_preserves_non_enumerated_fields(
        self, fs: FakeFilesystem
    ) -> None:
        # migration must carry forward every SourceConfig field via
        # model_validate(raw), not a hand-maintained allow-list. `branch` is a
        # field the old migration only forwarded explicitly; an unknown extra
        # key proves fields are read straight off the raw dict.
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(
            path,
            contents=(
                '{"name": "x", "skills_dir": "skills", "branch": "dev", '
                '"future_field": "kept"}'
            ),
        )

        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        cfg = result.cfg
        assert cfg.name == "x"
        assert cfg.branch == "dev"
        assert cfg.skills_dirs == ["skills"]

        on_disk = json.loads(path.read_text())
        assert on_disk["version"] == 1
        assert on_disk["name"] == "x"
        assert on_disk["branch"] == "dev"
        assert on_disk["skills_dirs"] == ["skills"]
        assert "skills_dir" not in on_disk
        # pydantic drops unknown fields, so legacy extras are not persisted
        assert "future_field" not in on_disk

    def test_load_legacy_without_name_migrates_to_empty_name(
        self, fs: FakeFilesystem
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents='{"skills_dir": "skills"}')

        result = load_source_config(Path("/repo"))
        assert result.state is ConfigState.OK
        assert result.cfg.name == ""
        assert result.cfg.skills_dirs == ["skills"]

    def test_load_v1_does_not_resave(self, fs: FakeFilesystem) -> None:
        path = Path("/repo/.repo-skills/source.json")
        contents = (
            '{"version": 1, "name": "x", "skills_dirs": ["skills"], "branch": "main"}'
        )
        fs.create_file(path, contents=contents)

        load_source_config(Path("/repo"))
        assert path.read_text() == contents

    def test_load_newer_version_raises(self, fs: FakeFilesystem) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(
            path,
            contents='{"version": 2, "name": "x", "skills_dirs": ["s"]}',
        )

        with pytest.raises(CliError, match="newer version"):
            load_source_config(Path("/repo"))

    def test_load_malformed_yields_broken_and_warns(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents="{not valid json")
        before = path.read_text()

        assert load_source_config(Path("/repo")).state is ConfigState.BROKEN

        warning = capsys.readouterr().out.lower()
        assert "warning" in warning
        assert "broken config file" in warning
        assert path.read_text() == before

    def test_load_non_object_json_yields_broken_and_warns(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents="[1, 2, 3]")

        assert load_source_config(Path("/repo")).state is ConfigState.BROKEN
        assert "broken config file" in capsys.readouterr().out.lower()

    def test_load_source_malformed_raises_source_broken(
        self, fs: FakeFilesystem
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents="{not valid json")

        with pytest.raises(SourceBrokenError):
            load_source(Path("/repo"), load_skills=False)

    @pytest.mark.usefixtures("fs")
    def test_load_source_with_empty_skills_dirs_yields_no_skills(self) -> None:
        repo_root = Path("/repo")
        save_source_config(SourceConfig(name="x", skills_dirs=[]), repo_root)

        source = load_source(repo_root, load_skills=True)
        assert source.skills == {}

    @pytest.mark.usefixtures("fs")
    def test_save_creates_parent_dirs(self) -> None:
        repo_root = Path("/deep/nested/dir")
        cfg = SourceConfig(name="test", skills_dirs=["skills"])
        save_source_config(cfg, repo_root)
        assert (repo_root / ".repo-skills" / "source.json").exists()


# -- Provider / ProviderRegistry --


class TestProviderRegistry:
    @pytest.mark.usefixtures("fs")
    def test_load_missing_file_creates_with_default_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        assert reg.is_registered("claude")
        assert reg.require("claude").install_path == Path("/home/user/.claude/skills")

    @pytest.mark.usefixtures("fs")
    def test_load_existing_v1_does_not_reinject_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        reg.unregister("claude")
        save_provider_registry(reg)

        reloaded = load_provider_registry()
        assert not reloaded.is_registered("claude")

    @pytest.mark.usefixtures("fs")
    def test_install_path_resolves_tilde(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = ProviderRegistry()
        prov = reg.register("test", "~/my-skills")
        assert prov.install_path == Path("/home/user/my-skills")

    @pytest.mark.usefixtures("fs")
    def test_save_and_load_round_trip(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        reg.register("cursor", "/opt/cursor/skills")
        save_provider_registry(reg)

        reloaded = load_provider_registry()
        assert len(reloaded.providers) == 2
        assert reloaded.require("claude").install_path == Path(
            "/home/user/.claude/skills"
        )
        assert reloaded.require("cursor").install_path == Path("/opt/cursor/skills")

    def test_require_unknown_raises(self) -> None:
        reg = ProviderRegistry()
        with pytest.raises(CliError):
            reg.require("nonexistent")

    def test_require_returns_registered_provider(self) -> None:
        reg = ProviderRegistry()
        reg.register("test", "/opt/test")
        provider = reg.require("test")
        assert provider.name == "test"
        assert provider.install_path == Path("/opt/test")

    def test_unregister_removes_provider(self) -> None:
        reg = ProviderRegistry()
        reg.register("test", "/opt/test")
        reg.unregister("test")
        assert not reg.is_registered("test")

    def test_unregister_missing_is_noop(self) -> None:
        reg = ProviderRegistry()
        reg.unregister("nonexistent")

    def test_load_unversioned_file_migrates_and_injects_defaults(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        path = default_config_path("providers.json")
        data = {"providers": {"custom": {"install_dir": "/custom/path"}}}
        fs.create_file(path, contents=json.dumps(data))

        reg = load_provider_registry()
        assert reg.is_registered("custom")
        assert reg.is_registered("claude")

    def test_load_newer_version_raises(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        path = default_config_path("providers.json")
        data = {
            "version": PROVIDER_CURRENT_VERSION + 1,
            "providers": {"custom": {"install_dir": "/custom/path"}},
        }
        fs.create_file(path, contents=json.dumps(data))

        with pytest.raises(CliError) as exc:
            load_provider_registry()

        assert str(PROVIDER_CURRENT_VERSION + 1) in render_error(exc.value.desc)


# -- SourceRegistry --


class TestSourceRegistry:
    @pytest.mark.usefixtures("fs")
    def test_empty_registry_has_no_sources(self) -> None:
        reg = SourceRegistry()
        assert reg.sources == {}

    @pytest.mark.usefixtures("fs")
    def test_save_and_load_round_trip(self) -> None:
        reg = SourceRegistry()
        reg.register_source("my-repo", Path("/home/user/projects/my-repo"))
        reg.register_source("other", Path("/opt/other"))
        save_source_registry(reg)

        loaded = load_source_registry()
        assert len(loaded.sources) == 2
        assert loaded.sources["my-repo"].repo_root == Path(
            "/home/user/projects/my-repo"
        )
        assert loaded.sources["other"].repo_root == Path("/opt/other")


# -- SkillManifest --


class TestSkillManifest:
    @pytest.mark.usefixtures("fs")
    def test_load_missing_file_returns_empty(self) -> None:
        manifest = load_skill_manifest()
        assert dict(manifest.skills) == {}

    @pytest.mark.usefixtures("fs")
    def test_save_and_load_round_trip(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill(
            "tdd",
            source_name="my-repo",
            baseline=Baseline(
                commit="abc1234",
                files={"SKILL.md": "sha256:deadbeef"},
            ),
        )
        save_skill_manifest(manifest)

        loaded = load_skill_manifest()
        assert "tdd" in loaded.skills
        entry = loaded.skills["tdd"]
        assert entry.source == "my-repo"
        assert entry.baseline is not None
        assert entry.baseline.commit == "abc1234"
        assert entry.baseline.files == {"SKILL.md": "sha256:deadbeef"}

    @pytest.mark.usefixtures("fs")
    def test_save_and_load_round_trip_with_none_baseline(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill("tdd", source_name="my-repo", baseline=None)
        save_skill_manifest(manifest)

        loaded = load_skill_manifest()
        assert "tdd" in loaded.skills
        entry = loaded.skills["tdd"]
        assert entry.source == "my-repo"
        assert entry.baseline is None

    def test_version_gating_returns_empty_for_missing_version(
        self, fs: FakeFilesystem
    ) -> None:
        path = default_config_path(SKILL_MANIFEST_FILE)
        data = {"skills": {"tdd": {"source": "my-repo", "commit": "abc"}}}
        fs.create_file(path, contents=json.dumps(data))

        loaded = load_skill_manifest()
        assert dict(loaded.skills) == {}

    def test_version_gating_returns_empty_for_older_version(
        self, fs: FakeFilesystem
    ) -> None:
        path = default_config_path(SKILL_MANIFEST_FILE)
        data = {
            "version": CURRENT_VERSION - 1,
            "skills": {"tdd": {"source": "my-repo", "commit": "abc"}},
        }
        fs.create_file(path, contents=json.dumps(data))

        loaded = load_skill_manifest()
        assert dict(loaded.skills) == {}

    def test_version_gating_raises_for_newer_version(self, fs: FakeFilesystem) -> None:
        path = default_config_path(SKILL_MANIFEST_FILE)
        data = {
            "version": CURRENT_VERSION + 1,
            "skills": {"tdd": {"source": "my-repo", "commit": "abc"}},
        }
        fs.create_file(path, contents=json.dumps(data))

        with pytest.raises(CliError) as exc:
            load_skill_manifest()

        assert str(CURRENT_VERSION + 1) in render_error(exc.value.desc)
        assert str(CURRENT_VERSION) in render_error(exc.value.desc)

    def test_version_gating_loads_for_current_version(self, fs: FakeFilesystem) -> None:
        path = default_config_path(SKILL_MANIFEST_FILE)
        data = {
            "version": CURRENT_VERSION,
            "skills": {"tdd": {"source": "my-repo", "commit": "abc"}},
        }
        fs.create_file(path, contents=json.dumps(data))

        loaded = load_skill_manifest()
        assert "tdd" in loaded.skills
        entry = loaded.skills["tdd"]
        assert entry.source == "my-repo"
        assert entry.baseline is not None
        assert entry.baseline.commit == "abc"

    def test_register_skill(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill(
            "tdd",
            source_name="my-repo",
            baseline=Baseline(commit="abc"),
        )
        assert "tdd" in manifest.skills
        assert manifest.skills["tdd"].source == "my-repo"
        assert manifest.skills["tdd"].baseline is not None
        assert manifest.skills["tdd"].baseline.commit == "abc"

    def test_unregister_skill(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill("tdd", source_name="my-repo")
        manifest.unregister_skill("tdd")
        assert "tdd" not in manifest.skills

    def test_skills_property_returns_mapping(self) -> None:
        manifest = SkillManifest()
        manifest.register_skill("tdd", source_name="my-repo")
        assert isinstance(manifest.skills, Mapping)


# -- compute_file_hashes --


class TestComputeFileHashes:
    def test_single_file(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="# TDD skill")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 1
        assert "SKILL.md" in hashes

        expected = "sha256:" + hashlib.sha256(b"# TDD skill").hexdigest()
        assert hashes["SKILL.md"] == expected

    def test_multiple_files(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="# TDD")
        fs.create_file(skill_dir / "tests.md", contents="# Tests")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 2
        assert "SKILL.md" in hashes
        assert "tests.md" in hashes

    def test_nested_files(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="top")
        fs.create_file(skill_dir / "sub" / "deep.md", contents="nested")

        hashes = compute_file_hashes(skill_dir)
        assert len(hashes) == 2
        assert "SKILL.md" in hashes
        assert "sub/deep.md" in hashes

    def test_empty_directory(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/empty")
        fs.create_dir(skill_dir)

        hashes = compute_file_hashes(skill_dir)
        assert hashes == {}

    def test_hash_format(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "SKILL.md", contents="content")

        hashes = compute_file_hashes(skill_dir)
        value = hashes["SKILL.md"]
        assert value.startswith("sha256:")
        hex_part = value.split(":")[1]
        assert len(hex_part) == 64
        assert all(c in "0123456789abcdef" for c in hex_part)

    def test_crlf_and_lf_produce_same_hash(self, fs: FakeFilesystem) -> None:
        lf_dir = Path("/skills/lf")
        crlf_dir = Path("/skills/crlf")
        fs.create_file(lf_dir / "SKILL.md", contents="line1\nline2\n")
        fs.create_file(
            crlf_dir / "SKILL.md",
            contents=b"line1\r\nline2\r\n",
        )

        lf_hashes = compute_file_hashes(lf_dir)
        crlf_hashes = compute_file_hashes(crlf_dir)
        assert lf_hashes["SKILL.md"] == crlf_hashes["SKILL.md"]

    def test_keys_use_forward_slashes(self, fs: FakeFilesystem) -> None:
        skill_dir = Path("/skills/tdd")
        fs.create_file(skill_dir / "sub" / "nested" / "file.md", contents="deep")

        hashes = compute_file_hashes(skill_dir)
        keys = list(hashes.keys())
        assert len(keys) == 1
        assert keys[0] == "sub/nested/file.md"
        assert "\\" not in keys[0]


# -- to_posix_path --


class TestToPosixPath:
    def test_converts_backslashes(self) -> None:
        assert to_posix_path("sub\\nested\\file.md") == "sub/nested/file.md"

    def test_leaves_forward_slashes_unchanged(self) -> None:
        assert to_posix_path("sub/nested/file.md") == "sub/nested/file.md"

    def test_mixed_slashes(self) -> None:
        assert to_posix_path("sub\\nested/file.md") == "sub/nested/file.md"

    def test_empty_string(self) -> None:
        assert to_posix_path("") == ""

    def test_no_slashes(self) -> None:
        assert to_posix_path("file.md") == "file.md"


# -- rel_posix --


class TestRelPosix:
    def test_basic(self) -> None:
        assert rel_posix(Path("/repo/skills/tdd"), Path("/repo")) == "skills/tdd"

    def test_single_component(self) -> None:
        assert rel_posix(Path("/repo/file.md"), Path("/repo")) == "file.md"

    def test_same_path(self) -> None:
        assert rel_posix(Path("/repo"), Path("/repo")) == "."


# -- _collect_source_skills posix paths --


class TestCollectSourceSkillsPosixPaths:
    def test_rel_path_uses_forward_slashes(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "skills" / "tdd" / "SKILL.md", contents="# TDD")

        skills = _collect_source_skills(repo_root, ["skills"])
        assert "tdd" in skills
        rel = skills["tdd"].rel_path
        assert "/" in rel or "\\" not in rel
        assert "\\" not in rel
        assert rel == "skills/tdd"


class TestCollectSourceSkillsMultiDir:
    def test_merges_skills_across_dirs(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "copilot/review/SKILL.md", contents="# review")

        skills = _collect_source_skills(repo_root, ["claude/skills", "copilot"])

        assert set(skills) == {"tdd", "review"}
        assert skills["tdd"].rel_path == "claude/skills/tdd"
        assert skills["review"].rel_path == "copilot/review"

    def test_nested_skill_md_inside_a_skill_is_not_a_separate_skill(
        self, fs: FakeFilesystem
    ) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(
            repo_root / "claude/skills/tdd/inner/SKILL.md", contents="# inner"
        )

        skills = _collect_source_skills(repo_root, ["claude/skills"])

        assert set(skills) == {"tdd"}

    def test_skill_under_hidden_dir_is_not_collected(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "skills/.archive/foo/SKILL.md", contents="# foo")
        fs.create_file(repo_root / "skills/tdd/SKILL.md", contents="# tdd")

        skills = _collect_source_skills(repo_root, ["skills"])

        assert set(skills) == {"tdd"}

    def test_missing_dir_is_skipped(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "copilot/review/SKILL.md", contents="# review")

        skills = _collect_source_skills(repo_root, ["claude/skills", "copilot"])

        assert set(skills) == {"review"}

    def test_empty_dirs_list_yields_no_skills(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "skills/tdd/SKILL.md", contents="# tdd")

        assert _collect_source_skills(repo_root, []) == {}

    def test_overlapping_dirs_collect_same_skill_once_without_warning(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo-overlap")
        fs.create_file(repo_root / "skills/group/tdd/SKILL.md", contents="# tdd")

        skills = _collect_source_skills(repo_root, ["skills", "skills/group"])

        assert set(skills) == {"tdd"}
        assert skills["tdd"].rel_path == "skills/group/tdd"

        out = capsys.readouterr().out
        assert "Warning" not in out

    def test_collision_excludes_all_copies_and_reports(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "copilot/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "copilot/review/SKILL.md", contents="# review")

        skills = _collect_source_skills(repo_root, ["claude/skills", "copilot"])

        assert "tdd" not in skills
        assert set(skills) == {"review"}

        out = capsys.readouterr().out
        assert "Warning" in out
        assert "Error:" not in out
        assert "tdd" in out
        assert "claude/skills" in out
        assert "copilot" in out

    def test_three_dir_collision_reported_once_and_fully_excluded(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo")
        fs.create_file(repo_root / "alpha/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "bravo/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "charlie/tdd/SKILL.md", contents="# tdd")

        skills = _collect_source_skills(repo_root, ["alpha", "bravo", "charlie"])

        assert skills == {}

        out = capsys.readouterr().out
        assert out.count("Warning") == 1
        assert "Error:" not in out
        assert "alpha" in out and "bravo" in out and "charlie" in out

    def test_collision_warning_lists_dirs_in_discovery_order(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo-order")
        fs.create_file(repo_root / "copilot/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "claude/skills/tdd/SKILL.md", contents="# tdd")

        _collect_source_skills(repo_root, ["copilot", "claude/skills"])

        out = capsys.readouterr().out
        # scan order, not the sorted view: the first-scanned dir is listed first
        assert out.index("copilot/tdd") < out.index("claude/skills/tdd")

    def test_intra_dir_duplicate_basename_excluded_and_reported(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo-intra")
        fs.create_file(repo_root / "skills/group-a/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "skills/group-b/tdd/SKILL.md", contents="# tdd")

        skills = _collect_source_skills(repo_root, ["skills"])

        assert "tdd" not in skills

        out = capsys.readouterr().out
        assert "Warning" in out
        assert "tdd" in out
        # each colliding copy is located by its full path, so the two subdirs
        # under the same skills dir are distinguishable
        assert "skills/group-a/tdd" in out
        assert "skills/group-b/tdd" in out

    def test_repeated_load_of_colliding_source_warns_each_load(
        self, fs: FakeFilesystem, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo_root = Path("/repo-twice")
        fs.create_file(repo_root / "claude/skills/tdd/SKILL.md", contents="# tdd")
        fs.create_file(repo_root / "copilot/tdd/SKILL.md", contents="# tdd")
        dirs = ["claude/skills", "copilot"]

        # dedup is scoped to a single load, so each load reports the collision
        # afresh rather than suppressing it via process-wide state
        _collect_source_skills(repo_root, dirs)
        _collect_source_skills(repo_root, dirs)

        out = capsys.readouterr().out
        assert out.count("Warning") == 2


def _write_skill(fs: FakeFilesystem, contents: str) -> Path:
    skill_dir = Path("/skills/tdd")
    fs.create_file(skill_dir / "SKILL.md", contents=contents)
    return skill_dir


class TestReadSkillDescription:
    @pytest.mark.parametrize(
        "contents, expected",
        [
            pytest.param(
                (
                    "---\n"
                    "name: tdd\n"
                    "description: Do the thing well.\n"
                    "disable-model-invocation: true\n"
                    "---\n\n# tdd\n"
                ),
                "Do the thing well.",
                id="present",
            ),
            pytest.param(
                "---\nname: tdd\n---\n\n# tdd\n",
                None,
                id="no-description",
            ),
            pytest.param(
                "# brand new\n",
                None,
                id="no-frontmatter",
            ),
            pytest.param(
                "---\nname: tdd\ndescription:\n---\n\n# tdd\n",
                None,
                id="empty",
            ),
            pytest.param(
                "---\nname: tdd\ndescription:    \n---\n\n# tdd\n",
                None,
                id="whitespace-only",
            ),
            pytest.param(
                "---\nname: tdd\ndescription:    Spaced out   \n---\n\n# tdd\n",
                "Spaced out",
                id="trimmed",
            ),
            pytest.param(
                (
                    "---\r\n"
                    "name: tdd\r\n"
                    "description: Does a thing.\r\n"
                    "---\r\n\r\n# tdd\r\n"
                ),
                "Does a thing.",
                id="crlf",
            ),
            pytest.param(
                '---\nname: tdd\ndescription: "Does X"\n---\n\n# tdd\n',
                "Does X",
                id="double-quoted",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: 'Does Y'\n---\n\n# tdd\n",
                "Does Y",
                id="single-quoted",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: >\n---\n\n# tdd\n",
                None,
                id="block-scalar-fold",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: |\n---\n\n# tdd\n",
                None,
                id="block-scalar-literal",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: >-\n---\n\n# tdd\n",
                None,
                id="block-scalar-fold-strip",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: |-\n---\n\n# tdd\n",
                None,
                id="block-scalar-literal-strip",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: |\n  Real body line\n---\n\n# tdd\n",
                None,
                id="block-scalar-populated-body",
            ),
            pytest.param(
                '---\nname: tdd\ndescription: "oops\n---\n\n# tdd\n',
                '"oops',
                id="unterminated-quote",
            ),
            pytest.param(
                '---\nname: tdd\ndescription: ""\n---\n\n# tdd\n',
                None,
                id="quoted-empty",
            ),
            pytest.param(
                '---\nname: tdd\ndescription: He said "hi"\n---\n\n# tdd\n',
                'He said "hi"',
                id="inner-quote",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: >foo\n---\n\n# tdd\n",
                None,
                id="leading-fold-treated-as-block-scalar",
            ),
            pytest.param(
                "---\nname: tdd\ndescription: |bar\n---\n\n# tdd\n",
                None,
                id="leading-literal-treated-as-block-scalar",
            ),
        ],
    )
    def test_reads_description(
        self, fs: FakeFilesystem, contents: str, expected: str | None
    ) -> None:
        skill_dir = _write_skill(fs, contents)
        assert read_skill_description(skill_dir) == expected

    @pytest.mark.usefixtures("fs")
    def test_returns_none_when_file_missing(self) -> None:
        assert read_skill_description(Path("/skills/missing")) is None
