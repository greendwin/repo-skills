// GENERATED from src/index.ts by scripts/build.mjs — bare Workflow function body (not a standalone module); run `npm run build`, do not hand-edit.
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

// src/schemas/pick.ts
var PICK_ITEM = {
  type: "object",
  properties: {
    taskId: { type: "string", description: "id of the chosen work item" },
    title: { type: "string", description: "title of the chosen work item" },
    isStory: { type: "boolean", description: "true when the work item is the story task itself" },
    description: {
      type: "string",
      description: "the chosen work item's verbatim description body (used to parse its depth marker)"
    }
  },
  required: ["taskId"]
};
var PICK_SCHEMA = {
  type: "object",
  properties: {
    done: { type: "boolean", description: "true when no pending work item remains" },
    kind: {
      type: "string",
      enum: ["refactor", "feature"],
      description: "`refactor` when the items are marker-bearing side-tasks; `feature` for an original depth-0 subtask"
    },
    items: {
      type: "array",
      description: "the chosen work items \u2014 a feature pick carries exactly one subtask; a refactor pick batches 1\u20135 small, local, non-overlapping side-tasks (hard cap 5)",
      items: PICK_ITEM
    }
  },
  required: ["done"]
};

// src/domain/raw.ts
function isRecord(x) {
  return typeof x === "object" && x !== null;
}

// src/subagent.ts
var identityParse = (raw) => raw;
function defineSubagent(spec) {
  const parse9 = spec.parse ?? identityParse;
  return {
    name: spec.name,
    run: async (args2) => {
      const label = typeof spec.label === "function" ? spec.label(args2) : spec.label;
      return parse9(await agent(spec.prompt(args2), { label, schema: spec.schema }));
    }
  };
}

// src/invocations/pick.ts
var pickPrompt = ({ storyId, packPath, excludeIds }) => `You are the queue step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs and status roles).
${excludeIds.length ? `
ALREADY-ATTEMPTED this run \u2014 NEVER select any of these ids even if their status reads \`pending\` (a dropped side-task is reset back to pending but must not be re-picked): ${excludeIds.join(", ")}.
` : ""}
Select the next work item and move it to in-progress:
1. Using the read-task and list-tasks verbs from the pack, load story ${storyId} and enumerate its subtasks at any depth.
2. Among the eligible subtasks \u2014 status \`pending\` AND id NOT in the already-attempted list above \u2014 classify each by its description:
   - A REFACTOR task carries a \`## Refactor side-task\` marker block in its description.
   - A FEATURE task is an original subtask with NO such marker block.
3. PREFER refactor tasks: if any eligible refactor task exists, the pick is a REFACTOR pick (kind="refactor"); otherwise it is a FEATURE pick (kind="feature"). This drains refactor side-tasks ahead of feature work so feature work lands on already-refactored code.
4. Build the \`items\` group for the chosen kind:
   - FEATURE pick: choose the FIRST eligible feature subtask (natural order) \u2014 EXACTLY ONE item. Feature subtasks are tracer-bullet units with distinct acceptance criteria and must NEVER be batched; never mix a feature task into a refactor group.
   - REFACTOR pick: starting from the first eligible refactor task (natural order), BATCH a group of small, local, non-overlapping refactor side-tasks to land in one pass. Judge feasible work size from each candidate's description (title/location/severity/suggested-fix/rationale): prefer same-area, non-conflicting changes; STOP adding once the combined change looks too big to land+review cleanly in one pass. The group is 1\u20135 members \u2014 a HARD cap of 5, never more, even when more refactors are eligible; fewer than 5 eligible means a smaller group (1\u20134); a single eligible refactor is a valid group of one. Every member must be an eligible refactor task (a \`## Refactor side-task\` marker block) and NOT in the already-attempted list.
5. Degenerate case: if story ${storyId} has NO subtasks at all, the work item is the story task ${storyId} itself with kind="feature" (a single-item group) \u2014 but only if its own status is \`pending\` and it is not in the already-attempted list.
6. If no pending work item exists (no eligible pending subtask, and either the story has subtasks or the story itself is not eligible), nothing is left.

If you selected a work item:
- Apply the HARD cap of 5 YOURSELF before returning: a REFACTOR group is at most 5 members and a FEATURE group is exactly 1 \u2014 never return more. Decide the exact group first, then act on ONLY those members.
- Move EXACTLY the members you return \u2014 and no others \u2014 to the \`in-progress\` status role using the set-status verb from the pack BEFORE returning, so a mid-run crash leaves consistent tracker state. Do NOT set \`in-progress\` on any task you are not returning; over-serving (moving more than 5 to in-progress, or moving any you then omit) strands tasks in a non-terminal status.
- Return done=false, kind=<"refactor" or "feature">, and items=[ one object per member {taskId:<id>, title:<its title>, isStory:<true only if it is the story task itself>, description:<the work item's verbatim description body, exactly as stored, so the orchestrator can parse any depth marker>} ]. A FEATURE pick carries EXACTLY ONE item; a REFACTOR pick carries 1\u20135 items (hard cap 5).

If nothing is left, return done=true.

Only query and set status \u2014 do not implement anything, do not edit files.`;
function parse(raw) {
  const FEATURE_GROUP_CAP = 1;
  const REFACTOR_GROUP_CAP = 5;
  const normalizeKind = (k) => k === "refactor" ? "refactor" : "feature";
  const donePick = (stalled) => ({
    done: true,
    kind: normalizeKind(),
    items: [],
    ...stalled ? { stalled: true } : {}
  });
  if (!isRecord(raw) || raw.done) return donePick();
  const rawItems = Array.isArray(raw.items) ? raw.items : [];
  const items = rawItems.filter((it) => isRecord(it) && typeof it.taskId === "string" && it.taskId.length > 0).map((it) => ({
    taskId: it.taskId,
    title: typeof it.title === "string" ? it.title : "",
    description: typeof it.description === "string" ? it.description : "",
    isStory: it.isStory === true
  }));
  if (items.length === 0) return donePick(true);
  const kind = normalizeKind(raw.kind);
  const cap = kind === "refactor" ? REFACTOR_GROUP_CAP : FEATURE_GROUP_CAP;
  const overserved = items.slice(cap).map((it) => it.taskId);
  return { done: false, kind, cap, items: items.slice(0, cap), overserved };
}
function formatOverserveWarning(pick2) {
  const overserved = pick2.overserved ?? [];
  const served = pick2.items.length + overserved.length;
  return `Pick agent over-served a ${pick2.kind} group: ${served} well-formed members for a hard cap of ${pick2.cap}. Truncating and resetting the dropped ${overserved.length} (${overserved.join(", ")}) back to pending so they are not stranded in-progress.`;
}
var pick = defineSubagent({
  name: "pick",
  label: "pick",
  schema: PICK_SCHEMA,
  prompt: pickPrompt,
  parse
});

// src/schemas/setup.ts
var BRANCH_SCHEMA = {
  type: "object",
  properties: {
    branch: { type: "string", description: "the branch now checked out" },
    baseRef: { type: "string", description: "HEAD sha the branch was created from" }
  },
  required: ["branch", "baseRef"]
};
var PACK_SCHEMA = {
  type: "object",
  properties: {
    packPath: { type: "string", description: "absolute path to the written context pack" },
    digest: { type: "string", description: "short summary of what the pack contains" }
  },
  required: ["packPath"]
};

