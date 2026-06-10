import hashlib
import os
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel
from typing_extensions import TypeAlias

from repo_skills.console import console
from repo_skills.errors import AppError, ConfigBrokenError
from repo_skills.utils import load_config, normalize_line_endings, rel_posix


class VersionedConfig(BaseModel):
    version: int = 0


_C = TypeVar("_C", bound=VersionedConfig)


class ConfigState(Enum):
    # version matches; `cfg` is ready to use as-is
    OK = auto()
    # no config file on disk
    MISSING = auto()
    # config file could not be parsed (a warning was already printed)
    BROKEN = auto()
    # version is older than supported; `cfg` holds the old data to migrate
    OUTDATED = auto()


@dataclass
class LoadedConfig(Generic[_C]):
    state: ConfigState
    # always populated: the loaded config, or a fresh default when there was
    # nothing valid to load (MISSING / BROKEN), so callers never null-check
    cfg: _C


def load_versioned_config(
    model: type[_C], path: Path, current_version: int
) -> LoadedConfig[_C]:
    try:
        cfg = load_config(model, path)
    except ConfigBrokenError:
        console.debug_traceback()

        console.print(f"[yellow]Warning[/yellow]: broken config file: {path}")
        return LoadedConfig(ConfigState.BROKEN, model())

    if cfg is None:
        return LoadedConfig(ConfigState.MISSING, model())

    if cfg.version > current_version:
        raise AppError(
            "Config was written by a newer version of the tool",
            hint="Update the tool to the latest version.",
            props={
                "path": str(path),
                "found": str(cfg.version),
                "supported": str(current_version),
            },
        )

    if cfg.version < current_version:
        return LoadedConfig(ConfigState.OUTDATED, cfg)

    return LoadedConfig(ConfigState.OK, cfg)


def default_config_path(*parts: str) -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"

    return base.joinpath("repo-skills", *parts)


RelPathHashes: TypeAlias = dict[str, str]


def compute_file_hashes(skill_dir: Path) -> RelPathHashes:
    result: RelPathHashes = {}
    for dirpath, _, filenames in os.walk(skill_dir):
        for fname in sorted(filenames):
            full = Path(dirpath) / fname
            rel = rel_posix(full, skill_dir)
            raw = normalize_line_endings(full.read_bytes())
            sha = hashlib.sha256(raw).hexdigest()
            result[rel] = f"sha256:{sha}"

    return result
