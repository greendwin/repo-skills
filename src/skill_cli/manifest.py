from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


def default_install_dir() -> Path:
    return Path.home() / ".claude" / "skills"


def default_manifest_path() -> Path:
    return default_install_dir() / ".skill-install.json"


class SkillEntry(BaseModel):
    commit: str = ""


class Manifest(BaseModel):
    repo_path: str | None = None
    skills: dict[str, SkillEntry] = {}

    @classmethod
    def load(cls, path: Path) -> Manifest:
        if not path.exists():
            return cls()

        data = path.read_text()
        return cls.model_validate_json(data)