// src/invocations/branch.ts
var branchPrompt = ({ storyId }) => `You are the setup step of an autonomous grind-story workflow for story ${storyId}.

Create the working branch and report the base ref. Use shell (Bash):
1. Capture the current HEAD sha: \`git rev-parse HEAD\` \u2014 this is the base ref every later agent diffs against.
2. Create and switch to \`grind/${storyId}\` from the current HEAD via \`git switch -c grind/${storyId}\`. If that branch already exists, just \`git switch grind/${storyId}\` instead of failing.
3. Confirm with \`git rev-parse --abbrev-ref HEAD\`.

Do not commit and do not modify any files. Return the branch name and the base ref sha.`;
var branch = defineSubagent({
  name: "branch",
  label: "branch",
  schema: BRANCH_SCHEMA,
  prompt: branchPrompt,
  parse: identityParse
});

// src/invocations/bootstrap.ts
var bootstrapPrompt = ({ storyId }) => `You are the bootstrap step of an autonomous grind-story workflow for story ${storyId}.

Build ONE shared context pack that every downstream agent reads first. Read these repo files and fold their RESOLVED prose into the pack \u2014 never make a downstream agent re-read the source configs, and never hardcode rosters/verbs elsewhere:
- \`docs/agents/task-tracker.md\` \u2014 the task-tracker verbs (read-task, list-tasks, set-status) and the status-role \u2192 native-status table. Spell out the EXACT MCP tool call a downstream agent must make for read-task, list-tasks, and for set-status to each of pending / in-progress / in-review.
- \`docs/agents/dev-loop.md\` \u2014 the code-reviewer and refactor-reviewer lens rosters (not exercised in this slice; include a brief summary for later slices).
- \`CLAUDE.md\` \u2014 development rules: \`uv run tox\` (all envs) is the gate and pre-existing failures must be fixed too; no task ids in code comments; the Python guide (no \`type: ignore\`, \`monkeypatch\` not \`unittest.mock.patch\`, no inline imports, \`assert_invoke\` not \`CliRunner\`).
- \`CONTEXT.md\` \u2014 the domain glossary / terminology.
- Any ADRs under \`docs/adr/\` \u2014 list them and one-line each so downstream agents respect them.

Write the pack to \`/tmp/grind-story/${storyId}.md\` (run \`mkdir -p /tmp/grind-story\` first). This path is OUTSIDE the working tree, so it is never committed and never pollutes the diff. A fresh agent given only this path must be able to resolve the task-tracker verbs/status-roles and the project conventions without opening the source configs.

Do not modify any tracked files. Return the pack path and a short digest.`;
var bootstrap = defineSubagent({
  name: "bootstrap",
  label: "context-pack",
  schema: PACK_SCHEMA,
  prompt: bootstrapPrompt,
  parse: identityParse
});

// src/schemas/roster.ts
var ROSTER_SCHEMA = {
  type: "object",
  properties: {
    lenses: {
      type: "array",
      description: "the code-reviewer lens names in roster order (empty when the roster is empty)",
      items: { type: "string" }
    }
  },
  required: ["lenses"]
};

// src/invocations/roster.ts
var rosterPrompt = ({ role, examples }) => ({ packPath }) => `You are the roster-resolution step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}. It resolves this repo's \`${role}\` lens roster (do not re-open the source configs).

Report the \`${role}\` roster as an ordered list of lens names exactly as the pack names them (e.g. ${examples}). If the pack resolves the \`${role}\` roster as EMPTY, return an empty list.

Do not review anything and do not edit files. Return only the lens names.`;
function parse2(raw) {
  const rawLenses = isRecord(raw) && Array.isArray(raw.lenses) ? raw.lenses : [];
  const lenses = rawLenses.filter((l) => typeof l === "string" && l.trim().length > 0);
  return { lenses };
}
var roster = defineSubagent({
  name: "roster",
  label: "roster:code-reviewer",
  schema: ROSTER_SCHEMA,
  prompt: rosterPrompt({ role: "code-reviewer", examples: "general, tests, performance" }),
  parse: parse2
});
var refactorRoster = defineSubagent({
  name: "refactor-roster",
  label: "roster:refactor-reviewer",
  schema: ROSTER_SCHEMA,
  prompt: rosterPrompt({ role: "refactor-reviewer", examples: "duplication, thermo-nuclear" }),
  parse: parse2
});

// src/schemas/reset.ts
var RESET_SCHEMA = {
  type: "object",
  properties: {
    clean: { type: "boolean", description: "true when the working tree is clean after the reset" },
    head: { type: "string", description: "sha HEAD points at after the reset (the preserved prior commit)" }
  },
  required: ["clean"]
};
var RESET_TO_PENDING_SCHEMA = {
  type: "object",
  properties: {
    reset: {
      type: "array",
      items: { type: "string", description: "a task id moved back to pending" },
      description: "the over-served ids reset to pending"
    }
  },
  required: ["reset"]
};

// src/invocations/reset-to-pending.ts
var resetToPendingPrompt = ({ packPath, ids, kind }) => `You are the over-serve cleanup step of an autonomous grind-story workflow.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs and status roles).

The pick agent over-served a ${kind} group: it moved more members to \`in-progress\` than that group's hard cap allows, so these tasks were truncated from the batch and must NOT be left stranded in a non-terminal status. Move EACH of these tasks back to the \`pending\` status role using the set-status verb resolved in the pack so a later pick can re-select them: ${ids.join(", ")}.

Do nothing else. Set status only \u2014 do not implement anything, do not edit other files. Confirm the ids you reset.`;
var resetToPending = defineSubagent({
  name: "reset-to-pending",
  label: "reset-overserved",
  schema: RESET_TO_PENDING_SCHEMA,
  prompt: resetToPendingPrompt,
  parse: identityParse
});

// src/schemas/findings.ts
var FINDING_ITEM = {
  type: "object",
  properties: {
    title: { type: "string" },
    location: { type: "string", description: "file:line or symbol the finding refers to" },
    severity: { type: "string", enum: ["blocker", "major", "minor", "nit"] },
    rationale: { type: "string" },
    "suggested-fix": { type: "string" },
    lens: { type: "string" }
  },
  required: ["title", "location", "severity", "rationale", "suggested-fix", "lens"]
};
var FINDINGS_SCHEMA = {
  type: "object",
  properties: {
    lens: { type: "string", description: "the lens that produced these findings" },
    findings: { type: "array", items: FINDING_ITEM }
  },
  required: ["lens", "findings"]
};
var bucketsSchema = (keys) => ({
  type: "object",
  properties: {
    buckets: {
      type: "object",
      properties: Object.fromEntries(keys.map((key) => [key, { type: "array", items: FINDING_ITEM }])),
      required: [...keys]
    }
  },
  required: ["buckets"]
});
var TRIAGE_SCHEMA = bucketsSchema(["fix-now", "deferred-to-refactor", "out-of-scope"]);
var REFACTOR_TRIAGE_SCHEMA = bucketsSchema(["apply-now", "delayed", "out-of-scope"]);

// src/domain/findings.ts
var SEVERITIES = ["blocker", "major", "minor", "nit"];
var str = (x, fallback) => typeof x === "string" && x !== "" ? x : fallback;
function normalizeFinding(raw) {
  if (!isRecord(raw)) return null;
  const severity = raw.severity;
  return {
    title: str(raw.title, "(untitled)"),
    location: str(raw.location, "?"),
    severity: SEVERITIES.includes(severity) ? severity : "minor",
    rationale: str(raw.rationale, ""),
    "suggested-fix": str(raw["suggested-fix"], ""),
    lens: str(raw.lens, "")
  };
}
function normalizeFindings(raw) {
  if (!Array.isArray(raw)) return [];
  const out = [];
  for (const el of raw) {
    const finding = normalizeFinding(el);
    if (finding) out.push(finding);
  }
  return out;
}

