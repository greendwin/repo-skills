---
id: s08t18
slug: error-when-manifest-version-is
status: done
---

# Error when manifest version is higher than supported

When loading the skill manifest, if `cfg.version > CURRENT_VERSION`, raise `AppError` telling the user the manifest was written by a newer version and they should update the tool. Currently any version mismatch silently returns an empty manifest, causing skills to vanish from `status`/`update` with no explanation.

`src/repo_skills/config/_skill_manifest.py`:
> TODO: config version can be *higher* then current,
>       we should stop then and ask to update

Fix: split the `cfg.version != CURRENT_VERSION` check into two branches — version too high → AppError with upgrade hint; version too low → keep current behavior (empty manifest, future migration path).

Remove the TODO once fixed.
