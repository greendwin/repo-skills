from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from cli_error import CliError
from pydantic import BaseModel

from repo_skills.console import fmt_ident
from repo_skills.utils import ConfigBrokenError, load_config, save_config

from ._source import Source, load_source
from ._utils import default_config_path, report_broken_config

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

    def load_source(self, name: str) -> Source:
        entry = self._get_entry(name)
        if entry.source is not None:
            return entry.source

        entry.source = load_source(entry.repo_root, load_skills=True)
        return entry.source

    def get_source_no_skills(self, name: str) -> Source:
        entry = self._get_entry(name)
        if entry.source is not None:
            # already loaded
            return entry.source

        # don't cache source without loaded skills
        return load_source(entry.repo_root, load_skills=False)

    def _get_entry(self, name: str) -> SourceEntry:
        entry = self._entries.get(name)
        if entry is None:
            raise CliError(f"Source {fmt_ident(name)} not found.")

        return entry

    def register_source(self, name: str, repo_root: Path) -> None:
        self._entries[name] = SourceEntry(repo_root)

    def unregister_source(self, name: str) -> None:
        self._entries.pop(name, None)


def load_source_registry() -> SourceRegistry:

    path = default_config_path(SOURCES_REGISTRY_FILE)
    try:
        cfg = load_config(_SourceRegistryConfig, path)
    except ConfigBrokenError:
        report_broken_config(path)
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
