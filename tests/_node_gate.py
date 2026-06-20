from __future__ import annotations

import enum
import os
import shutil
from collections.abc import Callable, Mapping


class NodeGate(enum.Enum):
    """How a node-dependent test suite should react to the node runtime."""

    RUN = "run"
    SKIP = "skip"
    FAIL = "fail"


#: Environment variable an environment sets to demand the JS suite actually run.
#: When set to a truthy value, a missing node runtime is a hard failure rather
#: than a silent skip, so a coverage blind spot cannot be mistaken for a pass.
REQUIRE_ENV = "REQUIRE_WORKFLOW_JS_TESTS"

SKIP_REASON = "node runtime not available to run the workflow JS test suite"
FAIL_REASON = (
    f"{REQUIRE_ENV} is set but the node runtime is unavailable: the workflow JS "
    "test suite cannot run, so this environment would report green without "
    "exercising any of its behavior. Install node or unset the variable."
)


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() not in {"", "0", "false", "no", "off"}


def resolve_node_gate(
    *,
    node_present: bool,
    require_js_tests: bool,
) -> NodeGate:
    """Decide how a node-dependent suite reacts to its environment.

    When node is present the suite runs. When node is absent the suite is
    skipped *unless* the environment demanded the suite run, in which case the
    absence is surfaced as a hard failure instead of a silent skip.
    """

    if node_present:
        return NodeGate.RUN
    if require_js_tests:
        return NodeGate.FAIL
    return NodeGate.SKIP


def gate_from_environment(
    *,
    which: Callable[[str], str | None] = shutil.which,
    environ: Mapping[str, str] | None = None,
) -> NodeGate:
    """Resolve the node gate from the live runtime environment."""

    env = os.environ if environ is None else environ
    return resolve_node_gate(
        node_present=which("node") is not None,
        require_js_tests=_is_truthy(env.get(REQUIRE_ENV)),
    )