// src/invocations/lens.ts
var lensRolePrompt = ({ role, titleGloss, rationaleGloss, fixGloss }) => ({ lens: lens2, packPath, baseRef }) => `You are the \`${lens2}\` ${role} lens of an autonomous grind-story workflow \u2014 a READ-ONLY reviewer. You never edit the tree; you only report findings.

Read the context pack first: ${packPath}. It resolves what the \`${lens2}\` lens must check (conventions, ADRs, and the lens's own focus).${lens2 === "thermo-nuclear" ? " The `thermo-nuclear` lens delegates to the `thermo-nuclear-code-quality-review` skill \u2014 apply that skill's focus (structural regressions, dramatic-simplification / code-judo that DELETES complexity, spaghetti conditionals, abstraction quality, mislayered logic)." : ""}

Review the change currently under review: inspect \`git diff ${baseRef}...HEAD\` plus any uncommitted working-tree changes (\`git diff\` and \`git status\`) for currency \u2014 that diff IS the change you review. Apply the \`${lens2}\` lens's focus as resolved in the pack.

Return your findings as a list; for EACH finding fill every field:
- \`title\` \u2014 one line naming the ${titleGloss}.
- \`location\` \u2014 file:line (or symbol) it occurs at.
- \`severity\` \u2014 one of blocker / major / minor / nit.
- \`rationale\` \u2014 ${rationaleGloss}.
- \`suggested-fix\` \u2014 a concrete inline ${fixGloss}; you do NOT apply it.
- \`lens\` \u2014 "${lens2}".

If you find nothing, return an empty findings list. Do not edit any file.`;
var lensPrompt = lensRolePrompt({
  role: "code-reviewer",
  titleGloss: "problem",
  rationaleGloss: "why it is a problem",
  fixGloss: "fix"
});
var refactorLensPrompt = lensRolePrompt({
  role: "refactor-reviewer",
  titleGloss: "refactoring opportunity",
  rationaleGloss: "why the refactoring improves the code",
  fixGloss: "refactoring"
});
function parse3(raw) {
  const lens2 = isRecord(raw) && typeof raw.lens === "string" ? raw.lens : "";
  const findings = isRecord(raw) ? normalizeFindings(raw.findings) : [];
  return { lens: lens2, findings };
}
var lens = defineSubagent({
  name: "lens",
  label: ({ lens: name, round }) => `lens:${name}:${round}`,
  schema: FINDINGS_SCHEMA,
  prompt: lensPrompt,
  parse: parse3
});
var refactorLens = defineSubagent({
  name: "refactor-lens",
  label: ({ lens: name, round }) => `refactor-lens:${name}:${round}`,
  schema: FINDINGS_SCHEMA,
  prompt: refactorLensPrompt,
  parse: parse3
});

// src/invocations/buckets.ts
function parseBuckets(raw, keys) {
  const buckets = isRecord(raw) && isRecord(raw.buckets) ? raw.buckets : {};
  const out = {};
  for (const key of keys) {
    out[key] = normalizeFindings(buckets[key]);
  }
  return out;
}

// src/invocations/triage.ts
var triagePrompt = ({ packPath, findingsJson }) => `You are the triage step of an autonomous grind-story workflow. You exercise judgement the orchestrator JS cannot \u2014 you do not write code.

Read the context pack first: ${packPath} (it resolves the ADRs and conventions the findings may cite).

Here are the raw findings from the \`code-reviewer\` lenses, as JSON:
---
${findingsJson}
---

First DEDUP: collapse findings that refer to the same underlying issue \u2014 overlapping \`location\` plus overlapping description \u2014 into one, keeping the strongest severity. Then BUCKET every surviving finding into exactly one of:
- \`fix-now\` \u2014 the change under review introduced it AND it threatens delivered behavior: a correctness bug, a security hole, data loss, a missing/weak test for new behavior, or an ADR violation.
- \`deferred-to-refactor\` \u2014 a legitimate quality issue that does NOT threaten delivered behavior (style, structure, naming, duplication, perf nits). When you are UNCERTAIN whether something belongs in fix-now, put it here.
- \`out-of-scope\` \u2014 pre-existing noise unrelated to this change, or ADR-conflicting suggestions. Reported, never acted on.

Rules: never silently drop a finding (every input finding lands in exactly one bucket), and never scope-creep into work the change did not touch. Return the three buckets; each entry keeps the finding's original fields.`;
function parse4(raw) {
  return parseBuckets(raw, ["fix-now", "deferred-to-refactor", "out-of-scope"]);
}
var triage = defineSubagent({
  name: "triage",
  label: ({ round }) => `triage-A:${round}`,
  schema: TRIAGE_SCHEMA,
  prompt: triagePrompt,
  parse: parse4
});

// src/invocations/refactor-triage.ts
var refactorTriagePrompt = ({ packPath, findingsJson }) => `You are the refactor-triage step of an autonomous grind-story workflow. You exercise judgement the orchestrator JS cannot \u2014 you do not write code.

Read the context pack first: ${packPath} (it resolves the ADRs and conventions the findings may cite).

Here are the raw refactor findings \u2014 the \`refactor-reviewer\` lens output merged with the \`deferred-to-refactor\` findings carried from Phase A \u2014 as JSON:
---
${findingsJson}
---

First DEDUP: collapse findings that refer to the same underlying issue \u2014 overlapping \`location\` plus overlapping description \u2014 into one, keeping the strongest severity. Then BUCKET every surviving finding into exactly one of:
- \`apply-now\` \u2014 improves quality, is scoped to the current task, and has a LOCAL blast radius: a refactoring the \`tdd\` apply agent can land behavior-preservingly right here (e.g. obvious local duplication collapse).
- \`delayed\` \u2014 genuinely valuable structural work that is big, touches OTHER systems, or extends scope: rule-of-three duplication across modules, real code-judo that deletes complexity but reaches beyond this task. Collected as side-task seeds; NOT applied in place here.
- \`out-of-scope\` \u2014 an ADR-conflicting "improvement" (the ADR always wins) or unrelated noise. Reported only, never applied and never filed.

Bias AGGRESSIVELY toward \`delayed\`: route genuinely valuable structural work there rather than forcing it in place. Reserve \`out-of-scope\` STRICTLY for ADR-conflicts and noise. An ADR-conflicting suggestion is always \`out-of-scope\`, never \`apply-now\` or \`delayed\`.

Rules: never silently drop a finding (every input finding lands in exactly one bucket), and never scope-creep. Return the three buckets; each entry keeps the finding's original fields.`;
function parse5(raw) {
  return parseBuckets(raw, ["apply-now", "delayed", "out-of-scope"]);
}
var refactorTriage = defineSubagent({
  name: "refactor-triage",
  label: ({ round }) => `triage-B:${round}`,
  schema: REFACTOR_TRIAGE_SCHEMA,
  prompt: refactorTriagePrompt,
  parse: parse5
});

// src/schemas/implement.ts
var IMPLEMENT_SCHEMA = {
  type: "object",
  properties: {
    green: { type: "boolean", description: "true when the targeted tests are green" },
    summary: { type: "string", description: "what was implemented, or why it could not reach green" }
  },
  required: ["green"]
};

