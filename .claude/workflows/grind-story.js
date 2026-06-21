export const meta = {
  name: 'grind-story',
  description: 'Autonomously drive a story\'s pending subtasks: branch, context pack, then per subtask implement → tox-gate → in-review → commit',
  whenToUse: 'Run an unattended implement loop over one story\'s pending subtasks on a dedicated grind branch.',
  phases: [
    { title: 'Setup', detail: 'create grind/<story> branch from HEAD, capture base ref' },
    { title: 'Bootstrap', detail: 'build the shared context pack once per run' },
    { title: 'Pick', detail: 'list the story subtree, take the next pending work item, set it in-progress' },
    { title: 'Implement', detail: 'tdd implement the work item to green targeted tests' },
    { title: 'Review-A', detail: 'code-reviewer lenses in parallel → triage → tdd fixes fix-now, until clean (cap 10)' },
    { title: 'Refactor-B', detail: 'refactor-reviewer lenses in parallel → apply-biased triage → tdd applies apply-now behavior-preservingly, until dry (cap 10)' },
    { title: 'File-side-tasks', detail: 'file delayed refactor findings as depth-bounded, deduped, capped flat side-tasks under the story' },
    { title: 'Verify', detail: 'uv run tox (all envs) green gate, with bounded fix-reconverge' },
    { title: 'Status', detail: 'move the work item to in-review (never done) before committing' },
    { title: 'Commit', detail: 'stage (incl. the .tasker status edit) + one commit-summary-style commit per work item' },
  ],
}

// ---- story id + recursion bounds -----------------------------------------
// Args is the story id, optionally followed by `key=value` tuning overrides:
//   "<story-id> maxDepth=3 totalCap=50"
// maxDepth gates how deep refactor side-tasks may spawn; totalCap is the hard
// backstop on side-tasks filed per run (thermo is never fully satisfied, so a
// ceiling is what guarantees the loop converges).
const rawArgs = typeof args === 'string' ? args.trim() : String(args || '').trim()
const argTokens = rawArgs.split(/\s+/).filter(Boolean)
const storyId = argTokens.length ? argTokens[0] : ''
if (!storyId) {
  return 'grind-story: no story id given. Invoke as Workflow({name:"grind-story", args:"<story-id>"}).'
}

const DEFAULT_MAX_DEPTH = 2
const DEFAULT_TOTAL_CAP = 30

function parsePositiveOverride(tokens, key, fallback) {
  for (const tok of tokens) {
    const eq = tok.indexOf('=')
    if (eq <= 0) continue
    if (tok.slice(0, eq) !== key) continue
    const n = Number.parseInt(tok.slice(eq + 1), 10)
    if (Number.isFinite(n) && n >= 0) return n
  }
  return fallback
}

const maxDepth = parsePositiveOverride(argTokens.slice(1), 'maxDepth', DEFAULT_MAX_DEPTH)
const totalSideTaskCap = parsePositiveOverride(argTokens.slice(1), 'totalCap', DEFAULT_TOTAL_CAP)

// Read an array-valued field off a possibly-null structured-output result,
// defaulting to [] — the one place the "agent may have died / returned a wrong
// shape" guard lives, so the call sites read as plain field access.
const arr = (obj, key) => (obj && Array.isArray(obj[key])) ? obj[key] : []

// ---- side-task depth marker (pure helpers) -------------------------------
// Depth + linkage live in the task description as a parseable marker block:
//
//   ## Refactor side-task
//   - depth: 1
//   - origin: s08t12 — thermo finding "collapse duplicate dispatch branches"
//
// Original subtasks have no such block and are therefore depth 0. A side-task
// spawned while processing a depth-d work item is born at depth d+1, recording
// the spawning task id + finding title on its `origin:` line.
const SIDE_TASK_HEADING = '## Refactor side-task'

// Parse the depth marker out of a task description. Returns {depth, origin} when
// a well-formed marker is present; null when absent (=> caller treats as depth
// 0); {malformed:true} when the heading is present but the depth line is not
// parseable (=> caller defaults to depth 0 AND logs the anomaly).
function parseDepthMarker(description) {
  const text = typeof description === 'string' ? description : ''
  if (!text.includes(SIDE_TASK_HEADING)) return null
  const depthMatch = text.match(/^[ \t]*-[ \t]*depth:[ \t]*(\d+)[ \t]*$/m)
  if (!depthMatch) return { malformed: true }
  const originMatch = text.match(/^[ \t]*-[ \t]*origin:[ \t]*(.+?)[ \t]*$/m)
  return {
    depth: Number.parseInt(depthMatch[1], 10),
    origin: originMatch ? originMatch[1].trim() : '',
  }
}

// Resolve a work item's depth AND origin from its description in ONE parse,
// logging malformed markers as anomalies. No marker => depth 0 with an empty
// origin (an original subtask). A hand-edited side-task with a broken marker is
// treated as depth 0 (it still gets fully processed; only its children are
// governed by depth) rather than crashing the run. The origin (the `- origin:`
// line of a side-task) is threaded into the report so every committed side-task
// shows where it came from.
function resolveMarker(taskId, description) {
  const marker = parseDepthMarker(description)
  if (marker === null) return { depth: 0, origin: '' }
  if (marker.malformed) {
    log(`Depth marker malformed on ${taskId} — treating as depth 0.`)
    return { depth: 0, origin: '' }
  }
  return { depth: marker.depth, origin: marker.origin || '' }
}

// Normalize a raw pick agent result into the uniform `{done, kind, items}`
// contract the loop consumes. A `done` (or empty/shapeless) result collapses to
// `{done: true, items: []}`. Otherwise every well-formed item (one carrying a
// `taskId`) is kept, the `kind` defaults to `feature` unless the agent tagged it
// `refactor`, and an items-less-but-not-done result is treated as done so the
// loop terminates rather than spinning on a malformed pick. The surviving
// well-formed members are then clamped to the kind's group cap — one for a
// feature pick, five for a refactor pick — so the cap holds even when the agent
// over-serves.
//
// The clamp is the deterministic, authoritative backstop: at most `cap` items
// ever reach `processItem`, regardless of what the agent returns. But the pick
// agent moves every member it returns to `in-progress` BEFORE returning, so a
// silent `slice` would strand the over-served members (6+) in a non-terminal
// `in-progress` status the pick loop never re-selects (it only picks `pending`),
// orphaning them. To make truncation a loud, self-healing backstop rather than a
// silent drop, the live (non-done) result also carries `overserved` — the
// taskIds of the well-formed members dropped beyond the cap — and a clamp logs
// loudly. The caller resets those ids back to `pending` so they re-enter the
// queue instead of being orphaned. In the obedient common case the agent honors
// the hard cap, `slice` is a no-op, and `overserved` is empty (zero cost).
function normalizePick(raw) {
  // Grouping bounds enforced regardless of the pick agent's judgment: a
  // `feature` pick is a single tracer-bullet subtask, so it is clamped to one
  // item; a `refactor` pick may batch up to five small, local, non-overlapping
  // side-tasks into one pass. These caps are the hard backstop behind the
  // prompt's grouping guidance.
  const FEATURE_GROUP_CAP = 1
  const REFACTOR_GROUP_CAP = 5
  // The terminal "nothing to do" pick. A fresh instance per call so a caller
  // mutating the returned object can never corrupt a shared sentinel. By
  // construction `done` is true exactly when `items` is empty, and both
  // early-exit branches below return this same shape — the invariant the loop
  // relies on (done ⇔ items empty) holds for every normalized pick.
  // The kind vocabulary's single normalizer: the default kind is `feature`
  // unless the agent tagged it `refactor`. Used for both the `donePick` default
  // and the live-pick branch so the "default is feature" rule lives in one place.
  const normalizeKind = (k) => (k === 'refactor' ? 'refactor' : 'feature')
  const donePick = () => ({ done: true, kind: normalizeKind(), items: [] })
  if (!raw || raw.done) return donePick()
  const items = (Array.isArray(raw.items) ? raw.items : [])
    .filter((it) => it && typeof it.taskId === 'string' && it.taskId)
    .map((it) => ({
      taskId: it.taskId,
      title: typeof it.title === 'string' ? it.title : '',
      description: typeof it.description === 'string' ? it.description : '',
      isStory: it.isStory === true,
    }))
  if (items.length === 0) return donePick()
  const kind = normalizeKind(raw.kind)
  const cap = kind === 'refactor' ? REFACTOR_GROUP_CAP : FEATURE_GROUP_CAP
  // The clamp dropped members the agent already moved to `in-progress`: surface
  // their ids loudly so the caller can reset them to `pending` rather than leave
  // them orphaned. Empty (and zero-cost) on the obedient common path.
  const overserved = items.slice(cap).map((it) => it.taskId)
  if (overserved.length > 0 && typeof log === 'function') {
    log(`Pick agent over-served a ${kind} group: ${items.length} well-formed members for a hard cap of ${cap}. Truncating and resetting the dropped ${overserved.length} (${overserved.join(', ')}) back to pending so they are not stranded in-progress.`)
  }
  return { done: false, kind, items: items.slice(0, cap), overserved }
}

