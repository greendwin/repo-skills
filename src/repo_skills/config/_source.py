import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from repo_skills.console import fmt_ident, fmt_path
from repo_skills.errors import AppError
from repo_skills.git import GitRepo
from repo_skills.utils import load_config, rel_posix, save_config

from ._skill_md import SKILL_FILE

REPO_SKILLS_DIR = ".repo-skills"
SOURCE_CONFIG_PATH = f"{REPO_SKILLS_DIR}/source.json"


class SourceBrokenError(AppError):
    def __init__(self, repo_root: Path) -> None:
        super().__init__(
            f"Source {fmt_ident(repo_root.name)} either broken or uninitialized.",
            props={"repo": fmt_path(repo_root)},
        )


class SourceConfig(BaseModel):
    name: str
    skills_dir: str
    branch: str = ""


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


def load_source_config(repo_root: Path) -> SourceConfig | None:
    return load_config(SourceConfig, repo_root / SOURCE_CONFIG_PATH)


def save_source_config(config: SourceConfig, repo_root: Path) -> None:
    save_config(config, repo_root / SOURCE_CONFIG_PATH)


def load_source(repo_root: Path, *, load_skills: bool) -> Source:
    config = load_source_config(repo_root)
    if config is None:
        raise SourceBrokenError(repo_root)

    if load_skills:
        skills = _collect_source_skills(repo_root, config.skills_dir)
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
