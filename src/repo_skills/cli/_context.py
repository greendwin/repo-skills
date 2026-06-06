from __future__ import annotations

from dataclasses import dataclass

from repo_skills.config import ProviderRegistry, SkillManifest, SourceRegistry


@dataclass
class CommandContext:
    provider_registry: ProviderRegistry
    source_registry: SourceRegistry
    manifest: SkillManifest
