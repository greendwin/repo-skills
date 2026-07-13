---
id: s08t40
slug: standardize-id-styled-name-lists
status: pending
---

# Standardize [id]-styled name lists; fix comma-inside-marker bug

Three sites build a comma-joined name string and wrap the *whole* string in one `[id]…[/id]` Rich role marker, so the comma is styled as part of the id and individual names are not `escape()`d.

`src/repo_skills/cli/_resolve_untracked.py` · `_resolve_provider` (multi-provider match):
> BUG: comma should not be included to [id]

`src/repo_skills/cli/_source.py` · unregister-skills reporting:
> BUG: comma should not be included to [id]

`src/repo_skills/cli/_merge.py` · diverged-provider ambiguity:
> BUG: comma should not be inside [id] marker

`src/repo_skills/cli/_install.py` · ambiguous-source error formatting:
> TODO: TBD: can we simplify this?
> (note that we must inline formatting in `CliError`)

Fix: extract a shared helper that renders a list as `", ".join(f"[id]{escape(n)}[/id]" for n in ...)` — comma *outside* the role marker, each name individually escaped. `_install.py:170` already hand-rolls the correct form (`f"[id]{escape(name)}[/id]"` joined with `", "`); collapse it onto the helper, which answers its "can we simplify this?". Fix the three BUG sites to use the helper.

Remove each TODO/BUG comment once fixed.
