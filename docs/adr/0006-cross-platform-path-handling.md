# Cross-platform (Windows) path handling

## Context

`repo_skills` manipulates filesystem paths pervasively: skills-directory
detection, repo-containment checks, repo-relative normalization of stored
`skills_dirs`, git-root discovery, and merge-target resolution. Much of this
code was written against POSIX assumptions, and during the s08t23 review both
the reviewers and the assistant treated a Windows-only behavioural divergence
(`Path.is_relative_to` being case-insensitive on `WindowsPath`, unlike the
prior case-sensitive `.parts` comparison) as out-of-scope on the grounds that
this is "a Linux project."

That premise is wrong: **Windows is a supported target platform.** Left
unrecorded, the same POSIX-only assumption would keep being reintroduced.

## Decision

Windows is a first-class supported platform. Path handling must not assume
POSIX semantics. Standing rules:

- Manipulate paths through `pathlib.Path`, not string surgery; never hardcode
  `/` (or `\`) as a separator. Stored, comparable values use an explicit
  POSIX normalization (`rel_posix`) so `source.json` is portable across OSes.
- Be deliberate about **case-sensitivity**: POSIX paths are case-sensitive,
  NTFS is case-insensitive, and `Path.is_relative_to` follows the path flavour.
  Any containment/equality check must state the case-semantics it intends.
- Mind `is_absolute()` caveats: a Windows drive-relative path such as `C:foo`
  is **not** absolute, so an `is_absolute()` precondition (e.g. in
  `path_within`) does not by itself guarantee a resolved path.
- Account for drive letters, UNC paths, and symlink-vs-junction resolution when
  reasoning about `.resolve()` and `.parts`.

The concrete audit that brings the existing path-handling surface (discovery,
`cli/_source`, `cli/_merge`, config, manifest) into line with this decision —
including deciding the intended containment case-semantics — is tracked as
task **s16**. Ideally the CI matrix gains a Windows job (or platform-parametrized
tests) so regressions are caught.

## Considered Options

- **Treat the project as Linux-only** and keep POSIX-only assumptions. Rejected:
  Windows is a supported target; this only defers breakage to Windows users.
- **Handle each site ad hoc** as Windows bugs surface. Rejected: cross-platform
  correctness is a cross-cutting concern; a single recorded decision keeps every
  path-manipulation site pulling in the same direction.
