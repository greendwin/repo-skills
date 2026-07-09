from __future__ import annotations

import pytest

from repo_skills.console import reporter


@pytest.fixture(autouse=True)
def _no_color() -> None:
    reporter.no_color = True
