from __future__ import annotations

from collections.abc import ValuesView
from dataclasses import dataclass
from pathlib import Path

from cli_error import CliError
from pydantic import BaseModel

from repo_skills.console import fmt_ident
from repo_skills.utils import save_config

from ._utils import (
    ConfigState,
    VersionedConfig,
    default_config_path,
    load_versioned_config,
)

PROVIDERS_REGISTRY_FILE = "providers.json"
CURRENT_VERSION = 1

_DEFAULT_PROVIDERS = {
    "claude": "~/.claude/skills",
}


class _ProviderEntryDesc(BaseModel):
    install_dir: str = ""


class _ProviderRegistryConfig(VersionedConfig):
    providers: dict[str, _ProviderEntryDesc] = {}


@dataclass
class Provider:
    name: str
    install_path: Path


class ProviderRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, Provider] = {}

    @property
    def providers(self) -> ValuesView[Provider]:
        return self._entries.values()

    def is_registered(self, name: str) -> bool:
        return name in self._entries

    def register(self, name: str, install_dir: str) -> Provider:
        provider = Provider(
            name=name,
            install_path=Path(install_dir).expanduser(),
        )
        self._entries[name] = provider
        return provider

    def unregister(self, name: str) -> None:
        self._entries.pop(name, None)

    def require(self, name: str) -> Provider:
        provider = self._entries.get(name)
        if provider is None:
            raise CliError(f"Provider {fmt_ident(name)} not found.")
        return provider


def _apply_defaults(cfg: _ProviderRegistryConfig) -> _ProviderRegistryConfig:
    for name, install_dir in _DEFAULT_PROVIDERS.items():
        if name not in cfg.providers:
            cfg.providers[name] = _ProviderEntryDesc(install_dir=install_dir)
    cfg.version = CURRENT_VERSION
    return cfg


def load_provider_registry() -> ProviderRegistry:
    path = default_config_path(PROVIDERS_REGISTRY_FILE)
    result = load_versioned_config(_ProviderRegistryConfig, path, CURRENT_VERSION)

    cfg = result.cfg
    if result.state is not ConfigState.OK:
        # missing / broken / outdated: inject defaults onto whatever we have
        cfg = _apply_defaults(cfg)
        # persist the result, but never overwrite a broken file the user may
        # still want to recover
        if result.state is not ConfigState.BROKEN:
            save_config(cfg, path)

    reg = ProviderRegistry()
    for name, entry in cfg.providers.items():
        reg.register(name, entry.install_dir)
    return reg


def save_provider_registry(reg: ProviderRegistry) -> None:
    cfg = _ProviderRegistryConfig(version=CURRENT_VERSION)
    for provider in reg.providers:
        cfg.providers[provider.name] = _ProviderEntryDesc(
            install_dir=str(provider.install_path)
        )

    save_config(cfg, default_config_path(PROVIDERS_REGISTRY_FILE))
