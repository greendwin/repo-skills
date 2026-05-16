from __future__ import annotations

import os
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
        if not os.path.exists(path):
            return cls()

        with open(path) as f:
            data = f.read()
        return cls.model_validate_json(data)

    def save(self, path: Path) -> None:
        os.makedirs(str(path.parent), exist_ok=True)
        with open(str(path), "w") as f:
            f.write(self.model_dump_json(indent=2) + "\n")
