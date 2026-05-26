from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from repo_skills.config import default_config_path
from repo_skills.utils import load_config, save_config

SKILL_MANIFEST_FILE = "skill-manifest.json"


class ManifestSkill(BaseModel):
    source: str = ""
    files: dict[str, str] = {}
    commit: str | None = None


class SkillManifest(BaseModel):
    skills: dict[str, ManifestSkill] = {}

    @classmethod
    def load(cls, path: Path) -> "SkillManifest":
        result = load_config(cls, path)
        if result is None:
            return cls()
        return result

    def save(self, path: Path) -> None:
        save_config(self, path)


def load_skill_manifest() -> SkillManifest:
    return SkillManifest.load(default_config_path(SKILL_MANIFEST_FILE))


def save_skill_manifest(manifest: SkillManifest) -> None:
    manifest.save(default_config_path(SKILL_MANIFEST_FILE))
