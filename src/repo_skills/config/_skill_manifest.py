from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel

from repo_skills.utils import load_config, save_config

from ._utils import default_config_path

SKILL_MANIFEST_FILE = "skill-manifest.json"


class _InstalledSkillDesc(BaseModel):
    source: str = ""
    files: dict[str, str] = {}
    commit: str | None = None
    detached: bool = False


class _SkillManifestConfig(BaseModel):
    skills: dict[str, _InstalledSkillDesc] = {}


@dataclass
class InstalledSkill:
    source: str
    commit: str | None
    files: dict[str, str] = field(default_factory=dict)
    detached: bool = False


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
        source: str = "",
        commit: str | None = None,
        files: dict[str, str] | None = None,
        detached: bool = False,
    ) -> None:
        self._entries[name] = InstalledSkill(
            source=source,
            commit=commit,
            files=files if files is not None else {},
            detached=detached,
        )

    def unregister_skill(self, name: str) -> None:
        self._entries.pop(name, None)


def load_skill_manifest() -> SkillManifest:
    path = default_config_path(SKILL_MANIFEST_FILE)
    cfg = load_config(_SkillManifestConfig, path)
    if cfg is None:
        cfg = _SkillManifestConfig()

    manifest = SkillManifest()
    for name, entry in cfg.skills.items():
        manifest.register_skill(
            name,
            source=entry.source,
            commit=entry.commit,
            files=dict(entry.files),
            detached=entry.detached,
        )
    return manifest


def save_skill_manifest(manifest: SkillManifest) -> None:
    cfg = _SkillManifestConfig()
    for name, skill in manifest.skills.items():
        cfg.skills[name] = _InstalledSkillDesc(
            source=skill.source,
            commit=skill.commit,
            files=dict(skill.files),
            detached=skill.detached,
        )
    save_config(cfg, default_config_path(SKILL_MANIFEST_FILE))
