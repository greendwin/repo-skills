---
id: s08t2901
slug: crlfagnostic-content-hashing
status: pending
---

# CR/LF-agnostic content hashing

## Goal

A skill whose working-tree files differ from the repo/blob only in line endings (CRLF vs LF) is reported as *in sync*, not modified. This is the literal reported bug: on Windows, git checks out LF-in-repo files as CRLF in the working tree, so byte-exact hashing/comparison spuriously reports installed copies as modified or out-of-sync.

## Decisions & constraints

- **Normalize in code, not git config or blob OIDs.** Self-contained, works regardless of user git config, covers every comparison path. Rejected `.gitattributes`/`core.autocrlf=false` (fragile, per-user, only our own repos) and blob-OID comparison (invasive, only git-tracked files).
- **Add `normalize_newlines(data: bytes) -> bytes` to `repo_skills/utils.py`.** Full canonicalization: `\r\n`→`\n` then lone `\r`→`\n` (the extra replace is free insurance). Lives in `utils.py` (leaf module, imports only `errors`) so `git_real.py` can import it without a git→config layer dependency.
- **Unconditional — no binary sniffing.** Transformed bytes only ever feed `sha256`, never written to disk, so nothing is corrupted. Only failure mode is an astronomically unlikely missed "modified" for two binaries differing solely in CR bytes. Rejected NUL-byte text/binary detection (heuristic with its own edge cases: UTF-16, stray NULs).
- **Apply at both raw-byte sites:** `compute_file_hashes` (`config/_utils.py` — normalize `read_bytes()` before `sha256`) and `verify_commit_content` (`git_real.py:248` — normalize both `local_file.read_bytes()` and the `git show` blob bytes before comparing).
- **No baseline migration.** No-op on Linux/macOS (values byte-identical to before); Windows was already broken so no valid stored baselines to preserve; normal write ops regenerate baselines.
- `_compute_distance` (`_merge.py`) already normalizes via `read_text()` — leave it; this slice removes the inconsistency on the byte-based paths.

## Edge cases

- Already-LF content → hash unchanged (no-op), so Linux/macOS users see zero difference.
- Lone `\r` (classic-Mac) → normalized to `\n`.
- Binary file containing `0x0D 0x0A` → bytes collapsed only for hashing; the file itself is untouched.

## Key files

- `src/repo_skills/utils.py` — new `normalize_newlines`.
- `src/repo_skills/config/_utils.py` — `compute_file_hashes` uses it.
- `src/repo_skills/git_real.py` — `verify_commit_content` uses it on both sides of the comparison.
- Tests: `tests/test_config.py` (compute_file_hashes), `tests/test_git_real.py` (verify_commit_content), plus a direct unit test for `normalize_newlines` (e.g. in `tests/test_config.py` or a utils test).

## Acceptance criteria

1. `normalize_newlines` maps CRLF, lone CR, mixed, and already-LF inputs all to the LF form; bytes with no line endings pass through untouched.
2. `compute_file_hashes` over two dirs identical except one file is CRLF and the other LF produces equal hash maps.
3. `verify_commit_content` returns `True` when a file is committed with LF in the blob but the working-tree copy is overwritten with CRLF bytes (simulates a Windows autocrlf checkout on Linux CI).
4. `uv run tox` (all environments) is green, including any pre-existing issues.
