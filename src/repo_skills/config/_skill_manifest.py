from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel

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
    cfg = load_config(_SkillManifestConfig, path)
    if cfg is None:
        cfg = _SkillManifestConfig()

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
        cfg.skills[name] = _InstalledSkillDesc(
            source=skill.source,
            commit=skill.baseline.commit if skill.baseline else None,
            files=dict(skill.baseline.files) if skill.baseline else {},
            detached=skill.detached,
        )
    save_config(cfg, default_config_path(SKILL_MANIFEST_FILE))
