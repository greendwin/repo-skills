export const meta = {
  name: 'grind-story',
  description: 'Autonomously drive a story\'s pending subtasks: branch, context pack, then per subtask implement → tox-gate → commit → in-review',
  whenToUse: 'Run an unattended implement loop over one story\'s pending subtasks on a dedicated grind branch.',
  phases: [
    { title: 'Setup', detail: 'create grind/<story> branch from HEAD, capture base ref' },
    { title: 'Bootstrap', detail: 'build the shared context pack once per run' },
    { title: 'Pick', detail: 'list the story subtree, take the next pending work item, set it in-progress' },
    { title: 'Implement', detail: 'tdd implement the work item to green targeted tests' },
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

const processed = []
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
    return report(setup, packPath, processed, {
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
    return report(setup, packPath, processed, {
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

return report(setup, packPath, processed, null)

// ---- report --------------------------------------------------------------
function report(setup, packPath, processed, failure) {
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