// src/invocations/implement.ts
var implementPrompt = ({ item, storyId, packPath }) => `You are the implementation step of an autonomous grind-story workflow, running the \`tdd\` skill in execute mode.

Read the context pack first: ${packPath}.

Work item: task ${item.taskId}${item.isStory ? " (this IS the story task itself \u2014 it has no subtasks)" : ""}. Load it via the read-task verb from the pack${item.isStory ? "." : `, and read parent story ${storyId} for the decisions/constraints that scope it.`}

The plan is PRE-APPROVED. Use \`tdd\`'s "skip review" path: skip planning/approval, go straight to tracer-bullet red\u2192green cycles. Implement the task's acceptance criteria with behavior-level tests through the public interface. Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments).

Contract: drive toward GREEN targeted tests. Return green=true with a short summary once your targeted tests pass. If you genuinely cannot make them pass (the approach is unworkable, the acceptance criteria are contradictory, or repeated red persists), return green=false with the reason \u2014 do NOT fake green by deleting or weakening tests.

Boundaries \u2014 do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\` (a later step gates that). Only write the source/test files this task needs.

Report what you implemented and which files you created or changed.`;
var implement = defineSubagent({
  name: "implement",
  label: ({ item }) => `impl:${item.taskId}`,
  schema: IMPLEMENT_SCHEMA,
  prompt: implementPrompt,
  parse: identityParse
});

// src/invocations/review-fix.ts
var reviewFixPrompt = ({ pick: pick2, packPath, fixJson }) => `You are the fix step of an autonomous grind-story workflow, running the \`tdd\` skill to resolve \`fix-now\` review findings for task ${pick2.taskId}.

Read the context pack first: ${packPath}.

These review findings were triaged \`fix-now\` \u2014 each threatens delivered behavior and must be fixed under tests:
---
${fixJson}
---

For each finding: write a failing behavior-level test that captures the correct behavior (red), then make it pass (green). Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments). Test behavior through the public interface, not internals.

Contract: return only when your targeted tests are GREEN.

Boundaries \u2014 do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\`. Only write the source/test files these findings require. Report what you changed.`;
var reviewFix = defineSubagent({
  name: "review-fix",
  label: ({ round }) => `fix-A:${round}`,
  prompt: reviewFixPrompt
});

// src/schemas/apply.ts
var APPLY_SCHEMA = {
  type: "object",
  properties: {
    results: {
      type: "array",
      items: {
        type: "object",
        properties: {
          finding: { type: "string", description: "title of the finding this result is for" },
          outcome: { type: "string", enum: ["applied", "dropped"] },
          reason: { type: "string", description: "why it was dropped (or a note when applied)" }
        },
        required: ["finding", "outcome"]
      }
    }
  },
  required: ["results"]
};

// src/invocations/apply.ts
var applyPrompt = ({ pick: pick2, packPath, applyJson }) => `You are the apply step of an autonomous grind-story workflow, running the \`tdd\` skill to apply \`apply-now\` refactorings for task ${pick2.taskId} BEHAVIOR-PRESERVINGLY.

Read the context pack first: ${packPath}.

These refactor findings were triaged \`apply-now\` \u2014 each is a local, scoped quality improvement to land under the green-test contract:
---
${applyJson}
---

For each finding: apply the refactoring while keeping the existing tests green. You MAY rework production code and fix test references to renamed/moved internals (same assertion, same expected value), but you must NEVER change expected behavior to force a refactor through. A refactoring you cannot keep green is DROPPED and reported with a reason \u2014 never forced. Honor the conventions in the pack (\`assert_invoke\` not \`CliRunner\`, \`pyfakefs\` not \`tmp_path\`, \`monkeypatch\` not \`unittest.mock.patch\`; no \`type: ignore\`; no inline imports; no task ids in code comments).

Contract: leave the targeted tests GREEN. Boundaries \u2014 do NOT commit, do NOT change the task's status, do NOT run the full \`uv run tox\`. Only write the source/test files these refactorings require.

Return one result per input finding: \`{finding: <its title>, outcome: applied|dropped, reason: <why dropped, or a note>}\`.`;
function parse6(raw) {
  const rawResults = isRecord(raw) && Array.isArray(raw.results) ? raw.results : [];
  const results = rawResults.filter((r) => isRecord(r) && (r.outcome === "applied" || r.outcome === "dropped")).map((r) => ({
    finding: typeof r.finding === "string" ? r.finding : "",
    outcome: r.outcome === "dropped" ? "dropped" : "applied",
    reason: typeof r.reason === "string" ? r.reason : ""
  }));
  return { results };
}
var apply = defineSubagent({
  name: "apply",
  label: ({ round }) => `apply-B:${round}`,
  schema: APPLY_SCHEMA,
  prompt: applyPrompt,
  parse: parse6
});

// src/schemas/verify.ts
var VERIFY_SCHEMA = {
  type: "object",
  properties: {
    green: { type: "boolean", description: "true when every tox environment passed" },
    failures: { type: "string", description: "concise but specific failure output when red" }
  },
  required: ["green"]
};

// src/invocations/verify.ts
var verifyPrompt = ({ packPath }) => `You are the green-gate step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}.

Run the full acceptance gate exactly as \`CLAUDE.md\` requires: \`uv run tox\` (ALL environments). Do not edit any files. Do not use \`--no-verify\` and do not skip any environment.

Return green=true only if every environment passed. Otherwise return green=false and put the relevant failure output (failing env names, test ids, error messages, file:line) into \`failures\` \u2014 concise but specific enough for a fixer to act without re-running.`;
var verify = defineSubagent({
  name: "verify",
  label: ({ round }) => `tox:${round}`,
  schema: VERIFY_SCHEMA,
  prompt: verifyPrompt,
  parse: identityParse
});

// src/invocations/fix.ts
var fixPrompt = ({ pick: pick2, packPath, failures }) => `You are the fix step of an autonomous grind-story workflow, running the \`tdd\` skill to repair a red \`uv run tox\`.

Read the context pack first: ${packPath}.

The full \`uv run tox\` is RED. Failures:
---
${failures}
---

Per \`CLAUDE.md\` you must fix ALL reported tox issues \u2014 including pre-existing ones, not only those introduced by task ${pick2.taskId}. Keep changes behavior-correct and test-backed where it makes sense. Honor the conventions in the pack (no \`type: ignore\`, \`monkeypatch\` not \`unittest.mock.patch\`, no inline imports, \`assert_invoke\` not \`CliRunner\`).

Boundaries \u2014 do NOT commit, do NOT change task status. Only edit the source/test/config needed to get tox green. Report what you changed.`;
var fix = defineSubagent({
  name: "fix",
  label: ({ round }) => `fix:${round}`,
  prompt: fixPrompt
});

// src/invocations/reset.ts
var resetPrompt = ({ item, storyId, baseRef }) => `You are the discard step of an autonomous grind-story workflow. A side-task could not converge and its uncommitted changes must be thrown away so the run can continue from a clean tree.

Discard ONLY the uncommitted working-tree changes for the failed side-task ${item.taskId}, preserving every prior commit on the \`grind/${storyId}\` branch:
1. \`git reset --hard HEAD\` \u2014 this resets tracked changes back to the last commit (the prior subtask, already committed). It must NOT move the branch off its commits and must NOT touch \`${baseRef}\` history.
2. \`git clean -fd\` to remove untracked files this side-task created \u2014 but NEVER delete anything outside the working tree (the context pack under \`/tmp/grind-story/\` is outside the tree and must be left alone).
3. Confirm with \`git status --porcelain\` (expect empty) and \`git rev-parse HEAD\`.

Do NOT reset to ${baseRef}; do NOT delete branches or commits; do NOT touch \`/tmp/grind-story/\`. Return clean=true only if \`git status --porcelain\` is empty afterward, plus the HEAD sha.`;
var reset = defineSubagent({
  name: "reset",
  label: ({ item }) => `reset:${item.taskId}`,
  schema: RESET_SCHEMA,
  prompt: resetPrompt,
  parse: identityParse
});

