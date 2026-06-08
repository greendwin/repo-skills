from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from repo_skills.utils import save_config

from ._utils import (
    ConfigState,
    RelPathHashes,
    VersionedConfig,
    compute_file_hashes,
    default_config_path,
    load_versioned_config,
)

SKILL_MANIFEST_FILE = "skill-manifest.json"

CURRENT_VERSION = 1


class _InstalledSkillDesc(BaseModel):
    source: str = ""
    files: dict[str, str] = {}
    commit: str | None = None
    detached: bool = False


class _SkillManifestConfig(VersionedConfig):
    skills: dict[str, _InstalledSkillDesc] = {}


@dataclass
class Baseline:
    commit: str
    files: dict[str, str] = field(default_factory=dict)


def make_baseline(commit: str, skill_path: Path) -> Baseline:
    return Baseline(commit=commit, files=compute_file_hashes(skill_path))


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
    result = load_versioned_config(_SkillManifestConfig, path, CURRENT_VERSION)

    # missing / broken / outdated manifests start empty
    if result.state is not ConfigState.OK:
        return SkillManifest()

    manifest = SkillManifest()
    for name, entry in result.cfg.skills.items():
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
