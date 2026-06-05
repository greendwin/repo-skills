---
id: s08t29
slug: windows-support
status: pending
---

# Windows support

On Windows, the CLI's content-hash and path comparisons are byte/OS-exact, so they break. Git checks out LF-in-repo files as CRLF in the working tree, and the OS path separator is `\`. Both make identical logical content compare unequal: installed copies are reported as modified or out-of-sync, and skill paths handed to git (`ls-tree`/`ls-files`) don't match. Goal: make content hashing line-ending-agnostic and make stored/compared paths OS-agnostic, so the tool works on Windows. The change is a no-op on Linux/macOS.

## Context

The CLI hashes skill file bytes (`compute_file_hashes`) and compares working-tree content against git blobs (`verify_commit_content`) to detect modifications and sync state. It also builds path strings (skill `rel_path`, `skills_dir`, hash-map keys, the working-file set in `verify_commit_content`) using the native OS separator. On Windows, CRLF working-tree bytes and `\` separators make all of these comparisons spuriously fail. `_compute_distance` already normalizes via `read_text()`, so the codebase is internally inconsistent.

## Decisions

- **Normalize in code, not via git config or blob OIDs** — a self-contained fix that works regardless of user git config and covers every comparison path. *Rejected: `.gitattributes`/`core.autocrlf=false` (fragile, per-user config, only covers our own repos not arbitrary sources); comparing git blob OIDs (invasive, only works for git-tracked files, breaks for installed copies not in a repo).*
- **Unconditional line-ending normalization — no binary sniffing** — transformed bytes are only ever fed to `sha256` (never written to disk), so nothing is corrupted; the only failure mode is an astronomically unlikely missed "modified" for two binaries differing solely in CR bytes. *Rejected: NUL-byte text/binary detection (adds a heuristic with its own edge cases — UTF-16, stray NULs — to guard a practically impossible case).*
- **Full line-ending canonicalization** — `\r\n`→`\n` then lone `\r`→`\n`, via a shared `normalize_newlines(data: bytes) -> bytes` helper. The extra `replace` is free insurance and makes hashing fully line-ending-agnostic.
- **POSIX is the path invariant** — any path stored in config/manifest or compared against git output is forward-slash, via a shared `to_posix(path) -> str` helper. Fixes hash keys, manifest portability, and git interop together. *Rejected: converting only at the git boundary (leaves hash-key and config-portability bugs unfixed, scatters conversions across every git call site).*
- **`to_posix` is `str(path).replace("\\", "/")`** — the only implementation that is both production-correct on Windows and deterministically testable on Linux CI. *Rejected: `PurePath.as_posix()` (on Linux, `Path("skills\\tdd").as_posix()` leaves the backslash untouched, so it can't be exercised by a plain test on Linux and behaves differently for str/PurePosixPath/PureWindowsPath inputs).*
- **Helpers live in `repo_skills/utils.py`** — a leaf module (imports only `errors`), so `git_real.py` can use them without introducing a git→config layer dependency.
- **No baseline migration** — the change is a no-op on Linux/macOS (values byte-identical to before); Windows was already broken (this bug), so there's no valid stored population to preserve. Normal write operations (`install`/`update`/`merge`) regenerate baselines. *Rejected: manifest version bump + recompute (disproportionate machinery for an already-broken population; manifest-version handling is separately tracked by s08t18).*
- **ADR recorded** — `docs/adr/0004-normalized-content-hashing.md` captures the invariant (hashes/paths are normalized, not byte/OS-exact) and the rejected alternatives, to guard against a future contributor reintroducing the bug via a raw `read_bytes()` or native-`os.sep` comparison.

## Open questions

- None outstanding.

## Out of scope

- CONTEXT.md glossary changes — line-ending/separator normalization is implementation detail, not domain vocabulary; "Baseline hashes" stays as-is.
- Manifest versioning/migration — tracked separately by s08t18.
- Any Windows issues beyond CR/LF and path separators (e.g. path-length limits, case-insensitivity) — not surfaced by this bug.

## Subtasks

- [ ] [s08t2901](s08t2901-crlfagnostic-content-hashing.md): CR/LF-agnostic content hashing
- [ ] [s08t2902](s08t2902-posixcanonical-paths.md): POSIX-canonical paths
