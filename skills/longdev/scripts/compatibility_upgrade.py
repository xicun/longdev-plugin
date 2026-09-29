"""Preserve one explicitly selected task using an immutable compatibility snapshot.

This CLI never rewrites task records or adopts a new workflow on their behalf.
Run at a handoff with the task writer stopped. The workspace lock coordinates
migration tools, not arbitrary editors; changed inputs are detected before publish.
An existing snapshot without its local journal is preserved as unverifiable;
the CLI never recreates that journal from the snapshot it is meant to verify.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile

from history_convergence import tracked
from workspace_common import atomic_write, digest, ignored, migration_lock, redirected, safe


SCHEMA = 1
PROFILE = "requirements-design-v1"
SIDECAR = "COMPATIBILITY.json"
JOURNAL = ".work/longdev-migration/compatibility"
ACTIVE = {"待执行", "执行中", "待检查", "待最终检查", "待报告", "检查通过", "待验收",
          "待用户验收", "受阻", "暂停", "预算停止", "候选耗尽", "in progress", "pending", "blocked"}
TERMINAL = {"已验收", "已完成", "目标达成", "已取消", "已终止", "accepted", "completed", "cancelled"}


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _json(path):
    try:
        value = json.loads(path.read_text("utf-8"))
    except (UnicodeError, ValueError) as error:
        raise ValueError("Unrecognized JSON: " + str(path)) from error
    if not isinstance(value, dict):
        raise ValueError("JSON object required: " + str(path))
    return value


def _status_text(text):
    # 只识别独立且完整的状态值；不能把“未完成”或正文提到“已验收”当作终态。
    values = re.findall(
        r"(?im)^\s*(?:\*\*)?(?:状态|任务状态|执行状态|验收状态|status)(?:\*\*)?\s*[：:]\s*([^\n]+)",
        text,
    )
    values = {v.strip().strip("*").strip().lower() for v in values}
    if len(values) != 1:
        return "unknown"
    value = next(iter(values))
    # 括号或后缀可能包含“待验收”等限定，不能当作无关说明丢掉。
    return value if value in ACTIVE | TERMINAL else "unknown"


def _source_text(raw, task):
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeError as error:
        raise ValueError("Unknown task encoding; preserve for review: " + task) from error
    # 本适配器仅识别无格式声明的 Markdown；不能把未来格式标签忽略后
    # 宣称兼容。无需解释未知格式内容，保留原文交给对应版本处理。
    declaration = re.search(
        r'(?im)^\s*(?:[-*]\s+)?(?:\*\*)?["\x27]?'
        r'(?:schema(?:_version)?|record_schema|record_format|record_format_version|'
        r'workflow_profile|workflow_version|adopted_workflow)'
        r'["\x27]?(?:\*\*)?\s*[：:]', text,
    )
    if declaration:
        raise ValueError("Declared task schema/profile is not supported by the unversioned adapter; preserve for review: " + task)
    return text


def _plugin_version():
    manifest = Path(__file__).resolve().parents[3] / ".codex-plugin/plugin.json"
    if not manifest.is_file():
        return "unknown"
    return str(_json(manifest).get("version", "unknown"))


def _paths(root, task):
    parts = PurePosixPath(task).parts
    if len(parts) != 3 or parts[0] != "docs" or parts[1] not in {"longdev", "autopilot"} or parts[2] == "archive":
        raise ValueError("Select one task: docs/longdev/<id> or docs/autopilot/<id>")
    folder = safe(root, task)
    main = folder / ("CHARTER.md" if parts[1] == "autopilot" else "PLAN.md")
    safe(root, main.relative_to(root).as_posix())
    if not main.is_file():
        raise ValueError("Task entry missing: " + str(main))
    return main, task + "/" + SIDECAR, JOURNAL + "/" + digest(task.encode()) + ".json"


def _validate_receipt(value, task):
    if (type(value.get("schema")) is not int or value.get("schema") != SCHEMA
            or value.get("workflow_profile") != PROFILE
            or value.get("task") != task or value.get("adoption") != "legacy-preserved"
            or value.get("semantic_rewrite") is not False
            or value.get("adopted_workflow") != "unchanged"
            or not isinstance(value.get("source_sha256"), dict) or not value["source_sha256"]):
        raise ValueError("Unknown or inconsistent compatibility receipt; preserve for review: " + task)
    main = task + ("/CHARTER.md" if task.startswith("docs/autopilot/") else "/PLAN.md")
    if main not in value["source_sha256"] or any(
            key not in {main, task + "/notes/analysis-design.md"}
            or not isinstance(hash_value, str) or not re.fullmatch(r"[0-9a-f]{64}", hash_value)
            for key, hash_value in value["source_sha256"].items()):
        raise ValueError("Invalid snapshot paths or hashes: " + task)


def _receipt(root, task, main):
    raw = main.read_bytes()
    text = _source_text(raw, task)
    status = _status_text(text)
    if status not in ACTIVE | TERMINAL:
        raise ValueError("Unknown or ambiguous task status; preserve for review: " + task)
    if status in TERMINAL:
        return None
    hashes = {main.relative_to(root).as_posix(): digest(raw)}
    design = safe(root, task + "/notes/analysis-design.md")
    if design.is_file():
        hashes[design.relative_to(root).as_posix()] = digest(design.read_bytes())
    return {
        "schema": SCHEMA,
        "created_by_plugin_version": _plugin_version(),
        "workflow_profile": PROFILE,
        "source_version": "unknown",
        "source_record_format": "unversioned-markdown",
        "task": task,
        "record_kind": PurePosixPath(task).parts[1],
        "adoption": "legacy-preserved",
        "adopted_workflow": "unchanged",
        "source_sha256": hashes,
        "status_snapshot": status,
        "resume_policy": "inspect_current_records_at_handoff",
        "design_state": "present_unverified" if design.is_file() else "reuse_existing_records_or_assess_gap",
        "semantic_rewrite": False,
        "upgrade_note": "不可变初始快照；不代表当前状态、设计通过、流程采纳或证据验收。",
    }


def _pending(root, task, target, journal_path):
    path = safe(root, journal_path)
    if not path.exists():
        return None
    journal = _json(path)
    if (type(journal.get("schema")) is not int or journal.get("schema") != SCHEMA
            or journal.get("task") != task
            or journal.get("target") != target or journal.get("state") not in {"applying", "complete"}):
        raise ValueError("Unknown compatibility journal; preserve for review: " + task)
    receipt = journal.get("receipt")
    if not isinstance(receipt, dict):
        raise ValueError("Invalid compatibility journal receipt: " + task)
    _validate_receipt(receipt, task)
    if journal.get("sha256") != digest(_encode(receipt)):
        raise ValueError("Changed compatibility journal: " + task)
    if journal["state"] == "complete":
        published = safe(root, target)
        if not published.is_file():
            raise ValueError("Completed compatibility output is missing; preserve for review: " + target)
        if published.read_bytes() != _encode(receipt):
            raise ValueError("Completed compatibility output differs from its journal; preserve for review: " + target)
        # 校验的是不可变初始快照，不能拿当前业务源哈希阻止其正常演进。
        return None
    return journal


def _verify_sources(root, receipt):
    for relative, expected in receipt["source_sha256"].items():
        source = safe(root, relative)
        if not source.is_file() or digest(source.read_bytes()) != expected:
            raise ValueError("Source changed during compatibility upgrade; preserve pending transaction: " + relative)


def build_plan(project, task=None):
    root = Path(project).absolute()
    if not root.is_dir() or any(redirected(p) for p in [root, *root.parents]):
        raise ValueError("Workspace must be an existing real directory")
    report = {"schema": SCHEMA, "profile": PROFILE, "actions": [], "outputs": {},
              "tracking_pending": [], "summary": {"tasks": 0, "created": 0, "pending": 0, "conflicts": 0}}
    if task is None:
        report["status"] = "not_selected"
        return report
    try:
        main, target, journal_path = _paths(root, task)
        _source_text(main.read_bytes(), task)
        existing = safe(root, target)
        journal = _pending(root, task, target, journal_path)
        if journal:
            receipt = journal["receipt"]
            data = _encode(receipt)
            if existing.exists():
                if existing.read_bytes() != data:
                    raise ValueError("Compatibility target changed during interrupted upgrade: " + target)
            else:
                _verify_sources(root, receipt)
                report["outputs"][target] = data
            action = "recover"
            report["journal"] = journal
        elif existing.exists():
            _validate_receipt(_json(existing), task)
            if not safe(root, journal_path).is_file():
                raise ValueError("Compatibility snapshot has no local journal; integrity is unverifiable, preserve for review: " + target)
            action = "unchanged"
        else:
            receipt = _receipt(root, task, main)
            action = "create" if receipt else "preserve_terminal"
            if receipt:
                report["outputs"][target] = _encode(receipt)
                report["journal"] = {"schema": SCHEMA, "task": task, "target": target,
                                     "state": "applying", "receipt": receipt,
                                     "sha256": digest(_encode(receipt))}
        if report["outputs"]:
            blocked = ignored(root, list(report["outputs"]))
            if blocked:
                raise ValueError("Compatibility outputs ignored: " + json.dumps(blocked, ensure_ascii=False))
        report["actions"] = [{"task": task, "target": target, "action": action}]
        if action != "preserve_terminal":
            report["tracking_pending"] = tracked(root, [target], report["outputs"])
        report["summary"].update(tasks=1, created=len(report["outputs"]), pending=int(action in {"create", "recover"}))
        report["status"] = "pending" if report["summary"]["pending"] else "current"
    except (OSError, ValueError) as error:
        report["outputs"] = {}
        report.pop("journal", None)
        report["actions"] = [{"task": task, "action": "conflict", "reason": str(error)}]
        report["summary"].update(tasks=1, created=0, pending=0, conflicts=1)
        report["status"] = "needs_review"
    return report


def _public(report):
    result = dict(report)
    result["output_files"] = sorted(result.pop("outputs", {}))
    result.pop("journal", None)
    return result


def _publish_new(root, target, data):
    # 同卷临时文件 + 硬链接发布：目标已存在时失败，永远不替换用户文件。
    path = safe(root, target)
    fd, temporary = tempfile.mkstemp(prefix="receipt-", dir=safe(root, ".work/longdev-migration"))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        os.unlink(temporary)


def upgrade(project, check=False, dry_run=False, task=None):
    root = Path(project).absolute()
    report = build_plan(root, task)
    if check or dry_run:
        report["mode"] = "dry_run" if dry_run else "check"
        return _public(report)
    if not report["summary"]["pending"]:
        return _public(report)
    with migration_lock(root):
        report = build_plan(root, task)
        if not report["summary"]["pending"]:
            return _public(report)
        journal = report["journal"]
        journal_path = _paths(root, task)[2]
        if not safe(root, journal_path).exists():
            atomic_write(root, journal_path, _encode(journal))
        elif _pending(root, task, journal["target"], journal_path) != journal:
            raise ValueError("Compatibility journal changed after inventory")
        for target, data in report["outputs"].items():
            _verify_sources(root, journal["receipt"])
            _publish_new(root, target, data)
        if safe(root, journal["target"]).read_bytes() != _encode(journal["receipt"]):
            raise ValueError("Compatibility output verification failed")
        atomic_write(root, journal_path, _encode({**journal, "state": "complete"}))
        report["status"] = "upgraded"
    return _public(report)


def exit_code(report, readonly=False):
    if report["status"] == "needs_review":
        return 2
    return int(readonly and bool(report["summary"]["pending"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task", required=True, help="Selected project-relative task directory")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        report = upgrade(args.project, args.check, args.dry_run, args.task)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return exit_code(report, args.check or args.dry_run)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
