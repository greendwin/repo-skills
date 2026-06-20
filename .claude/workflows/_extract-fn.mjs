// Shared test harness: extract a pure top-level helper from `grind-story.js`.
//
// `grind-story.js` is loaded by the harness as a function body (it ends in a
// top-level `return`), so it cannot be imported directly. Behavior-level test
// suites instead slice a named `function <name>(...) { ... }` out of the source
// by name and evaluate it in isolation, binding to the real shipped
// implementation rather than a copy. This module is not a `*.test.mjs` file, so
// the Python suite glob never collects it as a test.

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, 'grind-story.js'), 'utf8')

// Slice a top-level `function <name>(...) { ... }` out of the source by walking
// balanced braces from its declaration, so the test binds to the real shipped
// implementation rather than a copy.
export function extractFunction(name) {
  const start = source.indexOf(`function ${name}(`)
  assert.notEqual(start, -1, `function ${name} not found in grind-story.js`)
  let depth = 0
  let i = source.indexOf('{', start)
  for (; i < source.length; i++) {
    if (source[i] === '{') depth++
    else if (source[i] === '}' && --depth === 0) break
  }
  const body = source.slice(start, i + 1)
  // eslint-disable-next-line no-new-func
  return new Function(`${body}\nreturn ${name}`)()
}