// Group-aware repeat guard: return the first item of a pick group whose taskId
// is already in `seen`, or null when the whole group is fresh. Every item is
// checked so a group cannot smuggle an already-attempted id past the guard.
function firstRepeat(items, seen) {
  return items.find((it) => seen.has(it.taskId)) || null
}

// Record every taskId of a pick group in `seen` so the whole group — not just
// its first element — is excluded from later picks.
function recordSeen(items, seen) {
  for (const it of items) seen.add(it.taskId)
}

// Build the description body for a filed side-task: the marker block followed by
// the originating finding's detail so a later pick can run it through the full
// cycle like any original subtask.
function buildSideTaskDescription(depth, originTaskId, finding) {
  const f = finding || {}
  const title = f.title || '(untitled finding)'
  const lines = []
  lines.push(SIDE_TASK_HEADING)
  lines.push(`- depth: ${depth}`)
  lines.push(`- origin: ${originTaskId} — refactor finding "${title}"`)
  lines.push('')
  lines.push('## Goal')
  lines.push('')
  lines.push(`Apply the deferred refactoring surfaced while processing ${originTaskId}.`)
  if (f.location) lines.push(`- location: ${f.location}`)
  if (f.severity) lines.push(`- severity: ${f.severity}`)
  if (f.rationale) {
    lines.push('')
    lines.push(f.rationale)
  }
  if (f['suggested-fix']) {
    lines.push('')
    lines.push('## Suggested fix')
    lines.push('')
    lines.push(f['suggested-fix'])
  }
  return lines.join('\n')
}

// Stable signature for a delayed finding used to dedupe a re-surfaced finding
// against the side-tasks already filed this run AND against existing story
// children — so the loop converges instead of re-filing the same work forever.
function findingSignature(originTaskId, finding) {
  const f = finding || {}
  const loc = (f.location || '').trim().toLowerCase()
  const title = (f.title || '').trim().toLowerCase()
  return `${(originTaskId || '').trim()}::${title}::${loc}`
}

// ---- structured-output schemas ------------------------------------------
const BRANCH_SCHEMA = {
  type: 'object',
  properties: {
    branch: { type: 'string', description: 'the branch now checked out' },
    baseRef: { type: 'string', description: 'HEAD sha the branch was created from' },
  },
  required: ['branch', 'baseRef'],
}

const PACK_SCHEMA = {
  type: 'object',
  properties: {
    packPath: { type: 'string', description: 'absolute path to the written context pack' },
    digest: { type: 'string', description: 'short summary of what the pack contains' },
  },
  required: ['packPath'],
}

// The uniform pick contract: a pick is either `done`, or a `kind`-tagged group
// of `items`. A `feature` pick carries exactly one depth-0 subtask; a `refactor`
// pick batches 1–5 small, local, non-overlapping marker-bearing side-tasks. The
// loop iterates `items`. `kind` is consumed in `normalizePick` to pick the group
// cap (1 for feature, 5 for refactor); the per-item refactor/feature execution
// split is still driven by each item's depth marker (resolveMarker), not `kind`.
// Even a one-element group flows through the existing per-item machinery unchanged.
const PICK_ITEM = {
  type: 'object',
  properties: {
    taskId: { type: 'string', description: 'id of the chosen work item' },
    title: { type: 'string', description: 'title of the chosen work item' },
    isStory: { type: 'boolean', description: 'true when the work item is the story task itself' },
    description: {
      type: 'string',
      description: "the chosen work item's verbatim description body (used to parse its depth marker)",
    },
  },
  required: ['taskId'],
}

const PICK_SCHEMA = {
  type: 'object',
  properties: {
    done: { type: 'boolean', description: 'true when no pending work item remains' },
    kind: {
      type: 'string',
      enum: ['refactor', 'feature'],
      description: "`refactor` when the items are marker-bearing side-tasks; `feature` for an original depth-0 subtask",
    },
    items: {
      type: 'array',
      description: 'the chosen work items — a feature pick carries exactly one subtask; a refactor pick batches 1–5 small, local, non-overlapping side-tasks (hard cap 5)',
      items: PICK_ITEM,
    },
  },
  required: ['done'],
}

// What the dedupe agent reports about the story's current children: the RAW
// origin/finding fields of every refactor side-task already filed under the
// story. The signature string is built by `findingSignature` in JS so the exact
// format lives in exactly one place (the agent never reconstructs it).
const EXISTING_SIDE_TASKS_SCHEMA = {
  type: 'object',
  properties: {
    sideTasks: {
      type: 'array',
      description: 'the parsed origin/finding fields of every refactor side-task already filed under the story',
      items: {
        type: 'object',
        properties: {
          origin: { type: 'string', description: "the spawning task id from the side-task's `- origin:` line" },
          title: { type: 'string', description: 'the finding title quoted on the `- origin:` line' },
          location: { type: 'string', description: 'the `- location:` line value, or empty string when absent' },
        },
        required: ['origin', 'title'],
      },
    },
  },
  required: ['sideTasks'],
}

// One created side-task: the new id plus the signature it covers.
const FILE_SIDE_TASKS_SCHEMA = {
  type: 'object',
  properties: {
    created: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          taskId: { type: 'string', description: 'id of the created side-task' },
          title: { type: 'string', description: 'title given to the side-task' },
          signature: { type: 'string', description: 'finding signature this side-task covers' },
        },
        required: ['taskId'],
      },
    },
  },
  required: ['created'],
}

// The implement agent reports whether it reached its green-tests contract. A
// `tdd`-never-green outcome is a convergence failure the kind-split must act on,
// so it must be observable rather than silently swallowed.
const IMPLEMENT_SCHEMA = {
  type: 'object',
  properties: {
    green: { type: 'boolean', description: 'true when the targeted tests are green' },
    summary: { type: 'string', description: 'what was implemented, or why it could not reach green' },
  },
  required: ['green'],
}

// The reset agent reports whether the side-task's uncommitted changes were
// discarded back to a clean tree at the prior (preserved) commit.
const RESET_SCHEMA = {
  type: 'object',
  properties: {
    clean: { type: 'boolean', description: 'true when the working tree is clean after the reset' },
    head: { type: 'string', description: 'sha HEAD points at after the reset (the preserved prior commit)' },
  },
  required: ['clean'],
}

// The over-serve cleanup agent reports which over-served ids it moved back to
// `pending` so they re-enter the queue instead of being orphaned in-progress.
const RESET_TO_PENDING_SCHEMA = {
  type: 'object',
  properties: {
    reset: {
      type: 'array',
      items: { type: 'string', description: 'a task id moved back to pending' },
      description: 'the over-served ids reset to pending',
    },
  },
  required: ['reset'],
}

const VERIFY_SCHEMA = {
  type: 'object',
  properties: {
    green: { type: 'boolean', description: 'true when every tox environment passed' },
    failures: { type: 'string', description: 'concise but specific failure output when red' },
  },
  required: ['green'],
}

const COMMIT_SCHEMA = {
  type: 'object',
  properties: {
    sha: { type: 'string', description: 'sha of the created commit' },
    message: { type: 'string', description: 'the commit message used' },
    skipped: {
      type: 'array',
      items: { type: 'string' },
      description: 'untracked files deliberately left unstaged',
    },
  },
  required: ['sha', 'message'],
}

// The code-reviewer roster, resolved from the pack rather than hardcoded so it
// never drifts from the repo configs that the whole skill family depends on.
const ROSTER_SCHEMA = {
  type: 'object',
  properties: {
    lenses: {
      type: 'array',
      description: 'the code-reviewer lens names in roster order (empty when the roster is empty)',
      items: { type: 'string' },
    },
  },
  required: ['lenses'],
}

