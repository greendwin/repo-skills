import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from repo_skills.errors import ConfigBrokenError

_T = TypeVar("_T", bound=BaseModel)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def to_posix_path(path: str) -> str:
    return path.replace("\\", "/")


def rel_posix(path: Path, base: Path) -> str:
    return to_posix_path(str(path.relative_to(base)))


def normalize_line_endings(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def hash_content(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(normalize_line_endings(data)).hexdigest()}"


def load_config(cls: type[_T], path: Path) -> _T | None:
    if not os.path.exists(path):
        return None

    try:
        return cls.model_validate_json(read_text(path))
    except (ValidationError, json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise ConfigBrokenError(path) from ex


def load_raw_config(path: Path) -> dict[str, Any] | None:
    if not os.path.exists(path):
        return None

    try:
        raw = json.loads(read_text(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as ex:
        raise ConfigBrokenError(path) from ex

    if not isinstance(raw, dict):
        raise ConfigBrokenError(path)

    return raw


def save_config(cfg: BaseModel, path: Path) -> None:
    write_text(path, cfg.model_dump_json(indent=2))


def overwrite_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
