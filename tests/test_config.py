from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

from repo_skills.config import (
    Baseline,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceConfig,
    SourceRegistry,
    compute_file_hashes,
    default_config_path,
    load_provider_registry,
    load_skill_manifest,
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
from repo_skills.config._source import _collect_source_skills
from repo_skills.errors import AppError
from repo_skills.utils import rel_posix, to_posix_path
from tests.cli.helper import FakeGitRepo

# -- Source.get_branch --


class TestGetBranch:
    def test_returns_config_branch_when_set(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dir="skills", branch="develop"),
            skills={},
        )
        git = FakeGitRepo(main_branch="main")
        assert source.get_branch(git) == "develop"

    def test_falls_back_to_main_when_empty(self) -> None:
        source = Source(
            repo_root=Path("/repo"),
            config=SourceConfig(name="", skills_dir="skills"),
            skills={},
        )
        git = FakeGitRepo(main_branch="trunk")
        assert source.get_branch(git) == "trunk"


# -- default_config_dir --


class TestDefaultConfigDir:
    def test_returns_xdg_when_set(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", "/custom/config")
        result = default_config_path()
        assert result == Path("/custom/config/repo-skills")

    def test_falls_back_to_dot_config(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", "/home/testuser")
        result = default_config_path()
        assert result == Path("/home/testuser/.config/repo-skills")


# -- SourceConfig --


class TestSourceConfig:
    def test_load_missing_returns_none(self, fs: FakeFilesystem) -> None:
        cfg = load_source_config(Path("/nonexistent"))
        assert cfg is None

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/repo")
        cfg = SourceConfig(name="my-repo", skills_dir="custom/skills", branch="develop")
        save_source_config(cfg, repo_root)

        loaded = load_source_config(repo_root)
        assert loaded is not None
        assert loaded.name == "my-repo"
        assert loaded.skills_dir == "custom/skills"
        assert loaded.branch == "develop"

    def test_load_legacy_without_branch_defaults_to_empty(
        self, fs: FakeFilesystem
    ) -> None:
        path = Path("/repo/.repo-skills/source.json")
        fs.create_file(path, contents='{"name": "old-repo", "skills_dir": "skills"}')
        cfg = load_source_config(Path("/repo"))
        assert cfg is not None
        assert cfg.branch == ""

    def test_save_creates_parent_dirs(self, fs: FakeFilesystem) -> None:
        repo_root = Path("/deep/nested/dir")
        cfg = SourceConfig(name="test", skills_dir="skills")
        save_source_config(cfg, repo_root)
        assert (repo_root / ".repo-skills" / "source.json").exists()


# -- Provider / ProviderRegistry --


class TestProviderRegistry:
    def test_load_missing_file_creates_with_default_provider(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        assert reg.is_registered("claude")
        assert reg.require("claude").install_path == Path("/home/user/.claude/skills")

    def test_load_existing_v1_does_not_reinject_defaults(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = load_provider_registry()
        reg.unregister("claude")
        save_provider_registry(reg)

        reloaded = load_provider_registry()
        assert not reloaded.is_registered("claude")

    def test_install_path_resolves_tilde(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", "/home/user")
        reg = ProviderRegistry()
        prov = reg.register("test", "~/my-skills")
        assert prov.install_path == Path("/home/user/my-skills")

    def test_save_and_load_round_trip(
        self, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        with pytest.raises(AppError):
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

        with pytest.raises(AppError) as exc:
            load_provider_registry()

        assert str(PROVIDER_CURRENT_VERSION + 1) in exc.value.message


# -- SourceRegistry --


class TestSourceRegistry:
    def test_empty_registry_has_no_sources(self, fs: FakeFilesystem) -> None:
        reg = SourceRegistry()
        assert reg.sources == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
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
    def test_load_missing_file_returns_empty(self, fs: FakeFilesystem) -> None:
        manifest = load_skill_manifest()
        assert dict(manifest.skills) == {}

    def test_save_and_load_round_trip(self, fs: FakeFilesystem) -> None:
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

    def test_save_and_load_round_trip_with_none_baseline(
        self, fs: FakeFilesystem
    ) -> None:
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

        with pytest.raises(AppError) as exc:
            load_skill_manifest()

        assert str(CURRENT_VERSION + 1) in exc.value.message
        assert str(CURRENT_VERSION) in exc.value.message

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

        skills = _collect_source_skills(repo_root, "skills")
        assert "tdd" in skills
        rel = skills["tdd"].rel_path
        assert "/" in rel or "\\" not in rel
        assert "\\" not in rel
        assert rel == "skills/tdd"


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

    def test_returns_none_when_file_missing(self, fs: FakeFilesystem) -> None:
        assert read_skill_description(Path("/skills/missing")) is None