// The canonical finding shape, shared by the lens output AND every triage bucket
// so a triaged finding is contract-bound to round-trip its fields intact (the
// downstream JS reads `.title`/`.location`/`.severity` off these objects).
const FINDING_ITEM = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    location: { type: 'string', description: 'file:line or symbol the finding refers to' },
    severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] },
    rationale: { type: 'string' },
    'suggested-fix': { type: 'string' },
    lens: { type: 'string' },
  },
  required: ['title', 'location', 'severity', 'rationale', 'suggested-fix', 'lens'],
}

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string', description: 'the lens that produced these findings' },
    findings: { type: 'array', items: FINDING_ITEM },
  },
  required: ['lens', 'findings'],
}

const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    buckets: {
      type: 'object',
      properties: {
        'fix-now': { type: 'array', items: FINDING_ITEM },
        'deferred-to-refactor': { type: 'array', items: FINDING_ITEM },
        'out-of-scope': { type: 'array', items: FINDING_ITEM },
      },
      required: ['fix-now', 'deferred-to-refactor', 'out-of-scope'],
    },
  },
  required: ['buckets'],
}

// Phase B refactor triage: the apply-biased buckets, the policy flip toward
// applying genuinely-local quality work and deferring big structural work.
const REFACTOR_TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    buckets: {
      type: 'object',
      properties: {
        'apply-now': { type: 'array', items: FINDING_ITEM },
        'delayed': { type: 'array', items: FINDING_ITEM },
        'out-of-scope': { type: 'array', items: FINDING_ITEM },
      },
      required: ['apply-now', 'delayed', 'out-of-scope'],
    },
  },
  required: ['buckets'],
}

// Per-finding outcome from the apply agent — a refactor it cannot keep green is
// dropped (with a reason), never forced through by changing expected behavior.
const APPLY_SCHEMA = {
  type: 'object',
  properties: {
    results: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          finding: { type: 'string', description: 'title of the finding this result is for' },
          outcome: { type: 'string', enum: ['applied', 'dropped'] },
          reason: { type: 'string', description: 'why it was dropped (or a note when applied)' },
        },
        required: ['finding', 'outcome'],
      },
    },
  },
  required: ['results'],
}

// ---- agent prompts -------------------------------------------------------
const branchPrompt = `You are the setup step of an autonomous grind-story workflow for story ${storyId}.

Create the working branch and report the base ref. Use shell (Bash):
1. Capture the current HEAD sha: \`git rev-parse HEAD\` — this is the base ref every later agent diffs against.
2. Create and switch to \`grind/${storyId}\` from the current HEAD via \`git switch -c grind/${storyId}\`. If that branch already exists, just \`git switch grind/${storyId}\` instead of failing.
3. Confirm with \`git rev-parse --abbrev-ref HEAD\`.

Do not commit and do not modify any files. Return the branch name and the base ref sha.`

const bootstrapPrompt = `You are the bootstrap step of an autonomous grind-story workflow for story ${storyId}.

Build ONE shared context pack that every downstream agent reads first. Read these repo files and fold their RESOLVED prose into the pack — never make a downstream agent re-read the source configs, and never hardcode rosters/verbs elsewhere:
- \`docs/agents/task-tracker.md\` — the task-tracker verbs (read-task, list-tasks, set-status) and the status-role → native-status table. Spell out the EXACT MCP tool call a downstream agent must make for read-task, list-tasks, and for set-status to each of pending / in-progress / in-review.
- \`docs/agents/dev-loop.md\` — the code-reviewer and refactor-reviewer lens rosters (not exercised in this slice; include a brief summary for later slices).
- \`CLAUDE.md\` — development rules: \`uv run tox\` (all envs) is the gate and pre-existing failures must be fixed too; no task ids in code comments; the Python guide (no \`type: ignore\`, \`monkeypatch\` not \`unittest.mock.patch\`, no inline imports, \`assert_invoke\` not \`CliRunner\`).
- \`CONTEXT.md\` — the domain glossary / terminology.
- Any ADRs under \`docs/adr/\` — list them and one-line each so downstream agents respect them.

Write the pack to \`/tmp/grind-story/${storyId}.md\` (run \`mkdir -p /tmp/grind-story\` first). This path is OUTSIDE the working tree, so it is never committed and never pollutes the diff. A fresh agent given only this path must be able to resolve the task-tracker verbs/status-roles and the project conventions without opening the source configs.

Do not modify any tracked files. Return the pack path and a short digest.`

const pickPrompt = (packPath, excludeIds) => `You are the queue step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs and status roles).
${excludeIds && excludeIds.length ? `
ALREADY-ATTEMPTED this run — NEVER select any of these ids even if their status reads \`pending\` (a dropped side-task is reset back to pending but must not be re-picked): ${excludeIds.join(', ')}.
` : ''}
Select the next work item and move it to in-progress:
1. Using the read-task and list-tasks verbs from the pack, load story ${storyId} and enumerate its subtasks at any depth.
2. Among the eligible subtasks — status \`pending\` AND id NOT in the already-attempted list above — classify each by its description:
   - A REFACTOR task carries a \`## Refactor side-task\` marker block in its description.
   - A FEATURE task is an original subtask with NO such marker block.
3. PREFER refactor tasks: if any eligible refactor task exists, the pick is a REFACTOR pick (kind="refactor"); otherwise it is a FEATURE pick (kind="feature"). This drains refactor side-tasks ahead of feature work so feature work lands on already-refactored code.
4. Build the \`items\` group for the chosen kind:
   - FEATURE pick: choose the FIRST eligible feature subtask (natural order) — EXACTLY ONE item. Feature subtasks are tracer-bullet units with distinct acceptance criteria and must NEVER be batched; never mix a feature task into a refactor group.
   - REFACTOR pick: starting from the first eligible refactor task (natural order), BATCH a group of small, local, non-overlapping refactor side-tasks to land in one pass. Judge feasible work size from each candidate's description (title/location/severity/suggested-fix/rationale): prefer same-area, non-conflicting changes; STOP adding once the combined change looks too big to land+review cleanly in one pass. The group is 1–5 members — a HARD cap of 5, never more, even when more refactors are eligible; fewer than 5 eligible means a smaller group (1–4); a single eligible refactor is a valid group of one. Every member must be an eligible refactor task (a \`## Refactor side-task\` marker block) and NOT in the already-attempted list.
5. Degenerate case: if story ${storyId} has NO subtasks at all, the work item is the story task ${storyId} itself with kind="feature" (a single-item group) — but only if its own status is \`pending\` and it is not in the already-attempted list.
6. If no pending work item exists (no eligible pending subtask, and either the story has subtasks or the story itself is not eligible), nothing is left.

If you selected a work item:
- Apply the HARD cap of 5 YOURSELF before returning: a REFACTOR group is at most 5 members and a FEATURE group is exactly 1 — never return more. Decide the exact group first, then act on ONLY those members.
- Move EXACTLY the members you return — and no others — to the \`in-progress\` status role using the set-status verb from the pack BEFORE returning, so a mid-run crash leaves consistent tracker state. Do NOT set \`in-progress\` on any task you are not returning; over-serving (moving more than 5 to in-progress, or moving any you then omit) strands tasks in a non-terminal status.
- Return done=false, kind=<"refactor" or "feature">, and items=[ one object per member {taskId:<id>, title:<its title>, isStory:<true only if it is the story task itself>, description:<the work item's verbatim description body, exactly as stored, so the orchestrator can parse any depth marker>} ]. A FEATURE pick carries EXACTLY ONE item; a REFACTOR pick carries 1–5 items (hard cap 5).

If nothing is left, return done=true.

Only query and set status — do not implement anything, do not edit files.`

const implementPrompt = (item, packPath) => `You are the implementation step of an autonomous grind-story workflow, running the \`tdd\` skill in execute mode.

Read the context pack first: ${packPath}.

Work item: task ${item.taskId}${item.isStory ? ' (this IS the story task itself — it has no subtasks)' : ''}. Load it via the read-task verb from the pack${item.isStory ? '.' : `, and read parent story ${storyId} for the decisions/constraints that scope it.`}

The plan is PRE-APPROVED. Use \`tdd\`'s "skip review" path: skip planning/approval, go straight to tracer-bullet red→green cycles. Implement the task's acceptance criteria with behavior-level tests through the public interface. Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments).

Contract: drive toward GREEN targeted tests. Return green=true with a short summary once your targeted tests pass. If you genuinely cannot make them pass (the approach is unworkable, the acceptance criteria are contradictory, or repeated red persists), return green=false with the reason — do NOT fake green by deleting or weakening tests.

Boundaries — do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\` (a later step gates that). Only write the source/test files this task needs.

Report what you implemented and which files you created or changed.`