// src/invocations/status.ts
var statusPrompt = ({ pick: pick2, packPath }) => `You are the status step of an autonomous grind-story workflow.

Read the context pack first: ${packPath}.

Move task ${pick2.taskId} to the \`in-review\` status role using the set-status verb resolved in the pack. Never move it to \`done\`. Do nothing else, and confirm the new status.`;
var status = defineSubagent({
  name: "status",
  label: ({ pick: pick2 }) => `review:${pick2.taskId}`,
  prompt: statusPrompt
});

// src/schemas/commit.ts
var COMMIT_SCHEMA = {
  type: "object",
  properties: {
    sha: { type: "string", description: "sha of the created commit" },
    message: { type: "string", description: "the commit message used" },
    skipped: {
      type: "array",
      items: { type: "string" },
      description: "untracked files deliberately left unstaged"
    }
  },
  required: ["sha", "message"]
};

// src/invocations/commit.ts
var commitPrompt = ({ pick: pick2, storyId, packPath }) => `You are the commit step of an autonomous grind-story workflow, running the \`commit-summary\` message logic NON-INTERACTIVELY (this is unattended \u2014 never prompt).

Read the context pack first: ${packPath}.

Produce exactly ONE commit on the \`grind/${storyId}\` branch for the current change.

The task-tracker stores task status in git-tracked \`.tasker/<\u2026>.md\` frontmatter, so the pick (\u2192 in-progress) and status (\u2192 in-review) steps that ran before you left tracked edits under \`.tasker/\`. Those edits are EXPECTED and MUST ride in this commit \u2014 never unstage or exclude them as noise; \`git add -u\` stages them along with the source/test changes.

Staging:
1. \`git add -u\` to stage tracked modifications/deletions (this includes the \`.tasker/\` status-frontmatter edits for task ${pick2.taskId}).
2. \`git status --porcelain\` for untracked (\`??\`) entries. For each:
   - DENYLIST \u2014 never stage, never prompt: \`.env\`, \`.env.*\`, \`*.key\`, \`*.pem\`, \`*.p12\`, \`*.pfx\`, \`*.secret\`, \`credentials.json\`, \`secrets.yaml\`, \`.netrc\`, \`.npmrc\`, \`.venv/\`, \`venv/\`, \`node_modules/\`, \`__pycache__/\`, \`*.sqlite\`, \`*.db\`.
   - SUSPICIOUS \u2014 never stage, never prompt: editor temps (\`*.swp\`, \`*.swo\`, \`*~\`), backups (\`*.bak\`, \`*.orig\`), OS artifacts (\`.DS_Store\`, \`Thumbs.db\`), or anything common practice would not check in.
   - Otherwise \u2014 clearly project source/tests/docs created for task ${pick2.taskId}: stage it.
   Collect every untracked path you skip into a list to return.
3. Compose the message with \`commit-summary\` rules: calibrate prefix/bullet style from \`git log -n 10\`, pick the right prefix, imperative subject \u226472 chars, body only when warranted, correct backtick usage. Do NOT put any task id (e.g. ${pick2.taskId}) in the message \u2014 match the repo log style. Never append \`Co-Authored-By\` or \`Generated with Claude Code\` footers.
4. Commit via \`git commit -F <tmpfile>\` (write the raw message to a temp file, then remove it).

Return the resulting commit sha (\`git rev-parse HEAD\`), the exact message you used, and the list of skipped untracked files.`;
var commit = defineSubagent({
  name: "commit",
  label: ({ pick: pick2 }) => `commit:${pick2.taskId}`,
  schema: COMMIT_SCHEMA,
  prompt: commitPrompt,
  parse: identityParse
});

// src/schemas/side-tasks.ts
var EXISTING_SIDE_TASKS_SCHEMA = {
  type: "object",
  properties: {
    sideTasks: {
      type: "array",
      description: "the parsed origin/finding fields of every refactor side-task already filed under the story",
      items: {
        type: "object",
        properties: {
          origin: { type: "string", description: "the spawning task id from the side-task's `- origin:` line" },
          title: { type: "string", description: "the finding title quoted on the `- origin:` line" },
          location: { type: "string", description: "the `- location:` line value, or empty string when absent" }
        },
        required: ["origin", "title"]
      }
    }
  },
  required: ["sideTasks"]
};
var FILE_SIDE_TASKS_SCHEMA = {
  type: "object",
  properties: {
    created: {
      type: "array",
      items: {
        type: "object",
        properties: {
          taskId: { type: "string", description: "id of the created side-task" },
          title: { type: "string", description: "title given to the side-task" },
          signature: { type: "string", description: "finding signature this side-task covers" }
        },
        required: ["taskId"]
      }
    }
  },
  required: ["created"]
};

// src/invocations/existing-side-tasks.ts
var existingSideTasksPrompt = ({ storyId, packPath }) => `You are the dedupe-scan step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs).

Using the read-task verb, load story ${storyId} and inspect every one of its children. A refactor side-task is a child whose description contains a \`## Refactor side-task\` marker block with an \`- origin:\` line. The origin line looks like:
\`- origin: <spawning-task-id> \u2014 refactor finding "<finding title>"\`

For EACH such existing side-task, emit one row with these RAW fields (do NOT lowercase, trim, or join them \u2014 the orchestrator canonicalizes them):
- \`origin\` \u2014 the \`<spawning-task-id>\` from the \`- origin:\` line.
- \`title\` \u2014 the \`<finding title>\` quoted on the \`- origin:\` line.
- \`location\` \u2014 the value of the side-task body's \`- location:\` line if present, else an empty string.

Return only the list of rows. Do not create, edit, or re-status any task.`;
function parse7(raw) {
  const rawRows = isRecord(raw) && Array.isArray(raw.sideTasks) ? raw.sideTasks : [];
  const sideTasks = rawRows.filter((row) => isRecord(row) && typeof row.origin === "string").map((row) => ({
    origin: row.origin,
    title: typeof row.title === "string" ? row.title : void 0,
    location: typeof row.location === "string" ? row.location : void 0
  }));
  return { sideTasks };
}
var existingSideTasks = defineSubagent({
  name: "existing-side-tasks",
  label: ({ item }) => `dedupe-scan:${item.taskId}`,
  schema: EXISTING_SIDE_TASKS_SCHEMA,
  prompt: existingSideTasksPrompt,
  parse: parse7
});

