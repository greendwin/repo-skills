import json
import os
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from repo_skills.errors import ConfigBrokenError

_T = TypeVar("_T", bound=BaseModel)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_config(cls: type[_T], path: Path) -> _T | None:
    if not os.path.exists(path):
        return None

    try:
        return cls.model_validate_json(read_text(path))
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise ConfigBrokenError(path) from ex


def save_config(cfg: BaseModel, path: Path) -> None:
    write_text(path, cfg.model_dump_json(indent=2))
