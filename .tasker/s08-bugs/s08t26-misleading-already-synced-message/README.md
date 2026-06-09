---
id: s08t26
slug: misleading-already-synced-message
status: done
---

# Misleading "already synced" message

## Context

`skills merge` prints `"<skill> is already synced. Nothing to merge."` even when it has just re-attached a previously-detached skill. The message claims nothing happened, but the manifest was in fact mutated (the detached skill was brought back under tracking). After a detached skill becomes reachable again, the user runs `merge`, gets told it was "already synced", and is left confused — the displayed `mergeable` state seemingly contradicts the "nothing changed" message. We must tell the user the skill was re-attached and is now in sync.

## Decisions

- **Branch the in-sync message on whether a re-attach occurred** — the merge code already computes a re-attach condition just before raising and calls `_reattach_installed_skill`; reuse that boolean to choose the message instead of unconditionally printing "already synced". *Rejected: always printing one generic "in sync" message — it would keep conflating a genuine noop with a real state change.*
- **One unified "now tracked and in sync" message for both sub-cases** — the state-change outcome covers re-attach (`installed.detached` was set) and first-attach (path B's `not installed.baseline`, a previously untracked skill gaining a baseline). A single message `"<ident> is now tracked and in sync. Nothing to merge."` is truthful for both. *Rejected: two distinct messages keyed on `detached` — the re-attach-vs-never-tracked nuance isn't needed here; it already lives in `status`, and it would double the branch and test matrix.*
- **Keep `NoopError` / exit 0** — a manifest mutation happened, but no merge was performed and there's nothing for the user to act on, so the clean informational exit is correct. Wording keeps the familiar `"Nothing to merge."` tail for consistency with the sibling genuine-noop message (`"<ident> is already synced. Nothing to merge."`).
- **Centralize wording in a `_in_sync_message(skill_name, *, reattached)` helper** — both code paths currently duplicate the literal verbatim. The helper returns the re-attached wording when `reattached`, else the existing "already synced" wording, keeping each call site to two lines.

## Open questions

- None.

## Out of scope

- Changing detached-skill detection, the re-attach mechanics in `_reattach_installed_skill`, or how `status` displays detached/mergeable skills.
- Altering exit codes or the genuine-noop ("already synced") message text.

## Subtasks

- [x] [s08t2601](s08t2601-distinct-now-tracked-and-in.md): Distinct "now tracked and in sync" message on re-attach
