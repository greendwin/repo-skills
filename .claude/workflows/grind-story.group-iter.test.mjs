// Behavior-level tests for `runGroup` — extracted from grind-story.js via
// _extract-fn.mjs (see that file for why it is sliced rather than imported).
// Pins the group-iteration contract: a per-member skip abandons only that
// member (the rest of the group still runs), a halt stops the group and is
// returned to the caller, and any unclassified error propagates. This guards
// the batch-refactor case where a mid-group skip must not strand its siblings.

import test from 'node:test'
import assert from 'node:assert/strict'
import { extractFunction } from './_extract-fn.mjs'

const runGroup = extractFunction('runGroup')

test('a clean group runs every member and returns null', async () => {
  const processed = []
  const processOne = async (item) => { processed.push(item) }
  const classify = () => 'rethrow'
  const halted = await runGroup([1, 2, 3], processOne, classify)
  assert.equal(halted, null)
  assert.deepEqual(processed, [1, 2, 3])
})

test('a skip on a middle member still runs the later members', async () => {
  const processed = []
  const processOne = async (item) => {
    if (item === 2) throw { kind: 'skip' }
    processed.push(item)
  }
  const classify = (e) => e.kind
  const halted = await runGroup([1, 2, 3], processOne, classify)
  assert.equal(halted, null)
  assert.deepEqual(processed, [1, 3])
})

test('a halt stops the group and returns the offending error', async () => {
  const processed = []
  const boom = { kind: 'halt', failure: 'boom' }
  const processOne = async (item) => {
    if (item === 2) throw boom
    processed.push(item)
  }
  const classify = (e) => e.kind
  const halted = await runGroup([1, 2, 3], processOne, classify)
  assert.equal(halted, boom)
  assert.deepEqual(processed, [1])
})

test('an unclassified error propagates', async () => {
  const boom = new Error('unexpected')
  const processOne = async () => { throw boom }
  const classify = () => 'rethrow'
  await assert.rejects(() => runGroup([1, 2], processOne, classify), boom)
})