const resetPrompt = (item, baseRef) => `You are the discard step of an autonomous grind-story workflow. A side-task could not converge and its uncommitted changes must be thrown away so the run can continue from a clean tree.

Discard ONLY the uncommitted working-tree changes for the failed side-task ${item.taskId}, preserving every prior commit on the \`grind/${storyId}\` branch:
1. \`git reset --hard HEAD\` — this resets tracked changes back to the last commit (the prior subtask, already committed). It must NOT move the branch off its commits and must NOT touch \`${baseRef}\` history.
2. \`git clean -fd\` to remove untracked files this side-task created — but NEVER delete anything outside the working tree (the context pack under \`/tmp/grind-story/\` is outside the tree and must be left alone).
3. Confirm with \`git status --porcelain\` (expect empty) and \`git rev-parse HEAD\`.

Do NOT reset to ${baseRef}; do NOT delete branches or commits; do NOT touch \`/tmp/grind-story/\`. Return clean=true only if \`git status --porcelain\` is empty afterward, plus the HEAD sha.`

const rosterPrompt = (packPath) => `You are the roster-resolution step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}. It resolves this repo's \`code-reviewer\` lens roster (do not re-open the source configs).

Report the \`code-reviewer\` roster as an ordered list of lens names exactly as the pack names them (e.g. general, tests, performance). If the pack resolves the \`code-reviewer\` roster as EMPTY, return an empty list.

Do not review anything and do not edit files. Return only the lens names.`

const lensPrompt = (lens, packPath, baseRef) => `You are the \`${lens}\` code-reviewer lens of an autonomous grind-story workflow — a READ-ONLY reviewer. You never edit the tree; you only report findings.

Read the context pack first: ${packPath}. It resolves what the \`${lens}\` lens must check (conventions, ADRs, and the lens's own focus).

Review the change currently under review: inspect \`git diff ${baseRef}...HEAD\` plus any uncommitted working-tree changes (\`git diff\` and \`git status\`) for currency — that diff IS the change you review. Apply the \`${lens}\` lens's focus as resolved in the pack.

Return your findings as a list; for EACH finding fill every field:
- \`title\` — one line naming the problem.
- \`location\` — file:line (or symbol) it occurs at.
- \`severity\` — one of blocker / major / minor / nit.
- \`rationale\` — why it is a problem.
- \`suggested-fix\` — a concrete inline fix; you do NOT apply it.
- \`lens\` — "${lens}".

If you find nothing, return an empty findings list. Do not edit any file.`

const triagePrompt = (packPath, findingsJson) => `You are the triage step of an autonomous grind-story workflow. You exercise judgement the orchestrator JS cannot — you do not write code.

Read the context pack first: ${packPath} (it resolves the ADRs and conventions the findings may cite).

Here are the raw findings from the \`code-reviewer\` lenses, as JSON:
---
${findingsJson}
---

First DEDUP: collapse findings that refer to the same underlying issue — overlapping \`location\` plus overlapping description — into one, keeping the strongest severity. Then BUCKET every surviving finding into exactly one of:
- \`fix-now\` — the change under review introduced it AND it threatens delivered behavior: a correctness bug, a security hole, data loss, a missing/weak test for new behavior, or an ADR violation.
- \`deferred-to-refactor\` — a legitimate quality issue that does NOT threaten delivered behavior (style, structure, naming, duplication, perf nits). When you are UNCERTAIN whether something belongs in fix-now, put it here.
- \`out-of-scope\` — pre-existing noise unrelated to this change, or ADR-conflicting suggestions. Reported, never acted on.

Rules: never silently drop a finding (every input finding lands in exactly one bucket), and never scope-creep into work the change did not touch. Return the three buckets; each entry keeps the finding's original fields.`

const reviewFixPrompt = (pick, packPath, fixJson) => `You are the fix step of an autonomous grind-story workflow, running the \`tdd\` skill to resolve \`fix-now\` review findings for task ${pick.taskId}.

Read the context pack first: ${packPath}.

These review findings were triaged \`fix-now\` — each threatens delivered behavior and must be fixed under tests:
---
${fixJson}
---

For each finding: write a failing behavior-level test that captures the correct behavior (red), then make it pass (green). Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments). Test behavior through the public interface, not internals.

Contract: return only when your targeted tests are GREEN.

Boundaries — do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\`. Only write the source/test files these findings require. Report what you changed.`

const refactorRosterPrompt = (packPath) => `You are the roster-resolution step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}. It resolves this repo's \`refactor-reviewer\` lens roster (do not re-open the source configs).

Report the \`refactor-reviewer\` roster as an ordered list of lens names exactly as the pack names them (e.g. duplication, thermo-nuclear). If the pack resolves the \`refactor-reviewer\` roster as EMPTY, return an empty list.

Do not review anything and do not edit files. Return only the lens names.`

const refactorLensPrompt = (lens, packPath, baseRef) => `You are the \`${lens}\` refactor-reviewer lens of an autonomous grind-story workflow — a READ-ONLY reviewer. You never edit the tree; you only report findings.

Read the context pack first: ${packPath}. It resolves what the \`${lens}\` lens must check (conventions, ADRs, and the lens's own focus).${lens === 'thermo-nuclear' ? ' The `thermo-nuclear` lens delegates to the `thermo-nuclear-code-quality-review` skill — apply that skill\'s focus (structural regressions, dramatic-simplification / code-judo that DELETES complexity, spaghetti conditionals, abstraction quality, mislayered logic).' : ''}

Review the change currently under review: inspect \`git diff ${baseRef}...HEAD\` plus any uncommitted working-tree changes (\`git diff\` and \`git status\`) for currency — that diff IS the change you review. Apply the \`${lens}\` lens's focus as resolved in the pack.

Return your findings as a list; for EACH finding fill every field:
- \`title\` — one line naming the refactoring opportunity.
- \`location\` — file:line (or symbol) it occurs at.
- \`severity\` — one of blocker / major / minor / nit.
- \`rationale\` — why the refactoring improves the code.
- \`suggested-fix\` — a concrete inline refactoring; you do NOT apply it.
- \`lens\` — "${lens}".

If you find nothing, return an empty findings list. Do not edit any file.`

const refactorTriagePrompt = (packPath, findingsJson) => `You are the refactor-triage step of an autonomous grind-story workflow. You exercise judgement the orchestrator JS cannot — you do not write code.

Read the context pack first: ${packPath} (it resolves the ADRs and conventions the findings may cite).

Here are the raw refactor findings — the \`refactor-reviewer\` lens output merged with the \`deferred-to-refactor\` findings carried from Phase A — as JSON:
---
${findingsJson}
---

First DEDUP: collapse findings that refer to the same underlying issue — overlapping \`location\` plus overlapping description — into one, keeping the strongest severity. Then BUCKET every surviving finding into exactly one of:
- \`apply-now\` — improves quality, is scoped to the current task, and has a LOCAL blast radius: a refactoring the \`tdd\` apply agent can land behavior-preservingly right here (e.g. obvious local duplication collapse).
- \`delayed\` — genuinely valuable structural work that is big, touches OTHER systems, or extends scope: rule-of-three duplication across modules, real code-judo that deletes complexity but reaches beyond this task. Collected as side-task seeds; NOT applied in place here.
- \`out-of-scope\` — an ADR-conflicting "improvement" (the ADR always wins) or unrelated noise. Reported only, never applied and never filed.

Bias AGGRESSIVELY toward \`delayed\`: route genuinely valuable structural work there rather than forcing it in place. Reserve \`out-of-scope\` STRICTLY for ADR-conflicts and noise. An ADR-conflicting suggestion is always \`out-of-scope\`, never \`apply-now\` or \`delayed\`.

Rules: never silently drop a finding (every input finding lands in exactly one bucket), and never scope-creep. Return the three buckets; each entry keeps the finding's original fields.`

