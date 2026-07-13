from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, Optional

import typer
from cli_error import CliError, escape

from repo_skills.config import (
    SkillManifest,
    Source,
    SourceRegistry,
    SourceSkill,
    load_provider_registry,
    load_skill_manifest,
    load_source_registry,
    make_baseline,
    save_skill_manifest,
)
from repo_skills.console import reporter
from repo_skills.git import resolve_verified_commit
from repo_skills.utils import overwrite_dir

from ._app import app
from ._deps import prepare_source_repo


@app.command(help="Install a skill from a source.")
def install(
    *,
    names: Annotated[
        list[str],
        typer.Argument(help="Skill name(s) to install."),
    ],
    source: Annotated[
        Optional[str],
        typer.Option("--source", "-s", help="Source name (required when multiple)."),
    ] = None,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Skip git pull."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing skill."),
    ] = False,
) -> None:
    manifest = load_skill_manifest()
    source_registry = load_source_registry()

    pulled_sources: set[str] = set()
    for name in names:
        _install_one(
            manifest,
            source_registry,
            name,
            from_source=source,
            offline=offline,
            force=force,
            pulled_sources=pulled_sources,
        )


@app.command(help="Uninstall a skill.")
def uninstall(
    *,
    names: Annotated[
        list[str],
        typer.Argument(help="Skill name(s) to uninstall."),
    ],
) -> None:
    manifest = load_skill_manifest()
    provider_registry = load_provider_registry()

    for name in names:
        if name not in manifest.skills:
            raise CliError("Skill [id]{name}[/id] is not installed.", name=name)

        for provider in provider_registry.providers:
            dst = provider.install_path / name
            if dst.exists():
                shutil.rmtree(dst)

        manifest.unregister_skill(name)
        save_skill_manifest(manifest)

        reporter.print("Uninstalled [id]{name}[/id].", name=name)


def _install_one(
    manifest: SkillManifest,
    source_registry: SourceRegistry,
    skill_name: str,
    *,
    from_source: str | None,
    offline: bool,
    force: bool,
    pulled_sources: set[str],
) -> None:
    source = _resolve_source(source_registry, from_source, skill_name=skill_name)

    repo = prepare_source_repo(
        source,
        pull=not offline and source.name not in pulled_sources,
    )
    pulled_sources.add(source.name)

    skill = source.skills.get(skill_name)
    if skill is None:
        raise CliError(
            "Skill [id]{skill}[/id] not found in source [id]{source}[/id].",
            skill=skill_name,
            source=source.name,
        )

    src = source.repo_root / skill.rel_path
    commit = resolve_verified_commit(repo, skill.rel_path)

    provider_registry = load_provider_registry()

    for provider in provider_registry.providers:
        _copy_skill(
            src,
            skill_name,
            install_dir=provider.install_path,
            provider_name=provider.name,
            force=force,
        )

    _record_manifest(manifest, source, skill, commit)

    reporter.print(
        "Installed [id]{skill}[/id] from [data]{source}[/data].",
        skill=skill_name,
        source=source.name,
    )


def _resolve_source(
    source_registry: SourceRegistry, source_name: str | None, *, skill_name: str
) -> Source:
    if not source_registry.sources:
        raise CliError("No sources registered.").hint(
            "Run [cmd]skills init[/cmd] first."
        )

    if source_name is not None:
        if source_name not in source_registry.sources:
            raise CliError("Source [id]{source}[/id] not found.", source=source_name)

        return source_registry.load_source(source_name)

    if len(source_registry.sources) == 1:
        only = next(iter(source_registry.sources))
        return source_registry.load_source(only)

    matches: list[Source] = []
    for sn in source_registry.sources:
        candidate = source_registry.load_source(sn)
        if skill_name in candidate.skills:
            matches.append(candidate)

    if len(matches) == 1:
        return matches[0]

    # TODO: TBD: can we simplify this?
    # (note that we must inline formatting in `CliError`)
    names = ", ".join(
        f"[id]{escape(name)}[/id]" for name in sorted(source_registry.sources.keys())
    )
    raise CliError(f"Multiple sources registered ({names}).").hint(
        "Use [cmd]--source[/cmd] to specify."
    )


def _record_manifest(
    manifest: SkillManifest, source: Source, skill: SourceSkill, commit: str
) -> None:
    manifest.register_skill(
        skill.name,
        source_name=source.name,
        baseline=make_baseline(commit, source.repo_root / skill.rel_path),
    )
    save_skill_manifest(manifest)


def _copy_skill(
    src: Path,
    name: str,
    *,
    install_dir: Path,
    provider_name: str,
    force: bool,
) -> None:
    dst = install_dir / name

    if dst.exists() and not force:
        raise CliError(
            "Skill [id]{name}[/id] already exists at provider [id]{provider}[/id].",
            name=name,
            provider=provider_name,
        ).hint("Use [cmd]--force[/cmd] to overwrite.")

    overwrite_dir(src, dst)