// src/invocations/file-side-tasks.ts
var fileSideTasksPrompt = ({ item, storyId, packPath, items }) => `You are the side-task filing step of an autonomous grind-story workflow for story ${storyId}.

Read the context pack first: ${packPath} (it resolves this repo's task-tracker verbs \u2014 in particular create-subtask).

File each of the following refactor side-tasks as a FLAT child of story ${storyId} (parent = ${storyId}, NOT nested under ${item.taskId}). Use the create-subtask verb with \`parent: "${storyId}"\`, the given title, and the given description VERBATIM (it already contains the depth marker block). Each item:
---
${JSON.stringify(items, null, 2)}
---

For each item, create the subtask and report its new id alongside the item's \`signature\` (copy the signature through unchanged). The side-tasks are born \`pending\` \u2014 do NOT start, review, or finish them. Create nothing else.

Return one entry per item: \`{taskId: <new id>, title: <title used>, signature: <the item's signature>}\`.`;
function parse8(raw) {
  const rawRows = isRecord(raw) && Array.isArray(raw.created) ? raw.created : [];
  const created = rawRows.filter((c) => isRecord(c) && typeof c.taskId === "string" && c.taskId.length > 0).map((c) => ({
    taskId: c.taskId,
    title: typeof c.title === "string" ? c.title : void 0,
    signature: typeof c.signature === "string" ? c.signature : void 0
  }));
  return { created };
}
var fileSideTasks = defineSubagent({
  name: "file-side-tasks",
  label: ({ item }) => `file-side-tasks:${item.taskId}`,
  schema: FILE_SIDE_TASKS_SCHEMA,
  prompt: fileSideTasksPrompt,
  parse: parse8
});

// src/index.ts

