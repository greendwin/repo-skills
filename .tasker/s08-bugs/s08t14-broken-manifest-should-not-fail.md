---
id: s08t14
slug: broken-manifest-should-not-fail
status: done
---

# Broken manifest should not fail

```
$ skills status
Error: 1 validation error for _SkillManifestConfig
  Invalid JSON: EOF while parsing a value at line 1 column 0 [type=json_invalid, input_value='', input_type=str]
    For further information visit https://errors.pydantic.dev/2.13/v/json_invalid
```

When manifest is broken -- we should report error but continue
