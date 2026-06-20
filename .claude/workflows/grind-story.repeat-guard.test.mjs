// Behavior-level tests for the grind-story multi-item repeat guard.
//
// `grind-story.js` is loaded by the harness as a function body (it ends in a
// top-level `return`), so it cannot be imported directly. These tests extract
// the pure `firstRepeat` and `recordSeen` helpers from the source by name and
// evaluate them in isolation, exercising the group-aware repeat-guard contract
// through that public seam. Run with:
// `node --test .claude/workflows/grind-story.repeat-guard.test.mjs`.

import test from 'node:test'
import assert from 'node:assert/strict'
import { extractFunction } from './_extract-fn.mjs'

const firstRepeat = extractFunction('firstRepeat')
const recordSeen = extractFunction('recordSeen')

test('a clean group trips no repeat guard', () => {
  const seen = new Set(['s1t1'])
  const items = [{ taskId: 's2t1' }, { taskId: 's2t2' }]
  assert.equal(firstRepeat(items, seen), null)
})

test('a repeat anywhere in a multi-item group is detected (not just the first)', () => {
  const seen = new Set(['s2t2'])
  const items = [{ taskId: 's2t1' }, { taskId: 's2t2' }, { taskId: 's2t3' }]
  const repeat = firstRepeat(items, seen)
  assert.notEqual(repeat, null)
  assert.equal(repeat.taskId, 's2t2')
})

test('the first repeat is returned when several items are already seen', () => {
  const seen = new Set(['s2t2', 's2t3'])
  const items = [{ taskId: 's2t1' }, { taskId: 's2t2' }, { taskId: 's2t3' }]
  assert.equal(firstRepeat(items, seen).taskId, 's2t2')
})

test('an empty group never trips the guard', () => {
  assert.equal(firstRepeat([], new Set(['x'])), null)
})

test('recordSeen records every id of a group, not just the first', () => {
  const seen = new Set()
  recordSeen([{ taskId: 's2t1' }, { taskId: 's2t2' }, { taskId: 's2t3' }], seen)
  assert.ok(seen.has('s2t1'))
  assert.ok(seen.has('s2t2'))
  assert.ok(seen.has('s2t3'))
  assert.equal(seen.size, 3)
})

test('a re-served group is rejected after its ids are recorded (loop terminates)', () => {
  // Mirrors the loop: record a group, then the same group re-served must trip
  // the guard so the while-loop breaks instead of spinning.
  const seen = new Set()
  const group = [{ taskId: 's2t1' }, { taskId: 's2t2' }]
  assert.equal(firstRepeat(group, seen), null)
  recordSeen(group, seen)
  assert.notEqual(firstRepeat(group, seen), null)
})
