# Checks catalog schema

`check_runner.py` is a generic, stdlib-only runner. It reads a catalog from
`--catalog-root` and runs each case against `--source-root`. The catalog is
supplied by the caller (a project or the harness parent); the runner carries no
project-specific data and does not reference any parent repository path.

## Catalog files

Under `--catalog-root` there must be three JSON files, all `schema: 1`:

### `cases.json`
```json
{
  "schema": 1,
  "cases": [
    {
      "id": "case-id",
      "title": "human title",
      "profile": "smoke",
      "command": ["py", "-3.12", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "cwd": ".",
      "expected_exit": 0,
      "source": "short provenance of this case",
      "quality_refs": ["requirement:R-1", "test_case:T-1"]
    }
  ]
}
```

Per-case fields:
- `id`: unique, nonempty string.
- `profile`: one of `smoke`, `full`, `failure-probe`.
- `command`: nonempty list of strings.
- `cwd`: relative, safe path (no absolute/`..`).
- `expected_exit`: integer.
- `source`: free text provenance.
- `quality_refs`: list of keys of the form `<kind>:<id>` present in `quality_refs.json`.

### `matrix.json`
```json
{ "schema": 1, "profiles": { "smoke": ["case-id"], "full": ["case-id"], "failure-probe": [] } }
```
`environments` is optional metadata about verified/unverified run platforms. `smoke`, `full` and `failure-probe` must all be present; each profile's case list
exactly matches the cases whose `profile` equals that profile.

### `quality_refs.json`
```json
{ "schema": 1, "references": [ { "kind": "requirement", "id": "R-1", "reference": "link" } ] }
```
`kind` must be one of `requirement`, `acceptance`, `test_case`, `test_run`, `bug`.
`reference` is a traceability pointer (document/provenance) and must be nonempty.

## Library & subset

`<项目>/testcases/` is the project-level **shared library**: all tasks in the
project reference subsets of it rather than copying cases. A task records which
case ids it uses, and runs them with `--cases <id,id>` (comma-separated). This
keeps cases reusable and convergent, and keeps harness/plugin development cases
out of a consuming project's library.
## Output

Each run lands in a unique directory under `--output`, never overwriting an
existing run. It contains:
- `manifest.json`: schema, runner version, run metadata, per-case results.
- `fingerprints.json`: input catalog hashes and per-case stdout/stderr hashes.
- `cases/<id>/stdout.txt` and `stderr.txt`.

`--validate` only checks the catalog and writes nothing.