const applyPrompt = (pick, packPath, applyJson) => `You are the apply step of an autonomous grind-story workflow, running the \`tdd\` skill to apply \`apply-now\` refactorings for task ${pick.taskId} BEHAVIOR-PRESERVINGLY.

Read the context pack first: ${packPath}.

These refactor findings were triaged \`apply-now\` — each is a local, scoped quality improvement to land under the green-test contract:
---
${applyJson}
---

For each finding: apply the refactoring while keeping the existing tests green. You MAY rework production code and fix test references to renamed/moved internals (same assertion, same expected value), but you must NEVER change expected behavior to force a refactor through. A refactoring you cannot keep green is DROPPED and reported with a reason — never forced. Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments).

Contract: leave the targeted tests GREEN. Boundaries — do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\`. Only write the source/test files these refactorings require.

Return one result per input finding: \`{finding: <its title>, outcome: applied|dropped, reason: <why dropped, or a note>}\`.`

const verifyPrompt = (packPath) => `You are the green-gate step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}.

Run the full acceptance gate exactly as \`CLAUDE.md\` requires: \`uv run tox\` (ALL environments). Do not edit any files. Do not use \`--no-verify\` and do not skip any environment.

Return green=true only if every environment passed. Otherwise return green=false and put the relevant failure output (failing env names, test ids, error messages, file:line) into \`failures\` — concise but specific enough for a fixer to act without re-running.`

const fixPrompt = (pick, packPath, failures) => `You are the fix step of an autonomous grind-story workflow, running the \`tdd\` skill to repair a red \`uv run tox\`.

Read the context pack first: ${packPath}.

The full \`uv run tox\` is RED. Failures:
---
${failures}
---

Per \`CLAUDE.md\` you must fix ALL reported tox issues — including pre-existing ones, not only those introduced by task ${pick.taskId}. Keep changes behavior-correct and test-backed where it makes sense. Honor the conventions in the pack (no \`type: ignore\`, \`monkeypatch\` not \`unittest.mock.patch\`, no inline imports, \`assert_invoke\` not \`CliRunner\`).

Boundaries — do NOT commit, do NOT change task status. Only edit the source/test/config needed to get tox green. Report what you changed.`

const commitPrompt = (pick, packPath) => `You are the commit step of an autonomous grind-story workflow, running the \`commit-summary\` message logic NON-INTERACTIVELY (this is unattended — never prompt).

Read the context pack first: ${packPath}.

Produce exactly ONE commit on the \`grind/${storyId}\` branch for the current change.

The task-tracker stores task status in git-tracked \`.tasker/<…>.md\` frontmatter, so the pick (→ in-progress) and status (→ in-review) steps that ran before you left tracked edits under \`.tasker/\`. Those edits are EXPECTED and MUST ride in this commit — never unstage or exclude them as noise; \`git add -u\` stages them along with the source/test changes.

Staging:
1. \`git add -u\` to stage tracked modifications/deletions (this includes the \`.tasker/\` status-frontmatter edits for task ${pick.taskId}).
2. \`git status --porcelain\` for untracked (\`??\`) entries. For each:
   - DENYLIST — never stage, never prompt: \`.env\`, \`.env.*\`, \`*.key\`, \`*.pem\`, \`*.p12\`, \`*.pfx\`, \`*.secret\`, \`credentials.json\`, \`secrets.yaml\`, \`.netrc\`, \`.npmrc\`, \`.venv/\`, \`venv/\`, \`node_modules/\`, \`__pycache__/\`, \`*.sqlite\`, \`*.db\`.
   - SUSPICIOUS — never stage, never prompt: editor temps (\`*.swp\`, \`*.swo\`, \`*~\`), backups (\`*.bak\`, \`*.orig\`), OS artifacts (\`.DS_Store\`, \`Thumbs.db\`), or anything common practice would not check in.
   - Otherwise — clearly project source/tests/docs created for task ${pick.taskId}: stage it.
   Collect every untracked path you skip into a list to return.
3. Compose the message with \`commit-summary\` rules: calibrate prefix/bullet style from \`git log -n 10\`, pick the right prefix, imperative subject ≤72 chars, body only when warranted, correct backtick usage. Do NOT put any task id (e.g. ${pick.taskId}) in the message — match the repo log style. Never append \`Co-Authored-By\` or \`Generated with Claude Code\` footers.
4. Commit via \`git commit -F <tmpfile>\` (write the raw message to a temp file, then remove it).

Return the resulting commit sha (\`git rev-parse HEAD\`), the exact message you used, and the list of skipped untracked files.`

const resetToPendingPrompt = (packPath, ids, kind) => `You are the over-serve cleanup step of an autonomous grind-story workflow.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs and status roles).

The pick agent over-served a ${kind} group: it moved more members to \`in-progress\` than that group's hard cap allows, so these tasks were truncated from the batch and must NOT be left stranded in a non-terminal status. Move EACH of these tasks back to the \`pending\` status role using the set-status verb resolved in the pack so a later pick can re-select them: ${ids.join(', ')}.

Do nothing else. Set status only — do not implement anything, do not edit other files. Confirm the ids you reset.`

const statusPrompt = (pick, packPath) => `You are the status step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}.

Move task ${pick.taskId} to the \`in-review\` status role using the set-status verb resolved in the pack. Never move it to \`done\`. Do nothing else, and confirm the new status.`

const existingSideTasksPrompt = (packPath) => `You are the dedupe-scan step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs).

Using the read-task verb, load story ${storyId} and inspect every one of its children. A refactor side-task is a child whose description contains a \`## Refactor side-task\` marker block with an \`- origin:\` line. The origin line looks like:
\`- origin: <spawning-task-id> — refactor finding "<finding title>"\`

For EACH such existing side-task, emit one row with these RAW fields (do NOT lowercase, trim, or join them — the orchestrator canonicalizes them):
- \`origin\` — the \`<spawning-task-id>\` from the \`- origin:\` line.
- \`title\` — the \`<finding title>\` quoted on the \`- origin:\` line.
- \`location\` — the value of the side-task body's \`- location:\` line if present, else an empty string.

Return only the list of rows. Do not create, edit, or re-status any task.`

const fileSideTasksPrompt = (packPath, originTaskId, items) => `You are the side-task filing step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs — in particular create-subtask).

File each of the following refactor side-tasks as a FLAT child of story ${storyId} (parent = ${storyId}, NOT nested under ${originTaskId}). Use the create-subtask verb with \`parent: "${storyId}"\`, the given title, and the given description VERBATIM (it already contains the depth marker block). Each item:
---
${JSON.stringify(items, null, 2)}
---

For each item, create the subtask and report its new id alongside the item's \`signature\` (copy the signature through unchanged). The side-tasks are born \`pending\` — do NOT start, review, or finish them. Create nothing else.

Return one entry per item: \`{taskId: <new id>, title: <title used>, signature: <the item's signature>}\`.`

// ---- orchestration -------------------------------------------------------
const GUARD_MAX = 100

// Single source of truth for each bounded retry loop's round cap, so a phase and
// its cap can never drift apart and the split (a smaller Verify cap, a larger
// review/refactor cap) lives in one pure, testable place. Verify is cheap to
// re-run, so it caps low; Review-A and Refactor-B converge slower and share the
// higher cap. Pure (no free variables) so it is reachable through the test seam.
function phaseCap(phase) {
  const PHASE_CAPS = { 'Verify': 5, 'Review-A': 10, 'Refactor-B': 10 }
  return PHASE_CAPS[phase]
}

// Shared `<phase> round <round>/<cap> for <taskId>` log prefix for the three
// structurally identical bounded retry loops (Review-A, Refactor-B, Verify), so
// the phase/cap pair lives at the loop that owns it and a future cap change
// cannot drift between the loop bound and the log text.
const roundTag = (phase, round, cap, taskId) => `${phase} round ${round}/${cap} for ${taskId}`

phase('Setup')
const setup = await agent(branchPrompt, { label: 'branch', schema: BRANCH_SCHEMA })
if (!setup) return `grind-story: setup step failed for story ${storyId} — could not create the grind branch.`

phase('Bootstrap')
const pack = await agent(bootstrapPrompt, { label: 'context-pack', schema: PACK_SCHEMA })
if (!pack) return `grind-story: bootstrap step failed for story ${storyId} — no context pack was written.`
const packPath = pack.packPath

