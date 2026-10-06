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
      "id": "case-smoke-1",
      "title": "human title",
      "profile": "smoke",
      "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "cwd": ".",
      "expected_exit": 0,
      "source": "short provenance of this case",
      "quality_refs": ["requirement:R-1", "test_case:T-1"]
    },
    {
      "id": "case-full-1",
      "title": "full regression case",
      "profile": "full",
      "command": ["python3", "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
      "cwd": ".",
      "expected_exit": 0,
      "source": "short provenance of this case",
      "quality_refs": ["requirement:R-1"]
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
- `timeout_seconds`: optional positive integer (L04). When present it overrides
  `--default-timeout` for this case; a case that exceeds it fails with
  `timed_out: true` and its partial stdout/stderr are still on disk.
- `source`: free text provenance.
- `quality_refs`: list of keys of the form `<kind>:<id>` present in `quality_refs.json`.
  Reference ids are unique across the whole project library, but different tasks
  commonly number their requirements `R01`/`V01` from scratch. Keep the task's own
  numbering in its documents and register library entries with a scoped id
  `<scope>/<编号>` (for example `requirement:task-a/R01`, `requirement:task-b/R01`);
  the runner keys uniqueness on `kind:id`, so scoped entries from different tasks
  coexist and one case may reference both.

### Profiles (semantics)

Profiles are **mutually exclusive groups**, not nested suites. Every case
belongs to exactly one profile, and `matrix.json` must mirror that grouping
exactly. Running `--profile full` executes only the `full` group — it does
**not** automatically include the `smoke` cases. To run smoke plus full in one
run, pass the union of case ids via `--cases <smoke-ids,full-ids>`; `--cases`
is not restricted to a single profile.

### `matrix.json`
```json
{ "schema": 1, "profiles": { "smoke": ["case-smoke-1"], "full": ["case-full-1"], "failure-probe": [] } }
```
`environments` is optional metadata about verified/unverified run platforms. `smoke`, `full` and `failure-probe` must all be present; each profile's case list
exactly matches the cases whose `profile` equals that profile.

### `quality_refs.json`
```json
{
  "schema": 1,
  "references": [
    { "kind": "requirement", "id": "R-1", "reference": "link" },
    { "kind": "test_case", "id": "T-1", "reference": "link" }
  ]
}
```
`kind` must be one of `requirement`, `acceptance`, `test_case`, `test_run`, `bug`.
`reference` is a traceability pointer (document/provenance) and must be nonempty.

## Library & subset

`<项目>/testcases/` is the project-level **shared library**: all tasks in the
project reference subsets of it rather than copying cases. A task records which
case ids it uses, and runs them with `--cases <id,id>` (comma-separated). This
keeps cases reusable and convergent, and keeps harness/plugin development cases
out of a consuming project's library.

## Timeouts & streaming (L04)

- `--default-timeout <seconds>` applies to every case without its own
  `timeout_seconds`; a case without either has no timeout (use deliberately).
- stdout/stderr are written through open file handles, so output lands on disk
  while the child runs — a hang or interrupt still leaves the logs.
- `manifest.json` is rewritten after every case and again on interrupt
  (`interrupted: true`), so finished results survive a killed run.

## Source binding (L03)

`--bind-input <path>` (repeatable) fingerprints an explicit source file or
directory (recursively; `__pycache__`, `.git`, `.work`, `node_modules` are
skipped) before and after the run. Hashes are keyed by path relative to each
input root. The run records `source_binding` (`initial`/`final`/`matched`) in
`manifest.json` and merges the input hashes into `fingerprints.json`. A drift
(`matched: false`) fails the run even when every case passed.

## Write lease (cross-worktree)

- Editing the shared library must hold the `testcases` write lease: `.../skills/longdev/scripts/write_lease.py acquire --project <project> --resource testcases` before writing, and `release --token <token>` after. The lock lives under the Git common dir so worktrees of the same repo serialize instead of silently conflicting. Bug archives already use `docs/bugs/.write.lock`.
## Output

Each run lands in a unique directory under `--output`, never overwriting an
existing run. It contains:
- `manifest.json`: schema, runner version, run metadata, per-case results,
  `source_binding` (null when no `--bind-input`), `interrupted`, `exit_code`.
- `fingerprints.json`: input hashes (catalog files + bound inputs) and per-case
  stdout/stderr hashes.
- `cases/<id>/stdout.txt` and `stderr.txt`.

`--validate` only checks the catalog and writes nothing.