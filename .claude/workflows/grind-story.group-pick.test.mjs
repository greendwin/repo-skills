// Behavior-level tests for `normalizePick` — extracted from grind-story.js via
// _extract-fn.mjs (see that file for why it is sliced rather than imported).
// Exercises the grouping rules of the `{done, kind, items}` contract: a refactor
// pick may carry up to 5 members, a feature pick is always clamped to one, and
// the cap of 5 is enforced in JS regardless of what the pick agent returns.

import test from 'node:test'
import assert from 'node:assert/strict'
import { extractFunction } from './_extract-fn.mjs'

const normalizePick = extractFunction('normalizePick')

const refactorItems = (n) =>
  Array.from({ length: n }, (_, i) => ({
    taskId: `r${i + 1}`,
    title: `Refactor: dedup ${i + 1}`,
    description: '## Refactor side-task',
  }))

test('a refactor pick keeps several small eligible members as a group', () => {
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(4) })
  assert.equal(out.kind, 'refactor')
  assert.equal(out.items.length, 4)
  assert.deepEqual(
    out.items.map((it) => it.taskId),
    ['r1', 'r2', 'r3', 'r4'],
  )
})

test('a single eligible refactor is a valid group of one', () => {
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(1) })
  assert.equal(out.kind, 'refactor')
  assert.equal(out.items.length, 1)
})

test('a refactor pick is hard-capped at 5 members even when more are served', () => {
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(9) })
  assert.equal(out.kind, 'refactor')
  assert.equal(out.items.length, 5)
  assert.deepEqual(
    out.items.map((it) => it.taskId),
    ['r1', 'r2', 'r3', 'r4', 'r5'],
  )
})

test('exactly five refactors are all kept (the cap is inclusive)', () => {
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(5) })
  assert.equal(out.items.length, 5)
})

test('a feature pick never returns more than one item even if several are served', () => {
  const out = normalizePick({
    done: false,
    kind: 'feature',
    items: [
      { taskId: 'f1', title: 'Feature one', description: 'body' },
      { taskId: 'f2', title: 'Feature two', description: 'body' },
      { taskId: 'f3', title: 'Feature three', description: 'body' },
    ],
  })
  assert.equal(out.kind, 'feature')
  assert.equal(out.items.length, 1)
  assert.equal(out.items[0].taskId, 'f1')
})

test('a feature pick with one item is unchanged', () => {
  const out = normalizePick({
    done: false,
    kind: 'feature',
    items: [{ taskId: 'f1', title: 'Feature one', description: 'body', isStory: false }],
  })
  assert.equal(out.items.length, 1)
  assert.equal(out.items[0].taskId, 'f1')
})

test('an over-served refactor pick surfaces the truncated ids instead of dropping them silently', () => {
  // The pick agent moves EVERY member it returns to in-progress before returning.
  // When it over-serves (returns 6+), the JS clamp keeps only the first 5 — but
  // members 6+ are already in-progress in the tracker. A silent slice would
  // strand them there (the pick loop only re-selects pending tasks). So the
  // truncated ids must be surfaced (`overserved`) for the caller to reset back to
  // pending: truncation is self-healed, never a silent drop into in-progress limbo.
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(7) })
  assert.equal(out.items.length, 5)
  assert.deepEqual(out.overserved, ['r6', 'r7'])
  // No surviving member is both kept AND surfaced as dropped — the two sets are disjoint.
  const kept = out.items.map((it) => it.taskId)
  for (const id of out.overserved) assert.ok(!kept.includes(id))
})

test('a within-cap refactor pick over-serves nothing (zero-cost common path)', () => {
  const out = normalizePick({ done: false, kind: 'refactor', items: refactorItems(3) })
  assert.deepEqual(out.overserved, [])
})

test('idless members are dropped before the refactor cap is applied', () => {
  // Five real members plus interleaved junk must still yield five — the cap is
  // applied to the surviving (well-formed) members, not the raw input length.
  const items = [
    { taskId: 'r1', description: '## Refactor side-task' },
    { title: 'no id' },
    { taskId: 'r2', description: '## Refactor side-task' },
    null,
    { taskId: 'r3', description: '## Refactor side-task' },
    { taskId: '' },
    { taskId: 'r4', description: '## Refactor side-task' },
    { taskId: 'r5', description: '## Refactor side-task' },
    { taskId: 'r6', description: '## Refactor side-task' },
  ]
  const out = normalizePick({ done: false, kind: 'refactor', items })
  assert.deepEqual(
    out.items.map((it) => it.taskId),
    ['r1', 'r2', 'r3', 'r4', 'r5'],
  )
})
