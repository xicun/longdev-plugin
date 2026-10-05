#!/usr/bin/env python3
"""Generic regression catalog runner (Python standard library only).

Writes a verifiable run: `manifest.json` (metadata + per-case results),
`fingerprints.json` (input/output hashes), and per-case stdout/stderr.
A run never overwrites an existing directory. The catalog is supplied by the
caller (a project or the harness parent); this runner carries no project-specific
cases and does not reference any parent repository path.

L03 (evidence binding): `--bind-input <path>` (repeatable) fingerprints explicit
source inputs before and after the run; a mid-run drift is recorded in the
manifest and fails the run. L04: cases run with a configurable timeout
(per-case `timeout_seconds` or `--default-timeout`), stdout/stderr stream to
disk in real time, and the manifest is updated after every case so a hang or
interrupt keeps the already-finished results.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any

RUNNER_VERSION = "1.2"
PROFILES = ("smoke", "full", "failure-probe")
# General traceability kinds. Kept broad so a project or the harness parent can
# reference requirements, acceptance items, test cases/runs and past bugs without
# the runner knowing the concrete semantics.
REF_KINDS = {"requirement", "acceptance", "test_case", "test_run", "bug"}
# Case IDs become path segments under the run directory (run_dir/cases/<id>), so
# they must be a single safe segment: no separators, no traversal, no reserved
# device names. Keeps a naming mistake from writing logs outside the run root.
SAFE_CASE_ID = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL",
                    *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
# 绑定输入/目录遍历时跳过的部分；.work 与运行输出不属于被测源码。
SKIP_PARTS = {"__pycache__", ".git", ".work", "node_modules"}


def safe_case_id(case_id: str) -> bool:
    if not re.fullmatch(SAFE_CASE_ID, case_id) or case_id in {".", ".."}:
        return False
    return case_id.split(".")[0].upper() not in WINDOWS_RESERVED


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


def collect_files(root: Path) -> list[Path]:
    """Expand a bound path (file or directory) into stable file paths."""
    root = Path(root).resolve()
    if root.is_file():
        return [root]
    if not root.is_dir():
        raise RuntimeError(f"bind input does not exist: {root}")
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in SKIP_PARTS for part in p.parts)
    )


def hash_bound_inputs(roots: list[Path]) -> dict[str, str]:
    """Hash bound inputs; keys are relative to each input root (stable across machines)."""
    hashes: dict[str, str] = {}
    for root in roots:
        root = root.resolve()
        for file in collect_files(root):
            name = file.name if root.is_file() else str(file.relative_to(root))
            hashes[name] = sha256(file)
    return hashes


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
        if not safe_case_id(case_id):
            raise CatalogError(
                f"case id must be a single safe path segment (letters, digits, '.', '_', '-'; "
                f"no separators, traversal, or reserved device names): {case_id!r}")
        if case["profile"] not in PROFILES or not isinstance(case["command"], list) or not case["command"]:
            raise CatalogError(f"invalid profile or command for {case_id}")
        if not isinstance(case["cwd"], str) or Path(case["cwd"]).is_absolute() or ".." in Path(case["cwd"]).parts:
            raise CatalogError(f"case cwd must be a relative safe path: {case_id}")
        if not isinstance(case["expected_exit"], int):
            raise CatalogError(f"expected_exit must be an integer: {case_id}")
        if "timeout_seconds" in case and (not isinstance(case["timeout_seconds"], int) or isinstance(case["timeout_seconds"], bool) or case["timeout_seconds"] < 1):
            raise CatalogError(f"timeout_seconds must be a positive integer: {case_id}")
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


def run_cases(catalog_root: Path, source_root: Path, profile: str, case_id: str | None,
              case_list: list[str] | None, output: Path,
              bind_inputs: list[Path] | None = None,
              default_timeout: int | None = None) -> int:
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
        selected = [case for case in cases["cases"] if case["profile"] == profile
                    and (case_id is None or case["id"] == case_id)]
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

    # L03：绑定输入在执行前后各做一次指纹；漂移记录在 manifest 并使本 run 失败。
    bound_roots = [Path(item) for item in (bind_inputs or [])]
    bound_initial = hash_bound_inputs(bound_roots) if bound_roots else {}
    interrupted = False
    manifest: dict[str, Any] = {
        "schema": 1, "runner_version": RUNNER_VERSION, "run_id": run_dir.name,
        "profile": profile, "case_filter": case_id, "started_at": started.isoformat(),
        "finished_at": "", "command": [sys.executable, *sys.argv],
        "environment": {"python": platform.python_version(), "platform": platform.platform(),
                        "cwd": os.getcwd(), "overrides": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}},
        "source_root": str(source_root), "catalog_root": str(catalog_root.resolve()),
        "source_binding": None,
        "cases": results, "interrupted": False, "exit_code": 1,
    }

    try:
        for case in selected:
            case_dir = run_dir / "cases" / case["id"]
            # 纵深防御：即使 catalog 校验放行，派生目录也必须留在 run 根内且不经链接重定向。
            if (os.path.sep in case["id"] or "/" in case["id"] or "\\" in case["id"]
                    or Path(case["id"]).is_absolute()
                    or not case_dir.resolve().is_relative_to(run_dir.resolve())):
                raise CatalogError(f"derived case directory escapes the run root: {case['id']!r}")
            case_dir.mkdir(parents=True)
            command = [str(item) for item in case["command"]]
            timeout = case.get("timeout_seconds", default_timeout)
            started_case = time.monotonic()
            stdout_path = case_dir / "stdout.txt"
            stderr_path = case_dir / "stderr.txt"
            # L04：日志以文件句柄直写，进程边运行边落盘，不等执行完成。
            timed_out = False
            runner_error = None
            actual_exit: int | None = None
            with stdout_path.open("w", encoding="utf-8", newline="\n") as stdout_f, \
                    stderr_path.open("w", encoding="utf-8", newline="\n") as stderr_f:
                try:
                    child_env = os.environ.copy()
                    child_env.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"})
                    completed = subprocess.run(
                        command, cwd=str(source_root / case["cwd"]),
                        env=child_env, stdin=subprocess.DEVNULL,
                        stdout=stdout_f, stderr=stderr_f,
                        timeout=(case.get("timeout_seconds") or default_timeout),
                        check=False)
                    actual_exit = completed.returncode
                except subprocess.TimeoutExpired as exc:
                    runner_error = f"timeout after {timeout} seconds"
                    timed_out = True
                except (OSError, ValueError) as exc:
                    runner_error = str(exc)
                    actual_exit = 2
            passed = runner_error is None and actual_exit == case["expected_exit"]
            results.append({
                "id": case["id"], "title": case["title"], "command": command,
                "cwd": case["cwd"], "expected_exit": case["expected_exit"],
                "actual_exit": actual_exit,
                "passed": passed, "duration_seconds": round(time.monotonic() - started_case, 3),
                "runner_error": runner_error, "timed_out": timed_out,
                "timeout_seconds": timeout,
                "stdout": str(stdout_path.relative_to(run_dir)),
                "stderr": str(stderr_path.relative_to(run_dir)),
                "fingerprints": {"stdout": sha256(stdout_path), "stderr": sha256(stderr_path)},
            })
            # L04：每个 case 完成后立即更新 manifest，挂起/中断保留已完成结果。
            manifest["cases"] = results
            manifest["interrupted"] = False
            write_json(run_dir / "manifest.json", manifest)
    except BaseException:
        # L04：中断（含 KeyboardInterrupt/意外异常）保留部分 manifest 后按原语义抛出。
        interrupted = True
        manifest["interrupted"] = True
        write_json(run_dir / "manifest.json", manifest)
        raise

    fingerprints = {"inputs": {**input_hashes, **(bound_initial or {})}, "outputs": {}}
    for result in results:
        fingerprints["outputs"][result["id"]] = result["fingerprints"]
    write_json(run_dir / "fingerprints.json", fingerprints)
    finished = datetime.now(timezone.utc)
    # L03：执行后复测绑定输入；指纹变化说明被测源码在 run 中途被改动。
    bound_matched = True
    bound_final: dict[str, str] = {}
    if bound_roots:
        bound_final = hash_bound_inputs(bound_roots)
        bound_matched = bound_final == bound_initial
    exit_code = 0 if (all(result["passed"] for result in results) and bound_matched) else 1
    manifest = {
        "schema": 1, "runner_version": RUNNER_VERSION, "run_id": run_dir.name,
        "profile": profile, "case_filter": case_id, "started_at": started.isoformat(),
        "finished_at": finished.isoformat(), "command": [sys.executable, *sys.argv],
        "environment": {"python": platform.python_version(), "platform": platform.platform(), "cwd": os.getcwd(), "overrides": {"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}},
        "source_root": str(source_root), "catalog_root": str(catalog_root.resolve()),
        "source_binding": {
            "roots": [str(item) for item in bound_roots],
            "initial": bound_initial,
            "final": bound_final,
            "matched": bound_matched,
        },
        "cases": results, "interrupted": interrupted, "exit_code": exit_code,
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
    parser.add_argument("--default-timeout", type=int, default=None,
                        help="per-case timeout in seconds applied when the case has no timeout_seconds")
    parser.add_argument("--bind-input", action="append", type=Path, default=[],
                        help="file or directory fingerprinted before/after the run (repeatable)")
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
        bound_roots = [Path(item) for item in (args.bind_input or [])]
        for item in bound_roots:
            collect_files(item)
        return run_cases(args.catalog_root.resolve(), args.source_root, args.profile,
                         args.case, case_list, args.output, bind_inputs=bound_roots,
                         default_timeout=args.default_timeout)
    except CatalogError as exc:
        print(f"catalog error: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"runner error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
