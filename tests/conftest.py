from __future__ import annotations

import pytest

from repo_skills.console import console


@pytest.fixture(autouse=True)
def _no_color() -> None:
    console.no_color = True
