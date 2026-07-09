import os
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Generic, TypeVar

from cli_error import CliError
from pydantic import BaseModel, ValidationError
from typing_extensions import TypeAlias

from repo_skills.console import reporter
from repo_skills.utils import (
    ConfigBrokenError,
    hash_content,
    load_raw_config,
    rel_posix,
    save_config,
)


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
    model: type[_C],
    path: Path,
    current_version: int,
    *,
    migrate: Callable[[dict[str, Any]], _C] | None = None,
) -> LoadedConfig[_C]:
    try:
        raw = load_raw_config(path)
    except ConfigBrokenError:
        report_broken_config(path)
        return LoadedConfig(ConfigState.BROKEN, model())

    if raw is None:
        return LoadedConfig(ConfigState.MISSING, model())

    version = raw.get("version", 0)
    if version > current_version:
        raise (
            CliError("Config was written by a newer version of the tool")
            .prop_path("path", str(path))
            .prop_data("found", str(version))
            .prop_data("supported", str(current_version))
            .hint("Update the tool to the latest version.")
        )

    if version < current_version and migrate is not None:
        migrated = migrate(raw)
        migrated.version = current_version
        save_config(migrated, path)
        return LoadedConfig(ConfigState.OK, migrated)

    try:
        cfg = model.model_validate(raw)
    except ValidationError:
        report_broken_config(path)
        return LoadedConfig(ConfigState.BROKEN, model())

    if version < current_version:
        return LoadedConfig(ConfigState.OUTDATED, cfg)

    return LoadedConfig(ConfigState.OK, cfg)


def report_broken_config(path: Path) -> None:
    reporter.debug_traceback()
    reporter.print("[warn]Warning[/warn]: broken config file: {path}", path=path)


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
            result[rel] = hash_content(full.read_bytes())

    return result
