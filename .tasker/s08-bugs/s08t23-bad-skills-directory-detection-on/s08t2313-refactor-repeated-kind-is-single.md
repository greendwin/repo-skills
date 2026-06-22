---
id: s08t2313
slug: refactor-repeated-kind-is-single
status: pending
---

# Refactor: Repeated `kind is SINGLE and path is not None` guard with type-narrowing comment is a leaky DetectResult contr

## Refactor side-task
- depth: 1
- origin: s08t2303 — refactor finding "Repeated `kind is SINGLE and path is not None` guard with type-narrowing comment is a leaky DetectResult contract"

## Goal

Apply the deferred refactoring surfaced while processing s08t2303.
- location: src/repo_skills/discovery.py:20-23 (DetectResult) and src/repo_skills/cli/_source.py:175-177 (_detect_fresh_skills_dir)
- severity: nit

DetectResult models SINGLE as 'always has a path' but encodes path as `Path | None`, forcing every consumer to re-assert `detected.path is not None` and explain it with a `# SINGLE always carries a path; the None-check is type narrowing` comment. This invariant lives in prose comments rather than in the type, so the redundant guard and apology comment recur at each call site. A typed accessor would make the SINGLE-implies-path invariant load-bearing in one place. Reshaping the DetectResult type (typed accessor or per-kind union) touches the discovery contract consumed across the codebase, so it is structural work better seeded as a side task than forced in place.

## Suggested fix

Give DetectResult a helper such as `def require_path(self) -> Path:` that asserts/returns self.path for SINGLE, or model the result as a small union/dataclass per kind so SINGLE carries a non-optional path. Call sites then read `detected.require_path()` without the None re-check or comment.