// Resolve the code-reviewer roster from the pack once — it does not change per
// subtask. An empty roster means Phase A is skipped for the whole run.
const roster = await agent(rosterPrompt(packPath), { label: 'roster:code-reviewer', schema: ROSTER_SCHEMA })
const reviewLenses = arr(roster, 'lenses').filter((l) => typeof l === 'string' && l.trim())
if (reviewLenses.length === 0) {
  log('Phase A skipped for the run: the code-reviewer roster resolved empty.')
}

// Resolve the refactor-reviewer roster once too — it likewise does not change
// per subtask. An empty roster means Phase B is skipped for the whole run.
const refactorRoster = await agent(refactorRosterPrompt(packPath), { label: 'roster:refactor-reviewer', schema: ROSTER_SCHEMA })
const refactorLenses = arr(refactorRoster, 'lenses').filter((l) => typeof l === 'string' && l.trim())
if (refactorLenses.length === 0) {
  log('Phase B skipped for the run: the refactor-reviewer roster resolved empty.')
}

const processed = []
const deferredFindings = []
const delayedFindings = []
const outOfScopeFindings = []
const droppedRefactors = []
const seen = new Set()

// Kind-split failure bookkeeping. A side-task (depth >= 1) that cannot converge
// is `git reset --hard`-discarded and recorded here, then the loop continues;
// the report surfaces every dropped side-task with its reason. `escalations`
// collects the non-halting convergence problems worth a human's attention (a
// `fix-now` still open at the review cap), feeding the report's escalation section.
const droppedSideTasks = []
const escalations = []

// Side-task filing state, threaded across iterations so the run converges:
// `filedSignatures` dedupes re-surfaced findings against everything already
// filed this run; `filedSideTasks` and `residualFindings` feed the report;
// `capSuppressed` records findings dropped once the total cap is hit.
const filedSignatures = new Set()
const filedSideTasks = []
const residualFindings = []
const capSuppressed = []
let sideTaskCount = 0

// Convergence-failure control flow is expressed with two sentinels thrown out of
// the phase helpers and caught once around the loop, so the kind-split decision
// lives in exactly one place instead of being re-spelt at every failure site:
//   `Halt`     -> end the whole run, returning the report with this failure.
//   `SkipItem` -> abandon just this work item and continue with the next.
class Halt {
  constructor(failure) { this.failure = failure }
}
class SkipItem {}

// Kind-split on a convergence failure (tdd never green, fix-now open at the cap,
// or tox red at the cap), mirroring dev-loop's green contract. This function
// NEVER returns normally — it always throws one of the sentinels above:
//   depth 0 (original subtask) -> throw Halt: leave the tree dirty for
//     inspection, prior commits preserved, the report names the failure point.
//   depth >= 1 (side-task)      -> `git reset --hard` (via an agent) to discard
//     just this side-task's uncommitted changes — the tree is clean because the
//     prior subtask is already committed — record it dropped, then throw SkipItem
//     to continue with the next pending work item. A reset that does not leave a
//     clean tree escalates to Halt rather than building on a dirty tree.
async function failConvergence(item, depth, reason, failures) {
  if (depth === 0) {
    log(`HARD FAILURE: ${item.taskId} (depth 0) could not converge — ${reason}. Halting the run.`)
    throw new Halt({ taskId: item.taskId, title: item.title, reason, failures })
  }
  log(`${item.taskId} (depth ${depth}) could not converge — ${reason}. Discarding its changes (git reset --hard) and continuing.`)
  const reset = await agent(resetPrompt(item, setup.baseRef), { label: `reset:${item.taskId}`, schema: RESET_SCHEMA })
  if (!reset || !reset.clean) {
    log(`HARD FAILURE: could not cleanly discard side-task ${item.taskId} — halting to avoid building on a dirty tree.`)
    throw new Halt({
      taskId: item.taskId,
      title: item.title,
      reason: `side-task git reset --hard did not leave a clean tree (${reason})`,
      failures,
    })
  }
  droppedSideTasks.push({ taskId: item.taskId, title: item.title, depth, reason })
  throw new SkipItem()
}

// Fan the given lenses out in parallel for one review round and flatten their
// surviving findings — the shared fanout for both review phases. A lens that
// died or returned null contributes nothing; the round continues.
async function runLensRound(lenses, promptFn, labelPrefix, round) {
  const results = await parallel(
    lenses.map((lens) =>
      agent(promptFn(lens, packPath, setup.baseRef), { label: `${labelPrefix}:${lens}:${round}`, schema: FINDINGS_SCHEMA })),
  )
  return results.flatMap((r) => arr(r, 'findings'))
}

// Phase A — code-reviewer lenses → triage → tdd fixes fix-now, re-converging
// until no fix-now remains or the round cap is hit. Skipped on an empty roster.
// Returns the `deferred-to-refactor` findings to carry into Phase B; throws
// (Halt / SkipItem) via failConvergence when fix-now is still open at the cap.
async function reviewPhaseA(item, depth) {
  const carriedDeferred = []
  if (reviewLenses.length === 0) return carriedDeferred
  const ph = 'Review-A'
  phase(ph)
  const cap = phaseCap(ph)
  let openFixNow = []
  for (let round = 1; round <= cap; round++) {
    const findings = await runLensRound(reviewLenses, lensPrompt, 'lens', round)
    if (findings.length === 0) {
      openFixNow = []
      log(`${roundTag(ph, round, cap, item.taskId)}: lenses raised no findings.`)
      break
    }

    const triage = await agent(triagePrompt(packPath, JSON.stringify(findings, null, 2)), {
      label: `triage-A:${round}`,
      schema: TRIAGE_SCHEMA,
    })
    const buckets = (triage && triage.buckets) || {}
    const fixNow = arr(buckets, 'fix-now')
    const deferred = arr(buckets, 'deferred-to-refactor')
    for (const f of deferred) {
      deferredFindings.push({ taskId: item.taskId, finding: f })
      carriedDeferred.push(f)
    }

    if (fixNow.length === 0) {
      openFixNow = []
      log(`${roundTag(ph, round, cap, item.taskId)}: no fix-now findings; ${deferred.length} carried to Phase B.`)
      break
    }
    openFixNow = fixNow
    log(`${roundTag(ph, round, cap, item.taskId)}: ${fixNow.length} fix-now finding(s); routing to a tdd fix agent.`)
    if (round === cap) break
    await agent(reviewFixPrompt(item, packPath, JSON.stringify(fixNow, null, 2)), { label: `fix-A:${round}` })
  }
  if (openFixNow.length > 0) {
    // Cap reached with fix-now still open — a convergence failure: the change
    // carries an unresolved behavior-threatening finding, so it must not be
    // committed. failConvergence halts an original subtask (escalating the open
    // finding) or discards-and-continues a side-task.
    escalations.push({
      kind: 'fix-now-cap-open',
      taskId: item.taskId,
      depth,
      count: openFixNow.length,
      detail: `${openFixNow.length} fix-now finding(s) still open after ${cap} Review-A rounds`,
    })
    await failConvergence(
      item,
      depth,
      `${openFixNow.length} fix-now finding(s) still open at the ${cap}-round cap`,
      JSON.stringify(openFixNow, null, 2),
    )
  }
  return carriedDeferred
}

