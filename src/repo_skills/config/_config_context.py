from __future__ import annotations

from dataclasses import dataclass

from ._provider_registry import ProviderRegistry, load_provider_registry
from ._skill_manifest import SkillManifest, load_skill_manifest
from ._source_registry import SourceRegistry, load_source_registry


@dataclass
class ConfigContext:
    provider_registry: ProviderRegistry
    source_registry: SourceRegistry
    manifest: SkillManifest


def load_config_context() -> ConfigContext:
    return ConfigContext(
        provider_registry=load_provider_registry(),
        source_registry=load_source_registry(),
        manifest=load_skill_manifest(),
    )
