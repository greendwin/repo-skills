from __future__ import annotations

import subprocess
import warnings
from pathlib import Path

import pytest

from tests._node_gate import (
    FAIL_REASON,
    SKIP_REASON,
    NodeGate,
    gate_from_environment,
)

WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "workflows"


def _as_text(stream: str | bytes | None) -> str:
    """Render a captured subprocess stream as text for a failure message."""

    if stream is None:
        return ""
    if isinstance(stream, bytes):
        return stream.decode(errors="replace")
    return stream


def _js_test_files() -> list[Path]:
    return sorted(WORKFLOWS_DIR.glob("*.test.mjs"))


def test_workflow_js_suite_passes() -> None:
    gate = gate_from_environment()
    if gate is NodeGate.FAIL:
        pytest.fail(FAIL_REASON)
    if gate is NodeGate.SKIP:
        # Surface the skip loudly so a node-less run is not mistaken for full
        # coverage: a bare green tox is a coverage blind spot here.
        warnings.warn(SKIP_REASON, stacklevel=2)
        pytest.skip(SKIP_REASON)

    test_files = _js_test_files()
    assert test_files, "expected at least one .test.mjs suite under .claude/workflows"

    try:
        result = subprocess.run(
            ["node", "--test", *[str(path) for path in test_files]],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as expired:
        # `text=True` makes the captured streams str, but `TimeoutExpired`
        # types them as `str | bytes | None`; render defensively so a timed-out
        # run reports readable output regardless of the captured type.
        stdout = _as_text(expired.stdout)
        stderr = _as_text(expired.stderr)
        pytest.fail(
            "workflow JS test suite timed out before completing:\n"
            f"stdout:\n{stdout}\n"
            f"stderr:\n{stderr}"
        )

    assert result.returncode == 0, (
        "workflow JS test suite failed:\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
