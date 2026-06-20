export const meta = {
  name: 'grind-story',
  description: 'Autonomously drive a story\'s pending subtasks: branch, context pack, then per subtask implement → tox-gate → commit → in-review',
  whenToUse: 'Run an unattended implement loop over one story\'s pending subtasks on a dedicated grind branch.',
  phases: [
    { title: 'Setup', detail: 'create grind/<story> branch from HEAD, capture base ref' },
    { title: 'Bootstrap', detail: 'build the shared context pack once per run' },
    { title: 'Pick', detail: 'list the story subtree, take the next pending work item, set it in-progress' },
    { title: 'Implement', detail: 'tdd implement the work item to green targeted tests' },
    { title: 'Review-A', detail: 'code-reviewer lenses in parallel → triage → tdd fixes fix-now, until clean (cap 5)' },
    { title: 'Refactor-B', detail: 'refactor-reviewer lenses in parallel → apply-biased triage → tdd applies apply-now behavior-preservingly, until dry (cap 5)' },
    { title: 'Verify', detail: 'uv run tox (all envs) green gate, with bounded fix-reconverge' },
    { title: 'Commit', detail: 'stage + one commit-summary-style commit per work item' },
    { title: 'Status', detail: 'move the work item to in-review (never done)' },
  ],
}

// ---- story id ------------------------------------------------------------
const storyId = typeof args === 'string' ? args.trim() : String(args || '').trim()
if (!storyId) {
  return 'grind-story: no story id given. Invoke as Workflow({name:"grind-story", args:"<story-id>"}).'
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

const PICK_SCHEMA = {
  type: 'object',
  properties: {
    done: { type: 'boolean', description: 'true when no pending work item remains' },
    taskId: { type: 'string', description: 'id of the chosen work item (omit when done)' },
    title: { type: 'string', description: 'title of the chosen work item' },
    isStory: { type: 'boolean', description: 'true when the work item is the story task itself' },
  },
  required: ['done'],
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

const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    lens: { type: 'string', description: 'the lens that produced these findings' },
    findings: {
      type: 'array',
      items: {
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
      },
    },
  },
  required: ['lens', 'findings'],
}

