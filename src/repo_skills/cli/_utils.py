from __future__ import annotations

from dataclasses import dataclass

from repo_skills.config import (
    Provider,
    ProviderRegistry,
    SkillManifest,
    Source,
    SourceRegistry,
    SourceSkill,
    compute_file_hashes,
)
from repo_skills.console import fmt_command, fmt_ident
from repo_skills.errors import AppError


@dataclass
class UntrackedSkill:
    provider: Provider
    source: Source
    skill: SourceSkill


def find_skill_in_provider(
    provider_registry: ProviderRegistry, provider: Provider | None, skill_name: str
) -> Provider:
    if provider:
        skill_path = provider.install_path / skill_name
        if not skill_path.is_dir():
            raise AppError(
                f"Skill {fmt_ident(skill_name)} is not installed "
                f"in {fmt_ident(provider.name)}."
            )

        return provider

    matches = []
    for prov in provider_registry.providers:
        skill_path = prov.install_path / skill_name
        if skill_path.is_dir():
            matches.append(prov)

    if len(matches) > 1:
        names = ", ".join(
            fmt_ident(p.name) for p in sorted(matches, key=lambda x: x.name)
        )
        raise AppError(
            f"Multiple providers have {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--from')} to specify.",
        )

    if not matches:
        raise AppError(f"Skill {fmt_ident(skill_name)} is not installed.")

    return matches[0]


def resolve_untracked(
    provider_registry: ProviderRegistry,
    source_registry: SourceRegistry,
    *,
    provider: Provider | None,
    skill_name: str,
    source: Source | None = None,
) -> UntrackedSkill | None:
    provider = find_skill_in_provider(provider_registry, provider, skill_name)

    if source is not None:
        skill = source.skills.get(skill_name)
        if skill is None:
            return None
        return UntrackedSkill(provider, source, skill)

    matches: list[tuple[Source, SourceSkill]] = []
    for source_name in source_registry.sources:
        source = source_registry.get_source(source_name, load_skills=True)
        skill = source.skills.get(skill_name)
        if skill is not None:
            matches.append((source, skill))

    if len(matches) > 1:
        names = ", ".join(
            fmt_ident(s.name) for s, _ in sorted(matches, key=lambda x: x[0].name)
        )
        raise AppError(
            f"Multiple sources have {fmt_ident(skill_name)} ({names}).",
            hint=f"Use {fmt_command('--source')} to specify.",
        )

    if not matches:
        return None

    source, skill = matches[0]
    return UntrackedSkill(provider, source, skill)


def find_modified_skills(
    provider_registry: ProviderRegistry,
    manifest: SkillManifest,
    *,
    provider_name: str | None = None,
) -> list[str]:
    if provider_name is not None:
        providers = [provider_registry.require(provider_name)]
    else:
        providers = list(provider_registry.providers)

    modified: set[str] = set()
    for skill_name, entry in manifest.skills.items():
        if entry.baseline is None:
            continue

        for provider in providers:
            installed_path = provider.install_path / skill_name
            if not installed_path.is_dir():
                continue

            current_hashes = compute_file_hashes(installed_path)
            if current_hashes != entry.baseline.files:
                modified.add(skill_name)
                break

    return sorted(modified)


def require_single_modified(
    provider_registry: ProviderRegistry,
    manifest: SkillManifest,
    *,
    provider_name: str | None = None,
) -> str:
    modified = find_modified_skills(
        provider_registry, manifest, provider_name=provider_name
    )
    if len(modified) == 0:
        raise AppError("No modified skills found.")
    if len(modified) > 1:
        names = ", ".join(fmt_ident(s) for s in modified)
        raise AppError(
            f"Multiple skills are modified ({names}).",
            hint="Specify skill name.",
        )
    return modified[0]


def resolve_orphan_source(source_registry: SourceRegistry) -> Source:
    if not source_registry.sources:
        raise AppError("No sources registered.")

    if len(source_registry.sources) > 1:
        names = ", ".join(
            fmt_ident(name) for name in sorted(source_registry.sources.keys())
        )
        raise AppError(
            f"Multiple sources registered ({names}).",
            hint=f"Use {fmt_command('--source')} to specify.",
        )

    source_name = list(source_registry.sources)[0]
    return source_registry.get_source(source_name, load_skills=False)
