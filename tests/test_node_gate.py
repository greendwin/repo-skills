from __future__ import annotations

from tests._node_gate import (
    NodeGate,
    gate_from_environment,
    resolve_node_gate,
)


def test_node_present_runs_the_suite() -> None:
    assert resolve_node_gate(node_present=True, require_js_tests=False) is NodeGate.RUN


def test_node_present_runs_even_when_required() -> None:
    assert resolve_node_gate(node_present=True, require_js_tests=True) is NodeGate.RUN


def test_node_absent_skips_when_not_required() -> None:
    assert (
        resolve_node_gate(node_present=False, require_js_tests=False) is NodeGate.SKIP
    )


def test_node_absent_fails_loudly_when_required() -> None:
    # A node-less environment that opted into the JS suite must FAIL, never skip:
    # a silent skip would let the change's only coverage evaporate behind a green
    # tox run.
    assert resolve_node_gate(node_present=False, require_js_tests=True) is NodeGate.FAIL


def test_environment_demanding_js_tests_without_node_fails() -> None:
    gate = gate_from_environment(
        which=lambda _name: None,
        environ={"REQUIRE_WORKFLOW_JS_TESTS": "1"},
    )
    assert gate is NodeGate.FAIL


def test_environment_skips_when_node_absent_and_unset() -> None:
    gate = gate_from_environment(which=lambda _name: None, environ={})
    assert gate is NodeGate.SKIP


def test_environment_runs_when_node_present() -> None:
    gate = gate_from_environment(
        which=lambda _name: "/usr/bin/node",
        environ={},
    )
    assert gate is NodeGate.RUN


def test_require_flag_treats_falsey_strings_as_unset() -> None:
    for falsey in ("", "0", "false", "no", "off", "  "):
        gate = gate_from_environment(
            which=lambda _name: None,
            environ={"REQUIRE_WORKFLOW_JS_TESTS": falsey},
        )
        assert gate is NodeGate.SKIP, falsey
