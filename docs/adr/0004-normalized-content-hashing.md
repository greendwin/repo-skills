# Content hashes and stored paths are normalized, not byte/OS-exact

Skill content hashes and the path strings stored in config/manifests are normalized before they are compared: line endings are canonicalized to LF and path separators to POSIX (`/`). Hashes are therefore line-ending-agnostic, and stored/compared paths are OS-agnostic. Any comparison that hashes file bytes (`compute_file_hashes`) or compares working-tree content against a git blob (`verify_commit_content`) must apply this normalization; any path written to config/manifest or compared against git output must be POSIX.

This was driven by Windows: git checks out LF-in-repo files as CRLF in the working tree, and the OS path separator is `\`. Both made identical logical content compare unequal, so installed copies were reported as modified or out-of-sync and skill paths handed to git did not match.

## Considered Options

- **Normalize in code (chosen).** A `normalize_newlines(bytes)` helper feeds `compute_file_hashes` and `verify_commit_content`; a `to_posix(path)` helper (`str(path).replace("\\", "/")`) canonicalizes every stored/compared path. Self-contained, independent of user git config, fixes every comparison path uniformly, and is a no-op on Linux/macOS so no baseline migration is needed.
- **`.gitattributes` / `core.autocrlf=false`.** Fragile: depends on per-user git config and only covers files inside our own repos, not arbitrary registered sources.
- **Compare git blob OIDs instead of hashing bytes.** Invasive and only works for git-tracked files, not installed copies that may not live in a repo.
- **Sniff text vs binary before normalizing line endings.** Rejected in favour of unconditional normalization — the transformed bytes are only ever fed to `sha256` (never written), so nothing is corrupted, and the only failure mode is an astronomically unlikely missed "modified" for two binaries differing solely in CR bytes.

## Consequences

- Normalization is unconditional (all files, no binary detection). It must never write transformed bytes back to disk — it only feeds hashing/comparison.
- Existing baselines self-heal: on Linux/macOS the values are byte-identical to before; Windows was already broken (this bug), so there is no valid stored population to migrate. Normal write operations (`install`/`update`/`merge`) regenerate baselines.
- New byte-level or path comparisons must route through `normalize_newlines` / `to_posix`; introducing a raw `read_bytes()` comparison or a native-`os.sep` path string reintroduces the Windows bug.