// Phase B — refactor-reviewer lenses (merged with Phase A's deferred findings)
// → apply-biased triage → tdd applies apply-now behavior-preservingly, looping
// until no new apply-now or the round cap is hit. Skipped on an empty roster.
// Returns the `delayed` findings to seed side-task filing.
async function refactorPhaseB(item, carriedDeferred) {
  const carriedDelayed = []
  if (refactorLenses.length === 0) return carriedDelayed
  const ph = 'Refactor-B'
  phase(ph)
  const cap = phaseCap(ph)
  for (let round = 1; round <= cap; round++) {
    const findings = await runLensRound(refactorLenses, refactorLensPrompt, 'refactor-lens', round)
    // Only the first round merges the Phase A deferred findings — later rounds
    // re-review the now-refactored tree fresh so they cannot re-surface stale
    // findings already applied or routed.
    if (round === 1) findings.push(...carriedDeferred)

    if (findings.length === 0) {
      log(`${roundTag(ph, round, cap, item.taskId)}: lenses raised no findings — loop dry.`)
      break
    }

    const triage = await agent(refactorTriagePrompt(packPath, JSON.stringify(findings, null, 2)), {
      label: `triage-B:${round}`,
      schema: REFACTOR_TRIAGE_SCHEMA,
    })
    const buckets = (triage && triage.buckets) || {}
    const applyNow = arr(buckets, 'apply-now')
    const delayed = arr(buckets, 'delayed')
    const outOfScope = arr(buckets, 'out-of-scope')
    // `delayed` seeds the side-tasks filed after Phase B; `out-of-scope` is
    // reported only. Both are recorded globally for the report.
    for (const f of delayed) {
      delayedFindings.push({ taskId: item.taskId, finding: f })
      carriedDelayed.push(f)
    }
    for (const f of outOfScope) outOfScopeFindings.push({ taskId: item.taskId, finding: f })

    if (applyNow.length === 0) {
      log(`${roundTag(ph, round, cap, item.taskId)}: no apply-now; ${delayed.length} delayed, ${outOfScope.length} out-of-scope — loop dry.`)
      break
    }
    log(`${roundTag(ph, round, cap, item.taskId)}: ${applyNow.length} apply-now refactoring(s); routing to a tdd apply agent.`)
    if (round === cap) {
      // Phase B is best-effort and behavior-preserving (tests stay green), so an
      // unconverged refactor loop is logged and stopped — NOT a convergence
      // failure, unlike Phase A's open fix-now.
      log(`Refactor-B cap reached for ${item.taskId} with apply-now work still surfacing — stopping the refactor loop.`)
      break
    }
    const applied = await agent(applyPrompt(item, packPath, JSON.stringify(applyNow, null, 2)), {
      label: `apply-B:${round}`,
      schema: APPLY_SCHEMA,
    })
    const results = arr(applied, 'results')
    for (const res of results) {
      if (res && res.outcome === 'dropped') {
        droppedRefactors.push({ taskId: item.taskId, finding: res.finding, reason: res.reason || '(no reason given)' })
        log(`Refactor dropped for ${item.taskId}: "${res.finding}" — ${res.reason || '(no reason given)'}`)
      }
    }
  }
  return carriedDelayed
}

// File side-tasks from this subtask's `delayed` findings. Spawning is gated by
// depth: a work item already at maxDepth files NOTHING — its delayed findings
// become residual instead (the item itself is still fully refactored/committed,
// only its children are suppressed). Below maxDepth, surviving findings are
// deduped (against this run's already-filed set AND the story's existing
// children) and filed flat under the story at depth+1, bounded by the total
// cap; the overflow is reported as suppressed-by-cap.
async function fileSideTasks(item, depth, carriedDelayed) {
  if (carriedDelayed.length === 0) return
  if (depth >= maxDepth) {
    for (const f of carriedDelayed) residualFindings.push({ taskId: item.taskId, depth, finding: f })
    log(`${item.taskId} is at depth ${depth} (maxDepth ${maxDepth}) — its ${carriedDelayed.length} delayed finding(s) reported as residual, not filed.`)
    return
  }
  phase('File-side-tasks')
  // Seed the run's filed-signature set from the story's existing children so a
  // finding re-surfaced on a later round is not filed twice. The scan agent
  // returns raw origin/finding fields; `findingSignature` canonicalizes them so
  // the signature format lives in exactly one place.
  const existing = await agent(existingSideTasksPrompt(packPath), {
    label: `dedupe-scan:${item.taskId}`,
    schema: EXISTING_SIDE_TASKS_SCHEMA,
  })
  const existingRows = arr(existing, 'sideTasks')
  for (const row of existingRows) {
    if (!row || typeof row.origin !== 'string') continue
    filedSignatures.add(findingSignature(row.origin, { title: row.title, location: row.location }))
  }

  const toFile = []
  for (const finding of carriedDelayed) {
    const sig = findingSignature(item.taskId, finding)
    if (filedSignatures.has(sig)) {
      log(`Skipping already-filed delayed finding "${(finding && finding.title) || '(untitled)'}" from ${item.taskId}.`)
      continue
    }
    // Claim the signature now so duplicates within the same batch collapse.
    filedSignatures.add(sig)
    if (sideTaskCount + toFile.length >= totalSideTaskCap) {
      capSuppressed.push({ taskId: item.taskId, finding })
      continue
    }
    const childDepth = depth + 1
    toFile.push({
      signature: sig,
      title: `Refactor: ${(finding && finding.title) || 'deferred finding'}`.slice(0, 120),
      description: buildSideTaskDescription(childDepth, item.taskId, finding),
    })
  }

  const n = capSuppressed.filter((c) => c.taskId === item.taskId).length
  if (n > 0) {
    log(`Total side-task cap (${totalSideTaskCap}) reached — ${n} delayed finding(s) from ${item.taskId} suppressed, not filed.`)
  }

  if (toFile.length > 0) {
    const filed = await agent(fileSideTasksPrompt(packPath, item.taskId, toFile), {
      label: `file-side-tasks:${item.taskId}`,
      schema: FILE_SIDE_TASKS_SCHEMA,
    })
    const created = arr(filed, 'created')
    for (const c of created) {
      if (!c || !c.taskId) continue
      sideTaskCount += 1
      filedSideTasks.push({ originTaskId: item.taskId, childTaskId: c.taskId, title: c.title, depth: depth + 1 })
      log(`Filed side-task ${c.taskId} (depth ${depth + 1}) from ${item.taskId}: "${c.title || ''}".`)
    }
  }
}

// Run the full `uv run tox` gate, routing failures to a fix agent and
// re-verifying until green or the round cap is hit. Throws (Halt / SkipItem) via
// failConvergence when tox is still red at the cap.
async function verifyStep(item, depth) {
  const ph = 'Verify'
  phase(ph)
  const cap = phaseCap(ph)
  let lastFailures = ''
  for (let round = 1; round <= cap; round++) {
    const v = await agent(verifyPrompt(packPath), { label: `tox:${round}`, schema: VERIFY_SCHEMA })
    if (v && v.green) return
    lastFailures = (v && v.failures) || '(no failure detail captured)'
    log(`${roundTag(ph, round, cap, item.taskId)}: tox red; routing failures to a fix agent.`)
    if (round === cap) break
    await agent(fixPrompt(item, packPath, lastFailures), { label: `fix:${round}` })
  }
  await failConvergence(item, depth, `uv run tox still red after ${cap} fix rounds`, lastFailures)
}

// Move the work item to in-review then produce its single commit (including the
// `.tasker` status edit). Throws (Halt / SkipItem) via failConvergence when the
// commit step fails after a green gate. Records the commit in `processed`.
async function statusAndCommit(item, depth, origin) {
  // Move to in-review BEFORE committing so the task-tracker's `.tasker` status
  // edit is part of this work item's commit rather than left dirty and swept
  // into the next item's commit (or stranded uncommitted for the last item).
  phase('Status')
  await agent(statusPrompt(item, packPath), { label: `review:${item.taskId}` })

  phase('Commit')
  const commit = await agent(commitPrompt(item, packPath), { label: `commit:${item.taskId}`, schema: COMMIT_SCHEMA })
  if (!commit) {
    // The commit step itself failed after a green gate. failConvergence halts an
    // original subtask (its green changes, now in-review, left dirty for
    // inspection) or discards a side-task — `git reset --hard` also reverts the
    // in-review status edit back to in-progress — and continues.
    await failConvergence(item, depth, 'commit step returned no result', '')
  }
  if (commit.skipped && commit.skipped.length) {
    log(`Skipped untracked files (not staged): ${commit.skipped.join(', ')}`)
  }
  processed.push({ taskId: item.taskId, title: item.title, sha: commit.sha, message: commit.message, depth, origin })
}

// Run one work item through the full per-item pipeline. A pick item flows here
// whether it arrived alone (a feature subtask) or as one element of a group (a
// refactor side-task); grouping is uniform so a one-element group is just the
// degenerate case of the same path.
async function processItem(item) {
  // Depth governs whether THIS work item may spawn refactor side-tasks AND which
  // side of the kind-split a convergence failure takes. Original subtasks carry
  // no marker (=> depth 0); a filed side-task carries `depth: d`. Its origin
  // marker is threaded into the report's task -> commit -> origin map.
  const { depth, origin } = resolveMarker(item.taskId, item.description)
  log(`Processing ${item.taskId} (depth ${depth}): ${item.title || '(untitled)'}`)

  phase('Implement')
  const impl = await agent(implementPrompt(item, packPath), { label: `impl:${item.taskId}`, schema: IMPLEMENT_SCHEMA })
  if (!impl || !impl.green) {
    // `tdd` never reached green — a convergence failure (throws Halt / SkipItem).
    await failConvergence(item, depth, 'tdd never reached green targeted tests', (impl && impl.summary) || '')
  }

  const carriedDeferred = await reviewPhaseA(item, depth)
  const carriedDelayed = await refactorPhaseB(item, carriedDeferred)
  await fileSideTasks(item, depth, carriedDelayed)
  await verifyStep(item, depth)
  await statusAndCommit(item, depth, origin)
}

