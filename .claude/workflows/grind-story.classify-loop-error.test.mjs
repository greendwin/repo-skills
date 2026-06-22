// Behavior-level tests for `classifyLoopError` — extracted from grind-story.js
// via _extract-fn.mjs (see that file for why it is sliced rather than imported).
// Pins the mapping from the loop's control-flow sentinels to the vocabulary
// `runGroup` consumes: a skip member abandons only itself, a halt stops the run,
// and anything else propagates. A regression that swaps these or typos a literal
// would otherwise pass every other suite while silently breaking the loop.
//
// The classifier reads a `loopAction` discriminant the real `Halt`/`SkipItem`
// sentinels set on themselves. That sentinel-sets-discriminant wiring is the one
// atom the text-slice seam can't reach (the `class` declarations aren't pulled
// into the slice), so we exercise the classifier against plain objects carrying
// the same discriminant — the durable fix being an import()-able source, already
// noted in _extract-fn.mjs.

import test from 'node:test'
import assert from 'node:assert/strict'
import { extractFunction } from './_extract-fn.mjs'

const classifyLoopError = extractFunction('classifyLoopError')

test('a value carrying the skip discriminant classifies as skip', () => {
  assert.equal(classifyLoopError({ loopAction: 'skip' }), 'skip')
})

test('a value carrying the halt discriminant classifies as halt', () => {
  assert.equal(classifyLoopError({ loopAction: 'halt', failure: 'boom' }), 'halt')
})

test('a plain Error classifies as rethrow', () => {
  assert.equal(classifyLoopError(new Error('unexpected')), 'rethrow')
})

test('null and undefined classify as rethrow', () => {
  assert.equal(classifyLoopError(null), 'rethrow')
  assert.equal(classifyLoopError(undefined), 'rethrow')
})

test('a defined-but-unrecognized discriminant classifies as rethrow', () => {
  assert.equal(classifyLoopError({ loopAction: 'pause' }), 'rethrow')
})
