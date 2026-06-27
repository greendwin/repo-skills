---
id: s16t07
slug: add-provider-installed-path-to
status: in-review
---

# Add Provider.installed_path() to dedupe install-path math

Follow-up refactor from s08t40 (delayed). The one-liner `provider.install_path / skill_name` is recomputed at ~10 sites in `src/repo_skills/cli/_merge.py` (e.g. ~L155, L387, L409, L481, L592, L737, L761, L772, L799, L1030 — note differing receivers `provider` vs `prov`). If the install-path layout ever changes, one site can be missed, silently splitting "what got merged" from "what got recorded as baseline."

Goal: add a `Provider.installed_path(skill_name)` method and route all sites through it. Low risk, pure maintainability. Scope note: this intentionally touches pre-existing call sites beyond the s08t40 diff, which is why it was deferred out of that loop. Behavior-preserving; test-first against the existing suite; `uv run tox` clean.
