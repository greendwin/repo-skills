from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Self, TypeAlias

from pydantic import BaseModel

REPO_SKILLS_DIR = ".repo-skills"
SOURCE_CONFIG_FILE = "source.json"
SOURCES_REGISTRY_FILE = "sources.json"
SKILL_MANIFEST_FILE = "skill-manifest.json"
PROVIDERS_REGISTRY_FILE = "providers.json"

BUILTIN_PROVIDER_NAME = "claude"
BUILTIN_PROVIDER_INSTALL_DIR = "~/.claude/skills"


def default_config_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "repo-skills"


RelPathHashes: TypeAlias = dict[str, str]


def compute_file_hashes(skill_dir: Path) -> RelPathHashes:
    result: RelPathHashes = {}
    for dirpath, _, filenames in os.walk(skill_dir):
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            rel = str(full.relative_to(skill_dir))
            sha = hashlib.sha256(full.read_bytes()).hexdigest()
            result[rel] = f"sha256:{sha}"

    return result


class _Saveable(BaseModel):
    @classmethod
    def load(cls, path: Path) -> Self:
        if not os.path.exists(path):
            return cls()
        with open(path) as f:
            data = f.read()
        return cls.model_validate_json(data)

    def save(self, path: Path) -> None:
        os.makedirs(str(path.parent), exist_ok=True)
        with open(str(path), "w") as f:
            f.write(self.model_dump_json(indent=2) + "\n")


class SourceConfig(_Saveable):
    name: str = ""
    skills_dir: str = "skills"


class ProviderConfig(BaseModel):
    name: str = ""
    install_dir: str = ""


class ProviderRegistry(_Saveable):
    providers: dict[str, ProviderConfig] = {}

    def with_builtins(self) -> ProviderRegistry:
        if BUILTIN_PROVIDER_NAME not in self.providers:
            merged = {
                BUILTIN_PROVIDER_NAME: ProviderConfig(
                    name=BUILTIN_PROVIDER_NAME,
                    install_dir=BUILTIN_PROVIDER_INSTALL_DIR,
                ),
                **self.providers,
            }
            return ProviderRegistry(providers=merged)
        return self


class SourceEntry(BaseModel):
    path: str = ""


class SourceRegistry(_Saveable):
    sources: dict[str, SourceEntry] = {}


class SkillEntry(BaseModel):
    source: str = ""
    commit: str | None = None
    files: dict[str, str] = {}


class SkillManifest(_Saveable):
    skills: dict[str, SkillEntry] = {}


def list_source_skills(source_path: Path) -> list[str]:
    cfg = SourceConfig.load(source_path / REPO_SKILLS_DIR / SOURCE_CONFIG_FILE)
    skills_dir = source_path / cfg.skills_dir
    if not skills_dir.is_dir():
        return []
    result: list[str] = []
    for dirpath, _, filenames in os.walk(skills_dir):
        if "SKILL.md" in filenames:
            result.append(Path(dirpath).name)
    return sorted(result)


def load_source_config(repo_root: Path) -> SourceConfig:
    return SourceConfig.load(repo_root / REPO_SKILLS_DIR / SOURCE_CONFIG_FILE)


def load_source_registry() -> SourceRegistry:
    return SourceRegistry.load(default_config_dir() / SOURCES_REGISTRY_FILE)


def save_source_registry(registry: SourceRegistry) -> None:
    registry.save(default_config_dir() / SOURCES_REGISTRY_FILE)


def load_provider_registry(*, with_builtins: bool = True) -> ProviderRegistry:
    registry = ProviderRegistry.load(default_config_dir() / PROVIDERS_REGISTRY_FILE)
    if with_builtins:
        return registry.with_builtins()
    return registry


def save_provider_registry(registry: ProviderRegistry) -> None:
    registry.save(default_config_dir() / PROVIDERS_REGISTRY_FILE)


def load_skill_manifest() -> SkillManifest:
    return SkillManifest.load(default_config_dir() / SKILL_MANIFEST_FILE)


def save_skill_manifest(manifest: SkillManifest) -> None:
    manifest.save(default_config_dir() / SKILL_MANIFEST_FILE)
