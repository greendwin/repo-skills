---
id: s08t11
slug: reattach-detached-skill-on-insync
status: pending
---

# Reattach detached skill on in-sync, no-from merge path

`_merge.py` no-provider branch — when `--from` is omitted and no provider has diverged (all in sync), the code raises NoopError without reattaching, but the symmetric provider-given branch reattaches first. A detached skill that is now back in sync keeps its stale `detached` flag on this path.

> TODO: this case is not covered, but we can possibly
> have here 'detached' skill, need to test it

Fix: uncomment the `_reattach_installed_skill(...)` call so both in-sync branches behave identically (reattach → NoopError). The helper is provider-independent and self-guards (no-ops unless detached), so it is safe. Add a test: detached + no `--from` + in-sync clears the flag, then NoopError. Remove the TODO once fixed.
