from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from repo_skills.config import default_config_path
from repo_skills.errors import AppError
from repo_skills.utils import fmt_ident, load_config, save_config

SKILL_MANIFEST_FILE = "skill-manifest.json"
PROVIDERS_REGISTRY_FILE = "providers.json"

BUILTIN_PROVIDER_NAME = "claude"
BUILTIN_PROVIDER_INSTALL_DIR = "~/.claude/skills"


class ProviderConfig(BaseModel):
    name: str = ""
    install_dir: str = ""

    def resolve_path(self, *parts: str) -> Path:
        return Path(self.install_dir).expanduser().joinpath(*parts)


class ProviderRegistry(BaseModel):
    providers: dict[str, ProviderConfig] = {}

    @classmethod
    def load(cls, path: Path) -> "ProviderRegistry":
        result = load_config(cls, path)
        if result is None:
            return cls()
        return result

    def save(self, path: Path) -> None:
        save_config(self, path)

    def require(self, name: str) -> ProviderConfig:
        if name not in self.providers:
            raise AppError(f"Provider {fmt_ident(name)} not found.")

        return self.providers[name]

    def with_builtins(self) -> ProviderRegistry:
        if BUILTIN_PROVIDER_NAME in self.providers:
            return self

        merged = {
            BUILTIN_PROVIDER_NAME: ProviderConfig(
                name=BUILTIN_PROVIDER_NAME,
                install_dir=BUILTIN_PROVIDER_INSTALL_DIR,
            ),
            **self.providers,
        }
        return ProviderRegistry(providers=merged)


class ManifestSkill(BaseModel):
    source: str = ""
    files: dict[str, str] = {}
    commit: str | None = None


class SkillManifest(BaseModel):
    skills: dict[str, ManifestSkill] = {}

    @classmethod
    def load(cls, path: Path) -> "SkillManifest":
        result = load_config(cls, path)
        if result is None:
            return cls()
        return result

    def save(self, path: Path) -> None:
        save_config(self, path)


def load_provider_registry(*, with_builtins: bool = True) -> ProviderRegistry:
    registry = ProviderRegistry.load(default_config_path(PROVIDERS_REGISTRY_FILE))

    if with_builtins:
        return registry.with_builtins()
    return registry


def save_provider_registry(registry: ProviderRegistry) -> None:
    registry.save(default_config_path(PROVIDERS_REGISTRY_FILE))


def load_skill_manifest() -> SkillManifest:
    return SkillManifest.load(default_config_path(SKILL_MANIFEST_FILE))


def save_skill_manifest(manifest: SkillManifest) -> None:
    manifest.save(default_config_path(SKILL_MANIFEST_FILE))
