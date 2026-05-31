from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel

from repo_skills.console import console
from repo_skills.errors import ConfigBrokenError
from repo_skills.utils import load_config, save_config

from ._utils import RelPathHashes, default_config_path

SKILL_MANIFEST_FILE = "skill-manifest.json"

CURRENT_VERSION = 1


class _InstalledSkillDesc(BaseModel):
    source: str = ""
    files: dict[str, str] = {}
    commit: str | None = None
    detached: bool = False


class _SkillManifestConfig(BaseModel):
    version: int = 0
    skills: dict[str, _InstalledSkillDesc] = {}


@dataclass
class Baseline:
    commit: str
    files: dict[str, str] = field(default_factory=dict)


@dataclass
class InstalledSkill:
    source: str
    baseline: Baseline | None = None
    detached: bool = False

    def match_files(self, files: RelPathHashes) -> bool:
        return self.baseline is not None and self.baseline.files == files


class SkillManifest:
    def __init__(self) -> None:
        self._entries: dict[str, InstalledSkill] = {}

    @property
    def skills(self) -> Mapping[str, InstalledSkill]:
        return self._entries

    def register_skill(
        self,
        name: str,
        *,
        source_name: str = "",
        baseline: Baseline | None = None,
        detached: bool = False,
    ) -> InstalledSkill:
        entry = InstalledSkill(
            source=source_name,
            baseline=baseline,
            detached=detached,
        )
        self._entries[name] = entry
        return entry

    def unregister_skill(self, name: str) -> None:
        self._entries.pop(name, None)


def load_skill_manifest() -> SkillManifest:
    path = default_config_path(SKILL_MANIFEST_FILE)
    try:
        cfg = load_config(_SkillManifestConfig, path)
    except ConfigBrokenError:
        if console.debug:
            console.print_exception()

        console.print(f"[yellow]Warning[/yellow]: broken config file: {path}")
        return SkillManifest()

    if cfg is None:
        return SkillManifest()

    # TODO: config version can be *higher* then current,
    #       we should stop then and ask to update
    if cfg.version != CURRENT_VERSION:
        return SkillManifest()

    manifest = SkillManifest()
    for name, entry in cfg.skills.items():
        baseline: Baseline | None = None
        if entry.commit is not None:
            baseline = Baseline(commit=entry.commit, files=dict(entry.files))

        manifest.register_skill(
            name,
            source_name=entry.source,
            baseline=baseline,
            detached=entry.detached,
        )
    return manifest


def save_skill_manifest(manifest: SkillManifest) -> None:
    cfg = _SkillManifestConfig(version=CURRENT_VERSION)
    for name, skill in manifest.skills.items():
        desc = _InstalledSkillDesc(
            source=skill.source,
            detached=skill.detached,
        )
        if skill.baseline:
            desc.commit = skill.baseline.commit
            desc.files.update(skill.baseline.files)

        cfg.skills[name] = desc

    save_config(cfg, default_config_path(SKILL_MANIFEST_FILE))
