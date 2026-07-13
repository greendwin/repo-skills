from __future__ import annotations

from dataclasses import dataclass

from cli_error import CliError

from repo_skills.config import (
    Provider,
    ProviderRegistry,
    Source,
    SourceRegistry,
    SourceSkill,
)


@dataclass
class UntrackedSkill:
    provider: Provider
    source: Source
    skill: SourceSkill


def find_skill_in_provider(
    provider_registry: ProviderRegistry, *, provider: Provider | None, skill_name: str
) -> Provider:
    if provider:
        skill_path = provider.install_path / skill_name
        if not skill_path.is_dir():
            raise CliError(
                "Skill [id]{skill}[/id] is not installed in [id]{provider}[/id].",
                skill=skill_name,
                provider=provider.name,
            )

        return provider

    matches = []
    for prov in provider_registry.providers:
        skill_path = prov.install_path / skill_name
        if skill_path.is_dir():
            matches.append(prov)

    if len(matches) > 1:
        # BUG: comma should not be included to [id]
        names = ", ".join(p.name for p in sorted(matches, key=lambda x: x.name))
        raise CliError(
            "Multiple providers have [id]{skill}[/id] ([id]{names}[/id]).",
            skill=skill_name,
            names=names,
        ).hint("Use [cmd]--from[/cmd] to specify.")

    if not matches:
        raise CliError("Skill [id]{skill}[/id] is not installed.", skill=skill_name)

    return matches[0]


def resolve_untracked(
    provider_registry: ProviderRegistry,
    source_registry: SourceRegistry,
    *,
    provider: Provider | None,
    skill_name: str,
    source: Source | None = None,
) -> UntrackedSkill | None:
    provider = find_skill_in_provider(
        provider_registry, provider=provider, skill_name=skill_name
    )

    if source is not None:
        skill = source.skills.get(skill_name)
        if skill is None:
            return None

        return UntrackedSkill(provider, source, skill)

    matches: list[tuple[Source, SourceSkill]] = []
    for source_name in source_registry.sources:
        source = source_registry.load_source(source_name)
        skill = source.skills.get(skill_name)
        if skill is not None:
            matches.append((source, skill))

    if len(matches) > 1:
        names = ", ".join(s.name for s, _ in sorted(matches, key=lambda x: x[0].name))
        raise CliError(
            "Multiple sources have [id]{skill}[/id] ([id]{names}[/id]).",
            skill=skill_name,
            names=names,
        ).hint("Use [cmd]--source[/cmd] to specify.")

    if not matches:
        return None

    source, skill = matches[0]
    return UntrackedSkill(provider, source, skill)


def resolve_orphan_source(source_registry: SourceRegistry) -> Source:
    if not source_registry.sources:
        raise CliError("No sources registered.")

    if len(source_registry.sources) > 1:
        names = ", ".join(sorted(source_registry.sources.keys()))
        raise CliError(
            "Multiple sources registered ([id]{names}[/id]).", names=names
        ).hint("Use [cmd]--source[/cmd] to specify.")

    source_name = list(source_registry.sources)[0]
    return source_registry.get_source_no_skills(source_name)