async function main() {
  const rawArgs = typeof args === "string" ? args.trim() : String(args || "").trim();
  const argTokens = rawArgs.split(/\s+/).filter(Boolean);
  const storyId = argTokens.length ? argTokens[0] : "";
  if (!storyId) {
    return 'grind-story: no story id given. Invoke as Workflow({name:"grind-story", args:"<story-id>"}).';
  }
  const DEFAULT_MAX_DEPTH = 2;
  const DEFAULT_TOTAL_CAP = 30;
  function parseNonNegativeOverride(tokens, key, fallback) {
    for (const tok of tokens) {
      const eq = tok.indexOf("=");
      if (eq <= 0) continue;
      if (tok.slice(0, eq) !== key) continue;
      const n = Number.parseInt(tok.slice(eq + 1), 10);
      if (Number.isFinite(n) && n >= 0) return n;
    }
    return fallback;
  }
  const maxDepth = parseNonNegativeOverride(argTokens.slice(1), "maxDepth", DEFAULT_MAX_DEPTH);
  const totalSideTaskCap = parseNonNegativeOverride(argTokens.slice(1), "totalCap", DEFAULT_TOTAL_CAP);
  const SIDE_TASK_HEADING = "## Refactor side-task";
  function parseDepthMarker(description) {
    if (!description.includes(SIDE_TASK_HEADING)) return null;
    const depthMatch = description.match(/^[ \t]*-[ \t]*depth:[ \t]*(\d+)[ \t]*$/m);
    if (!depthMatch) return { malformed: true };
    const originMatch = description.match(/^[ \t]*-[ \t]*origin:[ \t]*(.+?)[ \t]*$/m);
    return {
      depth: Number.parseInt(depthMatch[1], 10),
      origin: originMatch ? originMatch[1].trim() : ""
    };
  }
  function resolveMarker(taskId, description) {
    const marker = parseDepthMarker(description);
    if (marker === null) return { depth: 0, origin: "" };
    if (marker.malformed) {
      log(`Depth marker malformed on ${taskId} \u2014 treating as depth 0.`);
      return { depth: 0, origin: "" };
    }
    return { depth: marker.depth, origin: marker.origin || "" };
  }
  function firstRepeat(items, seen2) {
    return items.find((it) => seen2.has(it.taskId)) || null;
  }
  function recordSeen(items, seen2) {
    for (const it of items) seen2.add(it.taskId);
  }
  function buildSideTaskDescription(depth, originTaskId, finding) {
    const lines = [];
    lines.push(SIDE_TASK_HEADING);
    lines.push(`- depth: ${depth}`);
    lines.push(`- origin: ${originTaskId} \u2014 refactor finding "${finding.title}"`);
    lines.push("");
    lines.push("## Goal");
    lines.push("");
    lines.push(`Apply the deferred refactoring surfaced while processing ${originTaskId}.`);
    if (finding.location) lines.push(`- location: ${finding.location}`);
    lines.push(`- severity: ${finding.severity}`);
    if (finding.rationale) {
      lines.push("");
      lines.push(finding.rationale);
    }
    if (finding["suggested-fix"]) {
      lines.push("");
      lines.push("## Suggested fix");
      lines.push("");
      lines.push(finding["suggested-fix"]);
    }
    return lines.join("\n");
  }
  function findingSignature(originTaskId, finding) {
    const f = finding || {};
    const loc = (f.location || "").trim().toLowerCase();
    const title = (f.title || "").trim().toLowerCase();
    return `${(originTaskId || "").trim()}::${title}::${loc}`;
  }
  const GUARD_MAX = 100;
  function phaseCap(phase2) {
    const PHASE_CAPS = { "Verify": 5, "Review-A": 10, "Refactor-B": 10 };
    return PHASE_CAPS[phase2];
  }
  const roundTag = (phase2, round, cap, taskId) => `${phase2} round ${round}/${cap} for ${taskId}`;
  phase("Setup");
  const setup = await branch.run({ storyId });
  if (!setup) return `grind-story: setup step failed for story ${storyId} \u2014 could not create the grind branch.`;
  phase("Bootstrap");
  const pack = await bootstrap.run({ storyId });
  if (!pack) return `grind-story: bootstrap step failed for story ${storyId} \u2014 no context pack was written.`;
  const packPath = pack.packPath;
  const reviewLenses = (await roster.run({ packPath })).lenses;
  if (reviewLenses.length === 0) {
    log("Phase A skipped for the run: the code-reviewer roster resolved empty.");
  }
  const refactorLenses = (await refactorRoster.run({ packPath })).lenses;
  if (refactorLenses.length === 0) {
    log("Phase B skipped for the run: the refactor-reviewer roster resolved empty.");
  }
  const processed = [];
  const deferredFindings = [];
  const delayedFindings = [];
  const outOfScopeFindings = [];
  const droppedRefactors = [];
  const seen = /* @__PURE__ */ new Set();
  const droppedSideTasks = [];
  const escalations = [];
  const filedSignatures = /* @__PURE__ */ new Set();
  const filedSideTasks = [];
  const residualFindings = [];
  const capSuppressed = [];
  let sideTaskCount = 0;
  class Halt {
    kind = "halt";
    failure;
    constructor(failure) {
      this.failure = failure;
    }
  }
  class SkipItem {
    kind = "skip";
  }
  async function failConvergence(item, depth, reason, failures) {
    if (depth === 0) {
      log(`HARD FAILURE: ${item.taskId} (depth 0) could not converge \u2014 ${reason}. Halting the run.`);
      throw new Halt({ taskId: item.taskId, title: item.title, reason, failures });
    }
    log(`${item.taskId} (depth ${depth}) could not converge \u2014 ${reason}. Discarding its changes (git reset --hard) and continuing.`);
    const reset2 = await reset.run({ item, storyId, baseRef: setup.baseRef });
    if (!reset2 || !reset2.clean) {
      log(`HARD FAILURE: could not cleanly discard side-task ${item.taskId} \u2014 halting to avoid building on a dirty tree.`);
      throw new Halt({
        taskId: item.taskId,
        title: item.title,
        reason: `side-task git reset --hard did not leave a clean tree (${reason})`,
        failures
      });
    }
    droppedSideTasks.push({ taskId: item.taskId, title: item.title, depth, reason });
    throw new SkipItem();
  }
  async function runLensRound(lenses, lensAgent, round) {
    const results = await parallel(
      lenses.map((lens2) => lensAgent.run({ lens: lens2, packPath, baseRef: setup.baseRef, round }))
    );
    return results.flatMap((r) => r.findings);
  }
  async function reviewPhaseA(item, depth) {
    const carriedDeferred = [];
    if (reviewLenses.length === 0) return carriedDeferred;
    const ph = "Review-A";
    phase(ph);
    const cap = phaseCap(ph);
    let openFixNow = [];
    for (let round = 1; round <= cap; round++) {
      const findings = await runLensRound(reviewLenses, lens, round);
      if (findings.length === 0) {
        openFixNow = [];
        log(`${roundTag(ph, round, cap, item.taskId)}: lenses raised no findings.`);
        break;
      }
      const buckets = await triage.run({ packPath, findingsJson: JSON.stringify(findings, null, 2), round });
      const fixNow = buckets["fix-now"];
      const deferred = buckets["deferred-to-refactor"];
      for (const f of deferred) {
        deferredFindings.push({ taskId: item.taskId, finding: f });
        carriedDeferred.push(f);
      }
      if (fixNow.length === 0) {
        openFixNow = [];
        log(`${roundTag(ph, round, cap, item.taskId)}: no fix-now findings; ${deferred.length} carried to Phase B.`);
        break;
      }
      openFixNow = fixNow;
      log(`${roundTag(ph, round, cap, item.taskId)}: ${fixNow.length} fix-now finding(s); routing to a tdd fix agent.`);
      if (round === cap) break;
      await reviewFix.run({ pick: item, packPath, fixJson: JSON.stringify(fixNow, null, 2), round });
    }
    if (openFixNow.length > 0) {
      escalations.push({
        kind: "fix-now-cap-open",
        taskId: item.taskId,
        depth,
        count: openFixNow.length,
        detail: `${openFixNow.length} fix-now finding(s) still open after ${cap} Review-A rounds`
      });
      await failConvergence(
        item,
        depth,
        `${openFixNow.length} fix-now finding(s) still open at the ${cap}-round cap`,
        JSON.stringify(openFixNow, null, 2)
      );
    }
    return carriedDeferred;
  }
  async function refactorPhaseB(item, carriedDeferred) {
    const carriedDelayed = [];
    if (refactorLenses.length === 0) return carriedDelayed;
    const ph = "Refactor-B";
    phase(ph);
    const cap = phaseCap(ph);
    for (let round = 1; round <= cap; round++) {
      const findings = await runLensRound(refactorLenses, refactorLens, round);
      if (round === 1) findings.push(...carriedDeferred);
      if (findings.length === 0) {
        log(`${roundTag(ph, round, cap, item.taskId)}: lenses raised no findings \u2014 loop dry.`);
        break;
      }
      const buckets = await refactorTriage.run({ packPath, findingsJson: JSON.stringify(findings, null, 2), round });
      const applyNow = buckets["apply-now"];
      const delayed = buckets["delayed"];
      const outOfScope = buckets["out-of-scope"];
      for (const f of delayed) {
        delayedFindings.push({ taskId: item.taskId, finding: f });
        carriedDelayed.push(f);
      }
      for (const f of outOfScope) outOfScopeFindings.push({ taskId: item.taskId, finding: f });
      if (applyNow.length === 0) {
        log(`${roundTag(ph, round, cap, item.taskId)}: no apply-now; ${delayed.length} delayed, ${outOfScope.length} out-of-scope \u2014 loop dry.`);
        break;
      }
      log(`${roundTag(ph, round, cap, item.taskId)}: ${applyNow.length} apply-now refactoring(s); routing to a tdd apply agent.`);
      if (round === cap) {
        log(`Refactor-B cap reached for ${item.taskId} with apply-now work still surfacing \u2014 stopping the refactor loop.`);
        break;
      }
      const applied = await apply.run({ pick: item, packPath, applyJson: JSON.stringify(applyNow, null, 2), round });
      const results = applied.results;
      for (const res of results) {
        if (res && res.outcome === "dropped") {
          droppedRefactors.push({ taskId: item.taskId, finding: res.finding, reason: res.reason || "(no reason given)" });
          log(`Refactor dropped for ${item.taskId}: "${res.finding}" \u2014 ${res.reason || "(no reason given)"}`);
        }
      }
    }
    return carriedDelayed;
  }
  async function fileSideTasks2(item, depth, carriedDelayed) {
    if (carriedDelayed.length === 0) return;
    if (depth >= maxDepth) {
      for (const f of carriedDelayed) residualFindings.push({ taskId: item.taskId, depth, finding: f });
      log(`${item.taskId} is at depth ${depth} (maxDepth ${maxDepth}) \u2014 its ${carriedDelayed.length} delayed finding(s) reported as residual, not filed.`);
      return;
    }
    phase("File-side-tasks");
    const existing = await existingSideTasks.run({ item, storyId, packPath });
    const existingRows = existing.sideTasks;
    for (const row of existingRows) {
      filedSignatures.add(findingSignature(row.origin, { title: row.title, location: row.location }));
    }
    const toFile = [];
    for (const finding of carriedDelayed) {
      const sig = findingSignature(item.taskId, finding);
      if (filedSignatures.has(sig)) {
        log(`Skipping already-filed delayed finding "${finding.title}" from ${item.taskId}.`);
        continue;
      }
      filedSignatures.add(sig);
      if (sideTaskCount + toFile.length >= totalSideTaskCap) {
        capSuppressed.push({ taskId: item.taskId, finding });
        continue;
      }
      const childDepth = depth + 1;
      toFile.push({
        signature: sig,
        title: `Refactor: ${finding.title}`.slice(0, 120),
        description: buildSideTaskDescription(childDepth, item.taskId, finding)
      });
    }
    const n = capSuppressed.filter((c) => c.taskId === item.taskId).length;
    if (n > 0) {
      log(`Total side-task cap (${totalSideTaskCap}) reached \u2014 ${n} delayed finding(s) from ${item.taskId} suppressed, not filed.`);
    }
    if (toFile.length > 0) {
      const filed = await fileSideTasks.run({ item, storyId, packPath, items: toFile });
      const created = filed.created;
      for (const c of created) {
        sideTaskCount += 1;
        filedSideTasks.push({ originTaskId: item.taskId, childTaskId: c.taskId, title: c.title, depth: depth + 1 });
        log(`Filed side-task ${c.taskId} (depth ${depth + 1}) from ${item.taskId}: "${c.title || ""}".`);
      }
    }
  }
  async function verifyStep(item, depth) {
    const ph = "Verify";
    phase(ph);
    const cap = phaseCap(ph);
    let lastFailures = "";
    for (let round = 1; round <= cap; round++) {
      const v = await verify.run({ packPath, round });
      if (v && v.green) return;
      lastFailures = v && v.failures || "(no failure detail captured)";
      log(`${roundTag(ph, round, cap, item.taskId)}: tox red; routing failures to a fix agent.`);
      if (round === cap) break;
      await fix.run({ pick: item, packPath, failures: lastFailures, round });
    }
    await failConvergence(item, depth, `uv run tox still red after ${cap} fix rounds`, lastFailures);
  }
  async function statusAndCommit(item, depth, origin) {
    phase("Status");
    await status.run({ pick: item, packPath });
    phase("Commit");
    const commit2 = await commit.run({ pick: item, storyId, packPath });
    if (!commit2) {
      await failConvergence(item, depth, "commit step returned no result", "");
    }
    if (commit2.skipped && commit2.skipped.length) {
      log(`Skipped untracked files (not staged): ${commit2.skipped.join(", ")}`);
    }
    processed.push({ taskId: item.taskId, title: item.title, sha: commit2.sha, message: commit2.message, depth, origin });
  }
  async function processItem(item) {
    const { depth, origin } = resolveMarker(item.taskId, item.description);
    log(`Processing ${item.taskId} (depth ${depth}): ${item.title || "(untitled)"}`);
    phase("Implement");
    const impl = await implement.run({ item, storyId, packPath });
    if (!impl || !impl.green) {
      await failConvergence(item, depth, "tdd never reached green targeted tests", impl && impl.summary || "");
    }
    const carriedDeferred = await reviewPhaseA(item, depth);
    const carriedDelayed = await refactorPhaseB(item, carriedDeferred);
    await fileSideTasks2(item, depth, carriedDelayed);
    await verifyStep(item, depth);
    await statusAndCommit(item, depth, origin);
  }
  async function runGroup(items, processOne, classify) {
    for (const item of items) {
      try {
        await processOne(item);
      } catch (e) {
        const c = classify(e);
        if (c.kind === "skip") continue;
        if (c.kind === "halt" && c.halt) return c.halt;
        throw e;
      }
    }
    return null;
  }
  function classifyLoopError(e) {
    const k = typeof e === "object" && e !== null ? e.kind : void 0;
    if (k === "halt") return { kind: "halt", halt: e };
    if (k === "skip") return { kind: "skip" };
    return { kind: "rethrow" };
  }
  while (processed.length < GUARD_MAX) {
    phase("Pick");
    const pick2 = await pick.run({ storyId, packPath, excludeIds: Array.from(seen) });
    if (pick2.done) {
      log(
        pick2.stalled ? "pick returned no usable items despite done=false \u2014 terminating; a task may have been left in-progress by the pick agent (check the tracker)." : "No pending work items remain."
      );
      break;
    }
    if (pick2.overserved && pick2.overserved.length) {
      log(formatOverserveWarning(pick2));
      await resetToPending.run({ packPath, ids: pick2.overserved, kind: pick2.kind });
    }
    const repeat = firstRepeat(pick2.items, seen);
    if (repeat) {
      log(`Re-picked ${repeat.taskId} \u2014 stopping to avoid a loop (already attempted this run); it (and any group siblings) may have been left in-progress by the pick agent \u2014 check the tracker.`);
      break;
    }
    recordSeen(pick2.items, seen);
    const halted = await runGroup(pick2.items, processItem, classifyLoopError);
    if (halted) return report(setup, packPath, processed, refactorOutcomes(), halted.failure);
  }
  return report(setup, packPath, processed, refactorOutcomes(), null);
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
      escalations
    };
  }
  function report(setup2, packPath2, processed2, refactor, failure) {
    const r = refactor;
    const deferredFindings2 = r.deferredFindings || [];
    const delayedFindings2 = r.delayedFindings || [];
    const outOfScopeFindings2 = r.outOfScopeFindings || [];
    const droppedRefactors2 = r.droppedRefactors || [];
    const filedSideTasks2 = r.filedSideTasks || [];
    const residualFindings2 = r.residualFindings || [];
    const capSuppressed2 = r.capSuppressed || [];
    const droppedSideTasks2 = r.droppedSideTasks || [];
    const escalations2 = r.escalations || [];
    const lines = [];
    const section = (title, items, fmt) => {
      if (!items || !items.length) return;
      lines.push("", `${title} (${items.length}):`);
      for (const it of items) lines.push(`  - ${fmt(it)}`);
    };
    const findingCore = (f) => `${f.title} @ ${f.location}`;
    const findingRow = (d) => `[${d.taskId}] ${findingCore(d.finding)} (${d.finding.severity})`;
    lines.push(`grind-story \u2014 story ${storyId}`);
    lines.push(`branch: ${setup2.branch} (base ${setup2.baseRef})`);
    lines.push(`context pack: ${packPath2}`);
    if (processed2.length === 0) {
      lines.push("", "No work items were committed.");
    } else {
      lines.push("", `Committed ${processed2.length} work item(s) (task \u2192 commit-sha \u2192 origin; each \u2192 in-review, tox green):`);
      for (const p of processed2) {
        const sha = (p.sha || "").slice(0, 12);
        const subject = (p.message || "").split("\n")[0];
        const originTag = p.origin ? ` \u2190 origin ${p.origin}` : " (origin: original subtask)";
        lines.push(`  - ${p.taskId} "${p.title || ""}" \u2192 ${sha}${originTag} : ${subject}`);
      }
    }
    section(
      "Dropped side-tasks (could not converge; git reset --hard-discarded, run continued)",
      droppedSideTasks2,
      (d) => `${d.taskId} (depth ${d.depth}) "${d.title || ""}" \u2014 ${d.reason || "(no reason given)"}`
    );
    section("Deferred-to-refactor findings carried into Phase B", deferredFindings2, findingRow);
    section("Delayed refactor findings collected for side-task filing", delayedFindings2, findingRow);
    section(
      "Refactor side-tasks filed",
      filedSideTasks2,
      (s) => `${s.childTaskId} (depth ${s.depth}) "${s.title || ""}" \u2190 origin ${s.originTaskId}`
    );
    section(
      "Residual refactor findings at maxDepth (not filed)",
      residualFindings2,
      (d) => `[${d.taskId} depth ${d.depth}] ${findingCore(d.finding)} (${d.finding.severity})`
    );
    section(`Side-task findings suppressed by the total cap of ${totalSideTaskCap}`, capSuppressed2, findingRow);
    section("Out-of-scope refactor findings (reported only, not filed)", outOfScopeFindings2, findingRow);
    section(
      "Dropped refactorings (could not stay green)",
      droppedRefactors2,
      (d) => `[${d.taskId}] ${d.finding || "(untitled)"} \u2014 ${d.reason || "(no reason given)"}`
    );
    const escalationLines = [];
    if (failure) {
      escalationLines.push(`  - HALT: ${failure.taskId} "${failure.title || ""}" \u2014 ${failure.reason}`);
    }
    for (const e of escalations2) {
      escalationLines.push(`  - fix-now at cap: ${e.taskId} (depth ${e.depth}) \u2014 ${e.detail || e.count + " open fix-now finding(s)"}`);
    }
    for (const d of residualFindings2) {
      escalationLines.push(`  - residual at maxDepth: [${d.taskId} depth ${d.depth}] ${findingCore(d.finding)}`);
    }
    for (const d of capSuppressed2) {
      escalationLines.push(`  - cap-suppressed side-task: [${d.taskId}] ${findingCore(d.finding)}`);
    }
    if (escalationLines.length) {
      lines.push("");
      lines.push(`Escalations for human review (${escalationLines.length}):`);
      lines.push(...escalationLines);
    }
    if (failure) {
      lines.push("");
      lines.push(`HALTED on ${failure.taskId} "${failure.title || ""}": ${failure.reason}`);
      lines.push("Working tree left dirty for inspection; prior commits preserved.");
      if (failure.failures) {
        lines.push("--- last failure output ---");
        lines.push(failure.failures);
      }
    } else {
      lines.push("");
      lines.push("Run complete \u2014 no pending work items remain.");
    }
    return lines.join("\n");
  }
}

return await main()
