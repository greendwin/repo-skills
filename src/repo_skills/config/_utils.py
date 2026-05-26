import hashlib
import os
from pathlib import Path

from typing_extensions import TypeAlias


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
            rel = str(full.relative_to(skill_dir))
            sha = hashlib.sha256(full.read_bytes()).hexdigest()
            result[rel] = f"sha256:{sha}"

    return result
