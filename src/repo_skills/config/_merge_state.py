from __future__ import annotations

from repo_skills.utils import save_config

from ._utils import (
    ConfigState,
    VersionedConfig,
    default_config_path,
    load_versioned_config,
)

MERGE_STATE_FILE = "merge-state.json"

CURRENT_VERSION = 1


class _MergeStateConfig(VersionedConfig):
    # merge-branch names whose deferred --continue must NOT retarget tracking
    # (--keep-source). Keyed by the full `skill-merge/<provider>/<skill>` branch
    # so intent is scoped to the exact in-progress merge: it self-invalidates
    # when the branch is gone and never leaks to another provider/skill. The
    # cross-source check in `_finalize` is the second guard.
    keep_source: list[str] = []


def load_keep_source() -> set[str]:
    path = default_config_path(MERGE_STATE_FILE)
    result = load_versioned_config(_MergeStateConfig, path, CURRENT_VERSION)
    if result.state is not ConfigState.OK:
        return set()
    return set(result.cfg.keep_source)


def mark_keep_source(branch: str) -> None:
    branches = load_keep_source()
    branches.add(branch)
    _save(branches)


def clear_keep_source(branch: str) -> None:
    branches = load_keep_source()
    if branch not in branches:
        return
    branches.discard(branch)
    _save(branches)


def _save(branches: set[str]) -> None:
    cfg = _MergeStateConfig(version=CURRENT_VERSION, keep_source=sorted(branches))
    save_config(cfg, default_config_path(MERGE_STATE_FILE))
