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
from repo_skills.console import fmt_command, fmt_ident


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
        raise CliError(
            f"Multiple providers have {fmt_ident(skill_name)} ({names})."
        ).hint(f"Use {fmt_command('--from')} to specify.")

    if not matches:
        raise CliError(f"Skill {fmt_ident(skill_name)} is not installed.")

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
        names = ", ".join(
            fmt_ident(s.name) for s, _ in sorted(matches, key=lambda x: x[0].name)
        )
        raise CliError(
            f"Multiple sources have {fmt_ident(skill_name)} ({names})."
        ).hint(f"Use {fmt_command('--source')} to specify.")

    if not matches:
        return None

    source, skill = matches[0]
    return UntrackedSkill(provider, source, skill)


def resolve_orphan_source(source_registry: SourceRegistry) -> Source:
    if not source_registry.sources:
        raise CliError("No sources registered.")

    if len(source_registry.sources) > 1:
        names = ", ".join(
            fmt_ident(name) for name in sorted(source_registry.sources.keys())
        )
        raise CliError(f"Multiple sources registered ({names}).").hint(
            f"Use {fmt_command('--source')} to specify."
        )

    source_name = list(source_registry.sources)[0]
    return source_registry.get_source_no_skills(source_name)
