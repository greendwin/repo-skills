from __future__ import annotations

import configparser
from pathlib import Path

from tests._node_gate import REQUIRE_ENV, NodeGate, gate_from_environment

TOX_INI = Path(__file__).resolve().parent.parent / "tox.ini"


def _testenv_environment() -> dict[str, str]:
    """The setenv values that apply to the default ``test`` environment.

    tox merges ``[testenv]`` defaults with any ``[testenv:test]`` overrides;
    this collapses both into the effective setenv mapping for that env.
    """

    parser = configparser.ConfigParser()
    parser.read(TOX_INI)
    setenv: dict[str, str] = {}
    for section in ("testenv", "testenv:test"):
        if not parser.has_option(section, "setenv"):
            continue
        for line in parser.get(section, "setenv").splitlines():
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, _, value = line.partition("=")
            setenv[key.strip()] = value.strip()
    return setenv


def test_tox_demands_the_workflow_js_suite() -> None:
    # The loud-fail node gate only protects the JS behavior if tox actually
    # opts in: without this, a node-less run silently skips and a coverage
    # blind spot is mistaken for a pass.
    setenv = _testenv_environment()
    assert REQUIRE_ENV in setenv, (
        f"tox.ini must set {REQUIRE_ENV} for the test env so a node-less run "
        "fails loudly instead of silently skipping the workflow JS suite"
    )
    # Confirm the configured value reads as an opt-in through the same public
    # gate the suite uses: with node absent, an opted-in env must FAIL loudly
    # (not silently SKIP), which is exactly the truthy-parsing contract.
    gate = gate_from_environment(
        which=lambda _name: None,
        environ={REQUIRE_ENV: setenv[REQUIRE_ENV]},
    )
    assert gate is NodeGate.FAIL
