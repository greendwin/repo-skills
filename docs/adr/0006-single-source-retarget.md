# Merging a skill to another source is a single-source retarget

A skill may physically exist in several registered sources, but the manifest tracks exactly **one** tracking source per skill. `skills merge --source <X>` for a skill currently tracked by `<Y>` (X≠Y) writes the installed content into X and, by default, **retargets** the manifest to track X. `--keep-source` writes the content into X without changing the tracking source, leaving the skill tracked by Y. "Keep a skill in sync across two sources" is achieved by merging to each source in turn — there is no dual-tracking.

Base resolution for the cross-source merge is always performed against **X's** history (the Y-baseline commit is meaningless outside Y): if X already has the skill, the merge runs a forced base search over X's history; if X lacks it, the skill is added to X via the orphan-add flow. The Y-baseline "already synced" short-circuit is bypassed when X≠Y, so a skill that is unmodified relative to Y can still be retargeted into X.

## Considered Options

- **Single-source retarget (chosen).** Manifest keeps one tracking source. `--source` gains a second job — retargeting a tracked skill — alongside its existing orphan-target role. Small, composes with the existing orphan-add and `--search-base` flows. The cost is that "sync to both sources" stays manual (one merge per source).
- **Dual-source tracking.** Manifest tracks a *set* of sources and `update`/`status` reconcile across all of them. Rejected: requires a manifest-schema change and forces an answer to "which source wins when the two diverge?" — ambiguous semantics for a feature the originating bug never needed. The user only wanted `--source` to *do something* on a tracked skill instead of reporting sync state against the wrong source.
- **Leave `--source` orphan-only.** The reported bug (`merge <skill> -s <other>` → "already synced. Nothing to merge.") stays unfixed for tracked skills. Rejected.

## Consequences

- `--source` now means "the source to merge into" uniformly: for an orphan skill it picks the source to add to; for a tracked skill it retargets (or, with `--keep-source`, publishes without retargeting).
- Retargeting drops the manifest's reference to the old tracking source Y (Y still physically holds its copy). To return, the user merges back with `--source Y`.
- Provider resolution for a cross-source merge is has-skill based (`--from` / single-provider / ambiguous), **not** Y-baseline-divergence based — a skill unmodified vs Y can still be published to X.
- A genuinely two-way-synced skill is the user's responsibility to maintain via repeated merges; if real demand for automatic dual-sync appears, it is a separate feature with its own schema and ADR.
