from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from repo_skills.console import console, fmt_ident
from repo_skills.errors import AppError, ConfigBrokenError
from repo_skills.utils import load_config, save_config

from ._source import Source, load_source
from ._utils import default_config_path

SOURCES_REGISTRY_FILE = "sources.json"


class _SourceEntryDesc(BaseModel):
    path: str = ""


class _SourceRegistryConfig(BaseModel):
    sources: dict[str, _SourceEntryDesc] = {}


@dataclass
class SourceEntry:
    repo_root: Path
    source: Source | None = None


class SourceRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, SourceEntry] = {}

    @property
    def sources(self) -> Mapping[str, SourceEntry]:
        return self._entries

    def get_source(self, name: str, *, load_skills: bool) -> Source:
        entry = self._entries.get(name)
        if entry is None:
            raise AppError(f"Source {fmt_ident(name)} not found.")

        if entry.source is not None:
            return entry.source

        if not load_skills:
            # don't cache source without loaded skills
            return load_source(entry.repo_root, load_skills=False)

        entry.source = load_source(entry.repo_root, load_skills=True)
        return entry.source

    def register_source(self, name: str, repo_root: Path) -> None:
        self._entries[name] = SourceEntry(repo_root)

    def unregister_source(self, name: str) -> None:
        self._entries.pop(name, None)


def load_source_registry() -> SourceRegistry:

    path = default_config_path(SOURCES_REGISTRY_FILE)
    try:
        cfg = load_config(_SourceRegistryConfig, path)
    except ConfigBrokenError:
        console.debug_traceback()

        console.print(f"[yellow]Warning[/yellow]: broken config file: {path}")
        return SourceRegistry()

    if cfg is None:
        return SourceRegistry()

    reg = SourceRegistry()
    for name, p in cfg.sources.items():
        reg.register_source(name, Path(p.path))

    return reg


def save_source_registry(reg: SourceRegistry) -> None:
    cfg = _SourceRegistryConfig()
    for name, entry in reg.sources.items():
        cfg.sources[name] = _SourceEntryDesc(path=str(entry.repo_root))

    save_config(cfg, default_config_path(SOURCES_REGISTRY_FILE))
