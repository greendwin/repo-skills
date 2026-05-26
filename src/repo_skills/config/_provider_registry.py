from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from repo_skills.errors import AppError
from repo_skills.utils import fmt_ident, load_config, save_config

from ._utils import default_config_path

PROVIDERS_REGISTRY_FILE = "providers.json"
CURRENT_VERSION = 1

_DEFAULT_PROVIDERS = {
    "claude": "~/.claude/skills",
}


class _ProviderEntryDesc(BaseModel):
    install_dir: str = ""


class _ProviderRegistryConfig(BaseModel):
    version: int = 0
    providers: dict[str, _ProviderEntryDesc] = {}


@dataclass
class Provider:
    name: str
    install_path: Path


class ProviderRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, Provider] = {}

    @property
    def providers(self) -> Mapping[str, Provider]:
        return self._entries

    def register_provider(self, name: str, install_dir: str) -> None:
        self._entries[name] = Provider(
            name=name,
            install_path=Path(install_dir).expanduser(),
        )

    def unregister_provider(self, name: str) -> None:
        self._entries.pop(name, None)

    def require(self, name: str) -> Provider:
        provider = self._entries.get(name)
        if provider is None:
            raise AppError(f"Provider {fmt_ident(name)} not found.")
        return provider


def _apply_defaults(cfg: _ProviderRegistryConfig) -> _ProviderRegistryConfig:
    for name, install_dir in _DEFAULT_PROVIDERS.items():
        if name not in cfg.providers:
            cfg.providers[name] = _ProviderEntryDesc(install_dir=install_dir)
    cfg.version = CURRENT_VERSION
    return cfg


def load_provider_registry() -> ProviderRegistry:
    path = default_config_path(PROVIDERS_REGISTRY_FILE)
    cfg = load_config(_ProviderRegistryConfig, path)

    if cfg is None:
        cfg = _apply_defaults(_ProviderRegistryConfig())
        save_config(cfg, path)
    elif cfg.version < CURRENT_VERSION:
        cfg = _apply_defaults(cfg)
        save_config(cfg, path)

    reg = ProviderRegistry()
    for name, entry in cfg.providers.items():
        reg.register_provider(name, entry.install_dir)
    return reg


def save_provider_registry(reg: ProviderRegistry) -> None:
    cfg = _ProviderRegistryConfig(version=CURRENT_VERSION)
    for name, provider in reg.providers.items():
        cfg.providers[name] = _ProviderEntryDesc(install_dir=str(provider.install_path))

    save_config(cfg, default_config_path(PROVIDERS_REGISTRY_FILE))
