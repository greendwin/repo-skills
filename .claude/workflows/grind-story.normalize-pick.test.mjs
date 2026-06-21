// Behavior-level tests for `normalizePick` — extracted from grind-story.js via
// _extract-fn.mjs (see that file for why it is sliced rather than imported).
// Exercises the uniform `{done, kind, items}` contract through that public seam.

import test from 'node:test'
import assert from 'node:assert/strict'
import { extractFunction } from './_extract-fn.mjs'

const normalizePick = extractFunction('normalizePick')

// The single terminal "nothing to do" pick shape every collapse case yields,
// mirroring the source's lone `donePick()` factory — assert against THE done
// pick so the terminal shape lives in one place across the suite.
const DONE = { done: true, kind: 'feature', items: [] }

test('a done pick collapses to an empty feature group', () => {
  assert.deepEqual(normalizePick({ done: true }), DONE)
})

test('a null/shapeless pick is treated as done', () => {
  assert.deepEqual(normalizePick(null), DONE)
  assert.deepEqual(normalizePick(undefined), DONE)
})

test('a feature pick yields kind feature with its single item', () => {
  const out = normalizePick({
    done: false,
    kind: 'feature',
    items: [{ taskId: 'tFeat', title: 'Split caps', description: 'body', isStory: false }],
  })
  assert.equal(out.done, false)
  assert.equal(out.kind, 'feature')
  assert.deepEqual(out.items, [
    { taskId: 'tFeat', title: 'Split caps', description: 'body', isStory: false },
  ])
})

test('a refactor pick keeps kind refactor', () => {
  const out = normalizePick({
    done: false,
    kind: 'refactor',
    items: [{ taskId: 'tRefac', title: 'Refactor: dedup', description: '## Refactor side-task' }],
  })
  assert.equal(out.kind, 'refactor')
  assert.equal(out.items.length, 1)
  assert.deepEqual(out.items[0], {
    taskId: 'tRefac',
    title: 'Refactor: dedup',
    description: '## Refactor side-task',
    isStory: false,
  })
})

test('an unknown kind defaults to feature', () => {
  const out = normalizePick({ done: false, items: [{ taskId: 's1t1' }] })
  assert.equal(out.kind, 'feature')
  const bogus = normalizePick({ done: false, kind: 'wat', items: [{ taskId: 's1t1' }] })
  assert.equal(bogus.kind, 'feature')
})

test('missing fields are defaulted, items without a taskId are dropped', () => {
  const out = normalizePick({
    done: false,
    kind: 'feature',
    items: [{ taskId: 's1t1' }, { title: 'no id' }, { taskId: '' }, null],
  })
  assert.equal(out.items.length, 1)
  assert.deepEqual(out.items[0], { taskId: 's1t1', title: '', description: '', isStory: false })
})

test('isStory is preserved only when literally true', () => {
  const story = normalizePick({ done: false, items: [{ taskId: 's1', isStory: true }] })
  assert.equal(story.items[0].isStory, true)
  const truthy = normalizePick({ done: false, items: [{ taskId: 's1', isStory: 'yes' }] })
  assert.equal(truthy.items[0].isStory, false)
})

test('a non-done pick with no usable items terminates the loop', () => {
  assert.deepEqual(normalizePick({ done: false, items: [] }), DONE)
  assert.deepEqual(normalizePick({ done: false }), DONE)
  assert.deepEqual(normalizePick({ done: false, items: 'nope' }), DONE)
})
