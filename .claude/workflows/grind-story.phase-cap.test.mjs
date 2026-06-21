// Behavior-level tests for `phaseCap` — extracted from grind-story.js via
// _extract-fn.mjs (see that file for why it is sliced rather than imported).
// Pins the cap values and the phase->cap binding. The story's central behavior
// is the split of the old single cap into a smaller Verify cap and a larger
// review/refactor cap; these tests guard against an accidental revert or a loop
// pointing at the wrong cap.

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { extractFunction } from './_extract-fn.mjs'

const phaseCap = extractFunction('phaseCap')

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, 'grind-story.js'), 'utf8')

// Pull the `(cap N)` figure out of a phase's user-facing `meta.phases` detail
// string, so a test can prove the advertised cap matches the real `phaseCap`.
function advertisedCap(phaseTitle) {
  const line = source
    .split('\n')
    .find((l) => l.includes(`title: '${phaseTitle}'`))
  assert.ok(line, `meta.phases entry for ${phaseTitle} not found`)
  const m = line.match(/\(cap (\d+)\)/)
  assert.ok(m, `no "(cap N)" figure in the ${phaseTitle} detail string`)
  return Number.parseInt(m[1], 10)
}

test('the Verify phase caps at 5 rounds', () => {
  assert.equal(phaseCap('Verify'), 5)
})

test('the Review-A phase caps at 10 rounds', () => {
  assert.equal(phaseCap('Review-A'), 10)
})

test('the Refactor-B phase caps at 10 rounds', () => {
  assert.equal(phaseCap('Refactor-B'), 10)
})

test('the review/refactor cap is strictly larger than the verify cap', () => {
  assert.ok(phaseCap('Review-A') > phaseCap('Verify'))
  assert.equal(phaseCap('Review-A'), phaseCap('Refactor-B'))
})

test('an unknown phase has no cap', () => {
  assert.equal(phaseCap('nope'), undefined)
})

test('the Review-A meta detail advertises the real phaseCap', () => {
  assert.equal(advertisedCap('Review-A'), phaseCap('Review-A'))
})

test('the Refactor-B meta detail advertises the real phaseCap', () => {
  assert.equal(advertisedCap('Refactor-B'), phaseCap('Refactor-B'))
})
