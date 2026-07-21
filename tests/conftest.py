from __future__ import annotations

import pathlib
import sys
from collections.abc import Callable, Generator
from types import FunctionType
from typing import Any

import pytest

from repo_skills.console import reporter


@pytest.fixture(autouse=True)
def _no_color() -> None:
    reporter.no_color = True


def _is_stale_real_path(value: object) -> bool:
    # PurePath built before pyfakefs patched pathlib -> bound to the real fs.
    return isinstance(value, pathlib.PurePath) and not type(
        value
    ).__module__.startswith("pyfakefs")


def _restore(obj: object, attr: str, value: Any) -> Callable[[], None]:
    return lambda: setattr(obj, attr, value)


@pytest.fixture(autouse=True)
def _fake_import_time_paths(request: pytest.FixtureRequest) -> Generator[None]:
    # Test modules build Path constants (and Path-valued call defaults) at
    # import time, before pyfakefs patches pathlib, so they stay bound to the
    # real fs. 3.11/3.12 tolerate mixing those with fake paths; 3.13+ (rewritten
    # pathlib) does not -- relative_to/equality across real+fake breaks. While
    # `fs` is active, swap such paths for fake equivalents; restore on teardown.
    if "fs" not in request.fixturenames:
        yield
        return

    request.getfixturevalue("fs")
    undo: list[Callable[[], None]] = []

    def rebind(value: Any) -> Any:
        return pathlib.Path(str(value)) if _is_stale_real_path(value) else value

    def patch_defaults(fn: FunctionType) -> None:
        if fn.__defaults__:
            faked = tuple(rebind(d) for d in fn.__defaults__)
            if faked != fn.__defaults__:
                undo.append(_restore(fn, "__defaults__", fn.__defaults__))
                fn.__defaults__ = faked
        if fn.__kwdefaults__:
            faked_kw = {k: rebind(d) for k, d in fn.__kwdefaults__.items()}
            if faked_kw != fn.__kwdefaults__:
                undo.append(_restore(fn, "__kwdefaults__", fn.__kwdefaults__))
                fn.__kwdefaults__ = faked_kw

    for module in list(sys.modules.values()):
        if not getattr(module, "__name__", "").startswith("tests"):
            continue
       
        members: dict[str, Any] = getattr(module, "__dict__", {})
        for name, value in list(members.items()):
            if _is_stale_real_path(value):
                undo.append(_restore(module, name, value))
                setattr(module, name, rebind(value))
            elif isinstance(value, FunctionType):
                patch_defaults(value)
            elif isinstance(value, type):
                for method in list(vars(value).values()):
                    if isinstance(method, FunctionType):
                        patch_defaults(method)

    try:
        yield
    finally:
        for restore in reversed(undo):
            restore()