while (processed.length < GUARD_MAX) {
  phase('Pick')
  // Exclude everything already attempted this run so a dropped side-task (which
  // `failConvergence` resets back to `pending`) is never re-picked — that would
  // otherwise trip the re-pick guard below and abandon the remaining queue.
  const raw = await agent(pickPrompt(packPath, Array.from(seen)), { label: 'pick', schema: PICK_SCHEMA })
  const pick = normalizePick(raw)
  // `normalizePick` guarantees done ⇔ items empty, so `pick.done` alone covers
  // the terminal "nothing to do" case.
  if (pick.done) {
    log('No pending work items remain.')
    break
  }
  // Self-heal an over-serve: the pick agent moved more members to `in-progress`
  // than the hard cap allows, so `normalizePick` truncated the batch and surfaced
  // the dropped ids. Reset them to `pending` (only an agent can write the tracker)
  // so they re-enter the queue on a later pick instead of being orphaned
  // in-progress. They are NOT recorded in `seen` — they were never attempted.
  // This runs before the repeat-guard below on purpose: over-served ids must
  // return to `pending` regardless of whether this run continues or halts, so the
  // tracker is left clean for the next invocation either way.
  if (pick.overserved && pick.overserved.length) {
    await agent(resetToPendingPrompt(packPath, pick.overserved, pick.kind), {
      label: 'reset-overserved',
      schema: RESET_TO_PENDING_SCHEMA,
    })
  }
  // Backstop: the pick agent ignored the exclusion list and re-served an
  // already-attempted id. Stop rather than risk a loop. Every returned item is
  // checked so a group cannot smuggle a repeat past the guard.
  const repeat = firstRepeat(pick.items, seen)
  if (repeat) {
    log(`Re-picked ${repeat.taskId} — stopping to avoid a loop (already attempted this run).`)
    break
  }
  recordSeen(pick.items, seen)

  try {
    // A feature pick carries one item; a refactor pick batches 1–5. The loop
    // body iterates uniformly so a one-element group is just the degenerate case.
    for (const item of pick.items) await processItem(item)
  } catch (e) {
    // The kind-split surfaces here exactly once: SkipItem abandons this work item
    // and continues; Halt ends the run with the report.
    if (e instanceof SkipItem) continue
    if (e instanceof Halt) return report(setup, packPath, processed, refactorOutcomes(), e.failure)
    throw e
  }
}

return report(setup, packPath, processed, refactorOutcomes(), null)

// Bundle the refactor-phase collections threaded into the report.
function refactorOutcomes() {
  return {
    deferredFindings,
    delayedFindings,
    outOfScopeFindings,
    droppedRefactors,
    filedSideTasks,
    residualFindings,
    capSuppressed,
    droppedSideTasks,
    escalations,
  }
}

// ---- report --------------------------------------------------------------
function report(setup, packPath, processed, refactor, failure) {
  const r = refactor || {}
  const deferredFindings = r.deferredFindings || []
  const delayedFindings = r.delayedFindings || []
  const outOfScopeFindings = r.outOfScopeFindings || []
  const droppedRefactors = r.droppedRefactors || []
  const filedSideTasks = r.filedSideTasks || []
  const residualFindings = r.residualFindings || []
  const capSuppressed = r.capSuppressed || []
  const droppedSideTasks = r.droppedSideTasks || []
  const escalations = r.escalations || []
  const lines = []
  // Emit a titled, count-suffixed section of `  - <fmt(item)>` rows, or nothing
  // when the collection is empty.
  const section = (title, items, fmt) => {
    if (!items || !items.length) return
    lines.push('', `${title} (${items.length}):`)
    for (const it of items) lines.push(`  - ${fmt(it)}`)
  }
  // The shared `title @ location` core of a finding, so the detail sections and
  // the escalation surface below format a finding the same way (no drift).
  const findingCore = (f) => `${(f || {}).title || '(untitled)'} @ ${(f || {}).location || '?'}`
  // A finding row keyed by task — the shared shape for most refactor collections.
  const findingRow = (d) => `[${d.taskId}] ${findingCore(d.finding)} (${(d.finding || {}).severity || '?'})`

  lines.push(`grind-story — story ${storyId}`)
  lines.push(`branch: ${setup.branch} (base ${setup.baseRef})`)
  lines.push(`context pack: ${packPath}`)
  if (processed.length === 0) {
    lines.push('', 'No work items were committed.')
  } else {
    lines.push('', `Committed ${processed.length} work item(s) (task → commit-sha → origin; each → in-review, tox green):`)
    for (const p of processed) {
      const sha = (p.sha || '').slice(0, 12)
      const subject = (p.message || '').split('\n')[0]
      // Original subtasks (depth 0, no marker) carry no origin; a side-task shows
      // the originating task + finding from its depth marker.
      const originTag = p.origin ? ` ← origin ${p.origin}` : ' (origin: original subtask)'
      lines.push(`  - ${p.taskId} "${p.title || ''}" → ${sha}${originTag} : ${subject}`)
    }
  }
  section('Dropped side-tasks (could not converge; git reset --hard-discarded, run continued)', droppedSideTasks,
    (d) => `${d.taskId} (depth ${d.depth}) "${d.title || ''}" — ${d.reason || '(no reason given)'}`)
  section('Deferred-to-refactor findings carried into Phase B', deferredFindings, findingRow)
  section('Delayed refactor findings collected for side-task filing', delayedFindings, findingRow)
  section('Refactor side-tasks filed', filedSideTasks,
    (s) => `${s.childTaskId} (depth ${s.depth}) "${s.title || ''}" ← origin ${s.originTaskId}`)
  section('Residual refactor findings at maxDepth (not filed)', residualFindings,
    (d) => `[${d.taskId} depth ${d.depth}] ${findingCore(d.finding)} (${(d.finding || {}).severity || '?'})`)
  section(`Side-task findings suppressed by the total cap of ${totalSideTaskCap}`, capSuppressed, findingRow)
  section('Out-of-scope refactor findings (reported only, not filed)', outOfScopeFindings, findingRow)
  section('Dropped refactorings (could not stay green)', droppedRefactors,
    (d) => `[${d.taskId}] ${d.finding || '(untitled)'} — ${d.reason || '(no reason given)'}`)
  // Escalations — the human-review surface that replaces the dropped interactive
  // gates: the halting original subtask, any fix-now open at the review cap, residual findings
  // stranded at maxDepth, and side-task findings suppressed by the total cap.
  const escalationLines = []
  if (failure) {
    escalationLines.push(`  - HALT: ${failure.taskId} "${failure.title || ''}" — ${failure.reason}`)
  }
  for (const e of escalations) {
    escalationLines.push(`  - fix-now at cap: ${e.taskId} (depth ${e.depth}) — ${e.detail || e.count + ' open fix-now finding(s)'}`)
  }
  for (const d of residualFindings) {
    escalationLines.push(`  - residual at maxDepth: [${d.taskId} depth ${d.depth}] ${findingCore(d.finding)}`)
  }
  for (const d of capSuppressed) {
    escalationLines.push(`  - cap-suppressed side-task: [${d.taskId}] ${findingCore(d.finding)}`)
  }
  if (escalationLines.length) {
    lines.push('')
    lines.push(`Escalations for human review (${escalationLines.length}):`)
    lines.push(...escalationLines)
  }
  if (failure) {
    lines.push('')
    lines.push(`HALTED on ${failure.taskId} "${failure.title || ''}": ${failure.reason}`)
    lines.push('Working tree left dirty for inspection; prior commits preserved.')
    if (failure.failures) {
      lines.push('--- last failure output ---')
      lines.push(failure.failures)
    }
  } else {
    lines.push('')
    lines.push('Run complete — no pending work items remain.')
  }
  return lines.join('\n')
}