const TRIAGE_SCHEMA = {
  type: 'object',
  properties: {
    buckets: {
      type: 'object',
      properties: {
        'fix-now': { type: 'array', items: { type: 'object' } },
        'deferred-to-refactor': { type: 'array', items: { type: 'object' } },
        'out-of-scope': { type: 'array', items: { type: 'object' } },
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
        'apply-now': { type: 'array', items: { type: 'object' } },
        'delayed': { type: 'array', items: { type: 'object' } },
        'out-of-scope': { type: 'array', items: { type: 'object' } },
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

const pickPrompt = (packPath) => `You are the queue step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs and status roles).

Select the next work item and move it to in-progress:
1. Using the read-task and list-tasks verbs from the pack, load story ${storyId} and enumerate its subtasks at any depth.
2. Choose the first subtask whose status is \`pending\` (natural order).
3. Degenerate case: if story ${storyId} has NO subtasks at all, the work item is the story task ${storyId} itself — but only if its own status is \`pending\`.
4. If no pending work item exists (no pending subtask, and either the story has subtasks or the story itself is not pending), nothing is left.

If you selected a work item:
- Move it to the \`in-progress\` status role using the set-status verb from the pack.
- Return done=false, taskId=<id>, title=<its title>, isStory=<true only if it is the story task itself>.

If nothing is left, return done=true.

Only query and set status — do not implement anything, do not edit files.`

const implementPrompt = (pick, packPath) => `You are the implementation step of an autonomous grind-story workflow, running the \`tdd\` skill in execute mode.

Read the context pack first: ${packPath}.

Work item: task ${pick.taskId}${pick.isStory ? ' (this IS the story task itself — it has no subtasks)' : ''}. Load it via the read-task verb from the pack${pick.isStory ? '.' : `, and read parent story ${storyId} for the decisions/constraints that scope it.`}

The plan is PRE-APPROVED. Use \`tdd\`'s "skip review" path: skip planning/approval, go straight to tracer-bullet red→green cycles. Implement the task's acceptance criteria with behavior-level tests through the public interface. Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments).

Contract: return only when your targeted tests are GREEN.

Boundaries — do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\` (a later step gates that). Only write the source/test files this task needs.

Report what you implemented and which files you created or changed.`

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

Staging:
1. \`git add -u\` to stage tracked modifications/deletions.
2. \`git status --porcelain\` for untracked (\`??\`) entries. For each:
   - DENYLIST — never stage, never prompt: \`.env\`, \`.env.*\`, \`*.key\`, \`*.pem\`, \`*.p12\`, \`*.pfx\`, \`*.secret\`, \`credentials.json\`, \`secrets.yaml\`, \`.netrc\`, \`.npmrc\`, \`.venv/\`, \`venv/\`, \`node_modules/\`, \`__pycache__/\`, \`*.sqlite\`, \`*.db\`.
   - SUSPICIOUS — never stage, never prompt: editor temps (\`*.swp\`, \`*.swo\`, \`*~\`), backups (\`*.bak\`, \`*.orig\`), OS artifacts (\`.DS_Store\`, \`Thumbs.db\`), or anything common practice would not check in.
   - Otherwise — clearly project source/tests/docs created for task ${pick.taskId}: stage it.
   Collect every untracked path you skip into a list to return.
3. Compose the message with \`commit-summary\` rules: calibrate prefix/bullet style from \`git log -n 10\`, pick the right prefix, imperative subject ≤72 chars, body only when warranted, correct backtick usage. Do NOT put any task id (e.g. ${pick.taskId}) in the message — match the repo log style. Never append \`Co-Authored-By\` or \`Generated with Claude Code\` footers.
4. Commit via \`git commit -F <tmpfile>\` (write the raw message to a temp file, then remove it).

Return the resulting commit sha (\`git rev-parse HEAD\`), the exact message you used, and the list of skipped untracked files.`

const statusPrompt = (pick, packPath) => `You are the status step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}.

Move task ${pick.taskId} to the \`in-review\` status role using the set-status verb resolved in the pack. Never move it to \`done\`. Do nothing else, and confirm the new status.`

// ---- orchestration -------------------------------------------------------
const CAP = 5
const GUARD_MAX = 100

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
const reviewLenses = (roster && Array.isArray(roster.lenses)) ? roster.lenses.filter((l) => typeof l === 'string' && l.trim()) : []
if (reviewLenses.length === 0) {
  log('Phase A skipped for the run: the code-reviewer roster resolved empty.')
}

// Resolve the refactor-reviewer roster once too — it likewise does not change
// per subtask. An empty roster means Phase B is skipped for the whole run.
const refactorRoster = await agent(refactorRosterPrompt(packPath), { label: 'roster:refactor-reviewer', schema: ROSTER_SCHEMA })
const refactorLenses = (refactorRoster && Array.isArray(refactorRoster.lenses)) ? refactorRoster.lenses.filter((l) => typeof l === 'string' && l.trim()) : []
if (refactorLenses.length === 0) {
  log('Phase B skipped for the run: the refactor-reviewer roster resolved empty.')
}

const processed = []
const deferredFindings = []
const delayedFindings = []
const outOfScopeFindings = []
const droppedRefactors = []
const seen = new Set()

while (processed.length < GUARD_MAX) {
  phase('Pick')
  const pick = await agent(pickPrompt(packPath), { label: 'pick', schema: PICK_SCHEMA })
  if (!pick || pick.done || !pick.taskId) {
    log('No pending work items remain.')
    break
  }
  if (seen.has(pick.taskId)) {
    log(`Re-picked ${pick.taskId} — stopping to avoid a loop (its status did not advance).`)
    break
  }
  seen.add(pick.taskId)
  log(`Processing ${pick.taskId}: ${pick.title || '(untitled)'}`)

  phase('Implement')
  await agent(implementPrompt(pick, packPath), { label: `impl:${pick.taskId}` })

  // The `deferred-to-refactor` findings raised for THIS subtask in Phase A,
  // merged into Phase B's refactor pool below.
  const carriedDeferred = []

  // Phase A — code-reviewer lenses → triage → tdd fixes fix-now, re-converging
  // until no fix-now remains or the round cap is hit. Skipped on an empty roster.
  if (reviewLenses.length > 0) {
    phase('Review-A')
    let openFixNow = []
    for (let round = 1; round <= CAP; round++) {
      const lensRuns = reviewLenses.map((lens) =>
        agent(lensPrompt(lens, packPath, setup.baseRef), { label: `lens:${lens}:${round}`, schema: FINDINGS_SCHEMA }),
      )
      const lensResults = await parallel(lensRuns)
      const findings = []
      for (const r of lensResults) {
        // A lens that died or returned null is filtered out; the round continues.
        if (r && Array.isArray(r.findings)) findings.push(...r.findings)
      }
      if (findings.length === 0) {
        openFixNow = []
        log(`Review-A round ${round}/${CAP} for ${pick.taskId}: lenses raised no findings.`)
        break
      }

      const triage = await agent(triagePrompt(packPath, JSON.stringify(findings, null, 2)), {
        label: `triage-A:${round}`,
        schema: TRIAGE_SCHEMA,
      })
      const buckets = (triage && triage.buckets) || {}
      const fixNow = Array.isArray(buckets['fix-now']) ? buckets['fix-now'] : []
      const deferred = Array.isArray(buckets['deferred-to-refactor']) ? buckets['deferred-to-refactor'] : []
      for (const f of deferred) {
        deferredFindings.push({ taskId: pick.taskId, finding: f })
        carriedDeferred.push(f)
      }

      if (fixNow.length === 0) {
        openFixNow = []
        log(`Review-A round ${round}/${CAP} for ${pick.taskId}: no fix-now findings; ${deferred.length} carried to Phase B.`)
        break
      }
      openFixNow = fixNow
      log(`Review-A round ${round}/${CAP} for ${pick.taskId}: ${fixNow.length} fix-now finding(s); routing to a tdd fix agent.`)
      if (round === CAP) break
      await agent(reviewFixPrompt(pick, packPath, JSON.stringify(fixNow, null, 2)), { label: `fix-A:${round}` })
    }
    if (openFixNow.length > 0) {
      // Cap reached with fix-now still open. Record it (Slice 5 owns hard
      // escalation); do not commit red — the green gate still has to pass.
      log(`Review-A cap reached for ${pick.taskId} with ${openFixNow.length} fix-now finding(s) still open — recorded for escalation.`)
    }
  }

  // Phase B — refactor-reviewer lenses (merged with Phase A's deferred findings)
  // → apply-biased triage → tdd applies apply-now behavior-preservingly, looping
  // until no new apply-now or the round cap is hit. Skipped on an empty roster.
  if (refactorLenses.length > 0) {
    phase('Refactor-B')
    for (let round = 1; round <= CAP; round++) {
      const lensRuns = refactorLenses.map((lens) =>
        agent(refactorLensPrompt(lens, packPath, setup.baseRef), { label: `refactor-lens:${lens}:${round}`, schema: FINDINGS_SCHEMA }),
      )
      const lensResults = await parallel(lensRuns)
      const findings = []
      for (const r of lensResults) {
        // A lens that died or returned null is filtered out; the round continues.
        if (r && Array.isArray(r.findings)) findings.push(...r.findings)
      }
      // Only the first round merges the Phase A deferred findings — later rounds
      // re-review the now-refactored tree fresh so they cannot re-surface stale
      // findings already applied or routed.
      if (round === 1) findings.push(...carriedDeferred)

      if (findings.length === 0) {
        log(`Refactor-B round ${round}/${CAP} for ${pick.taskId}: lenses raised no findings — loop dry.`)
        break
      }

      const triage = await agent(refactorTriagePrompt(packPath, JSON.stringify(findings, null, 2)), {
        label: `triage-B:${round}`,
        schema: REFACTOR_TRIAGE_SCHEMA,
      })
      const buckets = (triage && triage.buckets) || {}
      const applyNow = Array.isArray(buckets['apply-now']) ? buckets['apply-now'] : []
      const delayed = Array.isArray(buckets['delayed']) ? buckets['delayed'] : []
      const outOfScope = Array.isArray(buckets['out-of-scope']) ? buckets['out-of-scope'] : []
      // `delayed` seeds Slice 4's side-tasks; `out-of-scope` is reported only.
      for (const f of delayed) delayedFindings.push({ taskId: pick.taskId, finding: f })
      for (const f of outOfScope) outOfScopeFindings.push({ taskId: pick.taskId, finding: f })

      if (applyNow.length === 0) {
        log(`Refactor-B round ${round}/${CAP} for ${pick.taskId}: no apply-now; ${delayed.length} delayed, ${outOfScope.length} out-of-scope — loop dry.`)
        break
      }
      log(`Refactor-B round ${round}/${CAP} for ${pick.taskId}: ${applyNow.length} apply-now refactoring(s); routing to a tdd apply agent.`)
      if (round === CAP) {
        log(`Refactor-B cap reached for ${pick.taskId} with apply-now work still surfacing — stopping the refactor loop.`)
        break
      }
      const applied = await agent(applyPrompt(pick, packPath, JSON.stringify(applyNow, null, 2)), {
        label: `apply-B:${round}`,
        schema: APPLY_SCHEMA,
      })
      const results = (applied && Array.isArray(applied.results)) ? applied.results : []
      for (const res of results) {
        if (res && res.outcome === 'dropped') {
          droppedRefactors.push({ taskId: pick.taskId, finding: res.finding, reason: res.reason || '(no reason given)' })
          log(`Refactor dropped for ${pick.taskId}: "${res.finding}" — ${res.reason || '(no reason given)'}`)
        }
      }
    }
  }

  phase('Verify')
  let green = false
  let lastFailures = ''
  for (let round = 1; round <= CAP; round++) {
    const v = await agent(verifyPrompt(packPath), { label: `tox:${round}`, schema: VERIFY_SCHEMA })
    if (v && v.green) { green = true; break }
    lastFailures = (v && v.failures) || '(no failure detail captured)'
    log(`tox red (round ${round}/${CAP}) for ${pick.taskId}; routing failures to a fix agent.`)
    if (round === CAP) break
    await agent(fixPrompt(pick, packPath, lastFailures), { label: `fix:${round}` })
  }
  if (!green) {
    log(`HARD FAILURE: ${pick.taskId} could not reach green tox after ${CAP} rounds — stopping the run.`)
    return report(setup, packPath, processed, refactorOutcomes(), {
      taskId: pick.taskId,
      title: pick.title,
      reason: `uv run tox still red after ${CAP} fix rounds`,
      failures: lastFailures,
    })
  }

  phase('Commit')
  const commit = await agent(commitPrompt(pick, packPath), { label: `commit:${pick.taskId}`, schema: COMMIT_SCHEMA })
  if (!commit) {
    log(`HARD FAILURE: ${pick.taskId} reached green but the commit step failed — stopping the run.`)
    return report(setup, packPath, processed, refactorOutcomes(), {
      taskId: pick.taskId,
      title: pick.title,
      reason: 'commit step returned no result',
    })
  }
  if (commit.skipped && commit.skipped.length) {
    log(`Skipped untracked files (not staged): ${commit.skipped.join(', ')}`)
  }

  phase('Status')
  await agent(statusPrompt(pick, packPath), { label: `review:${pick.taskId}` })

  processed.push({ taskId: pick.taskId, title: pick.title, sha: commit.sha, message: commit.message })
}

return report(setup, packPath, processed, refactorOutcomes(), null)

// Bundle the refactor-phase collections threaded into the report.
function refactorOutcomes() {
  return { deferredFindings, delayedFindings, outOfScopeFindings, droppedRefactors }
}

// ---- report --------------------------------------------------------------
function report(setup, packPath, processed, refactor, failure) {
  const deferredFindings = (refactor && refactor.deferredFindings) || []
  const delayedFindings = (refactor && refactor.delayedFindings) || []
  const outOfScopeFindings = (refactor && refactor.outOfScopeFindings) || []
  const droppedRefactors = (refactor && refactor.droppedRefactors) || []
  const lines = []
  lines.push(`grind-story — story ${storyId}`)
  lines.push(`branch: ${setup.branch} (base ${setup.baseRef})`)
  lines.push(`context pack: ${packPath}`)
  lines.push('')
  if (processed.length === 0) {
    lines.push('No work items were committed.')
  } else {
    lines.push(`Committed ${processed.length} work item(s) (each → in-review, tox green):`)
    for (const p of processed) {
      const sha = (p.sha || '').slice(0, 12)
      const subject = (p.message || '').split('\n')[0]
      lines.push(`  - ${p.taskId} "${p.title || ''}" → ${sha} : ${subject}`)
    }
  }
  if (deferredFindings && deferredFindings.length) {
    lines.push('')
    lines.push(`Deferred-to-refactor findings carried into Phase B (${deferredFindings.length}):`)
    for (const d of deferredFindings) {
      const f = d.finding || {}
      lines.push(`  - [${d.taskId}] ${f.title || '(untitled)'} @ ${f.location || '?'} (${f.severity || '?'})`)
    }
  }
  if (delayedFindings && delayedFindings.length) {
    lines.push('')
    lines.push(`Delayed refactor findings collected for side-task filing (${delayedFindings.length}):`)
    for (const d of delayedFindings) {
      const f = d.finding || {}
      lines.push(`  - [${d.taskId}] ${f.title || '(untitled)'} @ ${f.location || '?'} (${f.severity || '?'})`)
    }
  }
  if (outOfScopeFindings && outOfScopeFindings.length) {
    lines.push('')
    lines.push(`Out-of-scope refactor findings (reported only, not filed) (${outOfScopeFindings.length}):`)
    for (const d of outOfScopeFindings) {
      const f = d.finding || {}
      lines.push(`  - [${d.taskId}] ${f.title || '(untitled)'} @ ${f.location || '?'} (${f.severity || '?'})`)
    }
  }
  if (droppedRefactors && droppedRefactors.length) {
    lines.push('')
    lines.push(`Dropped refactorings (could not stay green) (${droppedRefactors.length}):`)
    for (const d of droppedRefactors) {
      lines.push(`  - [${d.taskId}] ${d.finding || '(untitled)'} — ${d.reason || '(no reason given)'}`)
    }
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
