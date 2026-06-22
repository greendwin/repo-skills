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
//
// Limitation: the brace-walker is intentionally brace-naive. It counts raw `{`
// and `}` characters with no awareness of strings, template literals, regexes,
// or comments, so it would mis-slice any function that contains a `{` or `}`
// inside such a construct. Extracted helpers must therefore stay "brace-clean"
// (no braces inside strings, templates, regexes, or comments). If that ever
// becomes untenable, the durable fix is to make `grind-story.js` `import()`-able
// rather than text-sliced.
export function extractFunction(name) {
  // Anchor on the declaration, optionally including a leading `async` modifier
  // (with any whitespace) so an async helper keeps its modifier — and its
  // `await`s stay valid — once sliced into a standalone function.
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const decl = new RegExp(`(?:async\\s+)?function ${escaped}\\(`)
  const match = decl.exec(source)
  assert.notEqual(match, null, `function ${name} not found in grind-story.js`)
  const start = match.index
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
