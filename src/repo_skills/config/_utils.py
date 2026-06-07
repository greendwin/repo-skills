import hashlib
import os
from pathlib import Path

from typing_extensions import TypeAlias

from repo_skills.utils import normalize_line_endings, rel_posix


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
