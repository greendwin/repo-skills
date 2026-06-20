import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from repo_skills.console import fmt_ident, fmt_path
from repo_skills.errors import AppError
from repo_skills.git import GitRepo
from repo_skills.utils import rel_posix, save_config

from ._skill_md import SKILL_FILE
from ._utils import (
    ConfigState,
    LoadedConfig,
    VersionedConfig,
    load_versioned_config,
)

REPO_SKILLS_DIR = ".repo-skills"
SOURCE_CONFIG_PATH = f"{REPO_SKILLS_DIR}/source.json"

CURRENT_VERSION = 1


class SourceBrokenError(AppError):
    def __init__(self, repo_root: Path) -> None:
        super().__init__(
            f"Source {fmt_ident(repo_root.name)} either broken or uninitialized.",
            props={"repo": fmt_path(repo_root)},
        )


class SourceConfig(VersionedConfig):
    name: str = ""
    skills_dirs: list[str] = []
    branch: str = ""

    @property
    def active_dir(self) -> str | None:
        return self.skills_dirs[0] if self.skills_dirs else None


@dataclass
class SourceSkill:
    name: str
    rel_path: str  # rel path against source root


@dataclass
class Source:
    repo_root: Path
    config: SourceConfig
    skills: dict[str, SourceSkill]

    @property
    def name(self) -> str:
        return self.config.name or self.repo_root.name

    def get_branch(self, git: GitRepo) -> str:
        return self.config.branch or git.get_main_branch()

    def get_skill(self, name: str) -> SourceSkill:
        skill = self.skills.get(name)
        if skill is None:
            raise AppError(
                f"Skill {fmt_ident(name)} does not exist "
                f"in source {fmt_ident(self.name)}",
                props={"repo": fmt_path(self.repo_root)},
            )

        return skill


def _migrate_source_v0(raw: dict[str, Any]) -> SourceConfig:
    # legacy files may carry a non-string `skills_dir` (e.g. a list or null);
    # treat any non-string as "no skills dir" so migration is graceful, not fatal
    legacy_dir = raw.get("skills_dir")
    if not isinstance(legacy_dir, str):
        legacy_dir = None
    cfg = SourceConfig.model_validate(raw)
    cfg.skills_dirs = [legacy_dir] if legacy_dir else []
    return cfg


def load_source_state(repo_root: Path) -> LoadedConfig[SourceConfig]:
    path = repo_root / SOURCE_CONFIG_PATH
    return load_versioned_config(
        SourceConfig, path, CURRENT_VERSION, migrate=_migrate_source_v0
    )


def load_source_config(repo_root: Path) -> SourceConfig | None:
    result = load_source_state(repo_root)
    return result.cfg if result.state is ConfigState.OK else None


def save_source_config(config: SourceConfig, repo_root: Path) -> None:
    config.version = CURRENT_VERSION
    save_config(config, repo_root / SOURCE_CONFIG_PATH)


def load_source(repo_root: Path, *, load_skills: bool) -> Source:
    result = load_source_state(repo_root)
    if result.state is not ConfigState.OK:
        raise SourceBrokenError(repo_root)

    config = result.cfg
    active_dir = config.active_dir
    if load_skills and active_dir is not None:
        skills = _collect_source_skills(repo_root, active_dir)
    else:
        skills = {}

    return Source(repo_root=repo_root, config=config, skills=skills)


def _collect_source_skills(repo_root: Path, skills_dir: str) -> dict[str, SourceSkill]:
    skills_root = repo_root / skills_dir
    if not skills_root.is_dir():
        return {}

    result: dict[str, SourceSkill] = {}
    for dirpath, _, filenames in os.walk(skills_root):
        if SKILL_FILE not in filenames:
            continue

        name = os.path.basename(dirpath)
        result[name] = SourceSkill(
            name=name,
            rel_path=rel_posix(Path(dirpath), repo_root),
        )

    return result
