---
id: s04t1104
slug: evaluate-a-loc-locations-fixture
status: pending
---

# Evaluate a `loc`/`Locations` fixture to centralize test Path construction

## Context

After s04t1102 flipped test-side location constants to `str` and moved `Path(...)` construction to ~238 use-sites (ADR-0008: no surviving import-time `Path`), the refactor-review (thermo-nuclear lens) proposed centralizing those wraps behind a single fixture. Deferred from s04t1102 as a design decision, not a mechanical refactor — filed here for evaluation.

## Proposal

Replace the pervasive inline `Path(CONST) / ...` pattern with one fixture that builds real Paths *after* pyfakefs patches `pathlib`:

```python
@dataclass(frozen=True)
class Locations:
    install: Path; skills: Path; source_root: Path
    other_root: Path; other_skills: Path; cursor: Path

@pytest.fixture
def loc(fs: FakeFilesystem) -> Locations:  # fs active → fake-fs-bound Paths
    return Locations(install=Path(INSTALL_DIR), skills=Path(SKILLS_DIR), ...)
```

Use-sites become `loc.install / "tdd"` instead of `Path(INSTALL_DIR) / "tdd"`. Blast radius ~238 sites across ~14 test files, plus a `loc` param on every consuming test.

## Decision to make (this is an ADR-0008 revisit, not just a refactor)

- **Pro:** rebuild logic in one place; eliminates the `str`-typed-but-semantically-Path duality; invariant (Paths only exist post-patch) structurally enforced.
- **Con:** partially reverses ADR-0008's explicit "str constants + `Path()` at point of use" decision; the duplication lens argued the accessor *hides* the real-fs-vs-fake-fs timing rationale that inline `Path(CONST)` makes visible; wide diff for a debatable readability trade. Both refactor lenses in s04t1102 judged the inline pattern the accepted, readable choice.

If adopted, update ADR-0008 (or supersede its str-constant decision) to record the new shape and rationale. Must preserve the import-time-safety invariant and 3.11–3.14 green, including the 3.13/3.14 cross-fs check.

## Acceptance (if pursued)

- ADR-0008 updated to reflect the chosen shape.
- No surviving import-time `Path` in tests; grep gates stay clean.
- `uv run tox` green across 3.11–3.14, verified specifically on 3.13 and 3.14.
