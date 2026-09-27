#!/usr/bin/env python3
"""Generic regression catalog runner (Python standard library only).

Runs a catalog of cases from `--catalog-root` against a source root and writes
a verifiable run: `manifest.json` (metadata + per-case results), `fingerprints.json`
(input/output hashes), and per-case stdout/stderr. A run never overwrites an
existing directory. The catalog is supplied by the caller (a project or the
harness parent); this runner carries no project-specific cases and does not
reference any parent repository path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

RUNNER_VERSION = "1.1"
PROFILES = ("smoke", "full", "failure-probe")
# General traceability kinds. Kept broad so a project or the harness parent can
# reference requirements, acceptance items, test cases/runs and past bugs without
# the runner knowing the concrete semantics.
REF_KINDS = {"requirement", "acceptance", "test_case", "test_run", "bug"}


class CatalogError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot read {path}: {exc}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_catalog(catalog_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    cases = load_json(catalog_root / "cases.json")
    matrix = load_json(catalog_root / "matrix.json")
    refs = load_json(catalog_root / "quality_refs.json")
    if cases.get("schema") != 1 or not isinstance(cases.get("cases"), list):
        raise CatalogError("cases.json must have schema 1 and a cases list")
    if matrix.get("schema") != 1 or not isinstance(matrix.get("profiles"), dict):
        raise CatalogError("matrix.json must have schema 1 and profiles")
    if refs.get("schema") != 1 or not isinstance(refs.get("references"), list):
        raise CatalogError("quality_refs.json must have schema 1 and references")

    ref_map: dict[str, dict[str, Any]] = {}
    for ref in refs["references"]:
        if not isinstance(ref, dict) or ref.get("kind") not in REF_KINDS or not ref.get("id") or not ref.get("reference"):
            raise CatalogError(f"invalid quality reference: {ref!r}")
        key = f"{ref['kind']}:{ref['id']}"
        if key in ref_map:
            raise CatalogError(f"duplicate quality reference: {key}")
        ref_map[key] = ref

    case_map: dict[str, dict[str, Any]] = {}
    for case in cases["cases"]:
        if not isinstance(case, dict):
            raise CatalogError("each case must be an object")
        required = ("id", "title", "profile", "command", "cwd", "expected_exit", "source", "quality_refs")
        if any(key not in case for key in required):
            raise CatalogError(f"case is missing a required field: {case!r}")
        case_id = case["id"]
        if not isinstance(case_id, str) or not case_id or case_id in case_map:
            raise CatalogError(f"case IDs must be unique nonempty strings: {case_id!r}")
        if case["profile"] not in PROFILES or not isinstance(case["command"], list) or not case["command"]:
            raise CatalogError(f"invalid profile or command for {case_id}")
        if not isinstance(case["cwd"], str) or Path(case["cwd"]).is_absolute() or ".." in Path(case["cwd"]).parts:
            raise CatalogError(f"case cwd must be a relative safe path: {case_id}")
        if not isinstance(case["expected_exit"], int):
            raise CatalogError(f"expected_exit must be an integer: {case_id}")
        if not isinstance(case["quality_refs"], list) or any(ref not in ref_map for ref in case["quality_refs"]):
            raise CatalogError(f"quality_refs are missing from quality_refs.json: {case_id}")
        case_map[case_id] = case

    for profile, ids in matrix["profiles"].items():
        if profile not in PROFILES or not isinstance(ids, list) or any(case_id not in case_map for case_id in ids):
            raise CatalogError(f"matrix profile contains unknown or invalid cases: {profile}")
        expected = {case_id for case_id, case in case_map.items() if case["profile"] == profile}
        if set(ids) != expected:
            raise CatalogError(f"matrix profile does not match case profiles: {profile}")
    if set(matrix["profiles"]) != set(PROFILES):
        raise CatalogError("matrix must define smoke, full and failure-probe profiles")
    return cases, matrix, refs


def unique_output(base: Path) -> Path:
    if not base.exists():
        return base
    if not (base / "manifest.json").exists() and not any(base.iterdir()):
        return base
    for index in range(1, 10000):
        candidate = base.with_name(f"{base.name}-{index:03d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot allocate an unused output directory near {base}")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def run_cases(catalog_root: Path, source_root: Path, profile: str, case_id: str | None, case_list: list[str] | None, output: Path) -> int:
    cases, _matrix, _refs = validate_catalog(catalog_root)
    if case_list is not None:
        wanted = set(case_list)
        known = {case["id"] for case in cases["cases"]}
        missing = sorted(wanted - known)
        if missing:
            raise CatalogError(f"unknown case ids: {missing}")
        selected = [case for case in cases["cases"] if case["id"] in wanted]
        if not selected:
            raise CatalogError("no selected cases")
    else:
        selected = [case for case in cases["cases"] if case["profile"] == profile and (case_id is None or case["id"] == case_id)]
        if case_id is not None and not selected:
            raise CatalogError(f"case {case_id!r} is not in profile {profile!r}")
        if not selected:
            raise CatalogError(f"profile {profile!r} has no selected cases")
    source_root = source_root.resolve()
    run_dir = unique_output(output.resolve())
    run_dir.mkdir(parents=True)
    started = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    input_hashes: dict[str, str] = {}
    for catalog_file in ("cases.json", "matrix.json", "quality_refs.json"):
        input_hashes[f"catalog/{catalog_file}"] = sha256(catalog_root / catalog_file)

    for case in selected:
        case_dir = run_dir / "cases" / case["id"]
        case_dir.mkdir(parents=True)
        cwd = source_root / case["cwd"]
        command = [str(item) for item in case["command"]]
        started_case = time.monotonic()
        try:
            child_env = os.environ.copy()
            child_env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
            completed = subprocess.run(command, cwd=str(cwd), env=child_env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
            actual_exit = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            runner_error = None
        except (OSError, ValueError) as exc:
            actual_exit = 2
            stdout = ""
            stderr = f"runner error: {exc}\n"
            runner_error = str(exc)
        stdout_path = case_dir / "stdout.txt"
        stderr_path = case_dir / "stderr.txt"
        stdout_path.write_text(stdout, encoding="utf-8", newline="\n")
        stderr_path.write_text(stderr, encoding="utf-8", newline="\n")
        passed = runner_error is None and actual_exit == case["expected_exit"]
        results.append({
            "id": case["id"], "title": case["title"], "command": command,
            "cwd": str(cwd), "expected_exit": case["expected_exit"], "actual_exit": actual_exit,
            "passed": passed, "duration_seconds": round(time.monotonic() - started_case, 3),
            "runner_error": runner_error, "stdout": str(stdout_path.relative_to(run_dir)),
            "stderr": str(stderr_path.relative_to(run_dir)),
            "fingerprints": {"stdout": sha256(stdout_path), "stderr": sha256(stderr_path)},
        })

    fingerprints = {"inputs": input_hashes, "outputs": {}}
    for result in results:
        fingerprints["outputs"][result["id"]] = result["fingerprints"]
    write_json(run_dir / "fingerprints.json", fingerprints)
    finished = datetime.now(timezone.utc)
    exit_code = 0 if all(result["passed"] for result in results) else 1
    manifest = {
        "schema": 1, "runner_version": RUNNER_VERSION, "run_id": run_dir.name,
        "profile": profile, "case_filter": case_id, "started_at": started.isoformat(),
        "finished_at": finished.isoformat(), "command": [sys.executable, *sys.argv],
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "cwd": os.getcwd(), "overrides": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}},
        "source_root": str(source_root), "catalog_root": str(catalog_root.resolve()),
        "cases": results, "exit_code": exit_code,
    }
    write_json(run_dir / "manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir), "profile": profile, "cases": len(results), "exit_code": exit_code}, ensure_ascii=False))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--profile", choices=PROFILES)
    parser.add_argument("--case")
    parser.add_argument("--cases", help="comma-separated case ids to run (a task-subset)")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args(argv)
    try:
        validate_catalog(args.catalog_root.resolve())
        if args.validate:
            print("catalog validation passed")
            return 0
        case_list = None
        if args.cases:
            case_list = [item.strip() for item in args.cases.split(",") if item.strip()]
        if case_list is None and not args.profile:
            parser.error("--profile is required unless --cases is used")
        if args.output is None:
            parser.error("--output is required for a run")
        case_id = args.case
        return run_cases(args.catalog_root.resolve(), args.source_root, args.profile, case_id, case_list, args.output)
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"runner error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())