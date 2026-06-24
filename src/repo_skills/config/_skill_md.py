import os
from collections.abc import Iterator
from pathlib import Path

from repo_skills.utils import read_text

SKILL_FILE = "SKILL.md"


def iter_skill_dirs(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if SKILL_FILE in filenames:
            # outermost SKILL.md wins; don't descend into a skill's internals
            dirnames.clear()
            yield Path(dirpath)


def read_skill_description(skill_dir: Path) -> str | None:
    skill_file = skill_dir / SKILL_FILE
    if not skill_file.is_file():
        return None

    lines = read_text(skill_file).splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("description:"):
            value = line[len("description:") :].strip()
            return _normalize_description(value)

    return None


def _normalize_description(value: str) -> str | None:
    # A block-scalar header (`|`/`>`, optionally with modifiers) moves the value
    # onto following lines, so there is no inline description to read here.
    if value[:1] in ("|", ">"):
        return None

    # Surrounding quotes are YAML syntax, not part of the description value.
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]

    return value or None
