import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/longdev/scripts"
sys.path.insert(0, str(SCRIPTS))
import compatibility_upgrade as compatibility


class CompatibilityUpgradeTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".work").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / ".work")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.put(".gitignore", ".work/\n")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, check=True)

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    def plan(self, name, status="执行中", design=None):
        path = self.put(f"docs/longdev/{name}/PLAN.md", f"**状态**：{status}\n原始决定\n")
        if design is not None:
            self.put(f"docs/longdev/{name}/notes/analysis-design.md", design)
        return path

    def test_no_task_is_read_only_and_does_not_scan_workspace(self):
        self.plan("one")
        result = compatibility.upgrade(self.root)
        self.assertEqual(result["status"], "not_selected")
        self.assertFalse((self.root / "docs/longdev/one/COMPATIBILITY.json").exists())

    def test_selected_task_creates_immutable_receipt_and_is_idempotent(self):
        plan = self.plan("one")
        before = plan.read_bytes()
        preview = compatibility.upgrade(self.root, task="docs/longdev/one", dry_run=True)
        self.assertEqual(preview["status"], "pending")
        self.assertEqual(plan.read_bytes(), before)
        first = compatibility.upgrade(self.root, task="docs/longdev/one")
        self.assertEqual(first["status"], "upgraded")
        receipt_path = plan.parent / "COMPATIBILITY.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["adoption"], "legacy-preserved")
        self.assertEqual(receipt["adopted_workflow"], "unchanged")
        self.assertFalse(receipt["semantic_rewrite"])
        self.assertEqual(plan.read_bytes(), before)
        self.assertEqual(compatibility.upgrade(self.root, task="docs/longdev/one")["status"], "current")

    def test_source_evolution_does_not_rewrite_initial_snapshot(self):
        plan = self.plan("one")
        compatibility.upgrade(self.root, task="docs/longdev/one")
        receipt_path = plan.parent / "COMPATIBILITY.json"
        original = receipt_path.read_bytes()
        plan.write_text("**状态**：执行中\n后来正常演进\n", encoding="utf-8")
        result = compatibility.upgrade(self.root, task="docs/longdev/one")
        self.assertEqual(result["status"], "current")
        self.assertEqual(receipt_path.read_bytes(), original)

    def test_complete_transaction_detects_receipt_and_journal_changes_without_writes(self):
        for name in ("target-hash", "journal-hash", "journal-receipt", "journal-schema", "journal-profile"):
            with self.subTest(change=name):
                plan = self.plan(name)
                task = "docs/longdev/" + name
                compatibility.upgrade(self.root, task=task)
                target = plan.parent / "COMPATIBILITY.json"
                journal = self.root / compatibility._paths(self.root, task)[2]
                changed = target if name == "target-hash" else journal
                data = json.loads(changed.read_text(encoding="utf-8"))
                if name == "target-hash":
                    data["source_sha256"][task + "/PLAN.md"] = "0" * 64
                elif name == "journal-hash":
                    data["sha256"] = "0" * 64
                elif name == "journal-receipt":
                    data["receipt"]["source_sha256"][task + "/PLAN.md"] = "0" * 64
                elif name == "journal-schema":
                    data["schema"] = True
                else:
                    data["receipt"]["workflow_profile"] = "unknown-future"
                    data["sha256"] = compatibility.digest(compatibility._encode(data["receipt"]))
                changed.write_bytes(compatibility._encode(data))
                protected = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (plan, target, journal)}
                for mode in ({"check": True}, {"dry_run": True}, {}):
                    result = compatibility.upgrade(self.root, task=task, **mode)
                    self.assertEqual(result["status"], "needs_review")
                    self.assertEqual(compatibility.exit_code(result, bool(mode)), 2)
                    self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in protected}, protected)

    def test_snapshot_without_local_journal_is_preserved_as_unverifiable(self):
        plan = self.plan("portable")
        task = "docs/longdev/portable"
        compatibility.upgrade(self.root, task=task)
        target = plan.parent / "COMPATIBILITY.json"
        journal = self.root / compatibility._paths(self.root, task)[2]
        journal.unlink()
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (plan, target)}
        for mode in ({"check": True}, {"dry_run": True}, {}):
            result = compatibility.upgrade(self.root, task=task, **mode)
            self.assertEqual(result["status"], "needs_review")
            self.assertIn("integrity is unverifiable", result["actions"][0]["reason"])
            self.assertFalse(journal.exists())
            self.assertEqual({p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before}, before)

    def test_design_is_recorded_without_claiming_validation(self):
        self.plan("one", design="方案草稿")
        compatibility.upgrade(self.root, task="docs/longdev/one")
        receipt = json.loads((self.root / "docs/longdev/one/COMPATIBILITY.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["design_state"], "present_unverified")

    def test_terminal_task_is_preserved_without_sidecar(self):
        self.plan("done", "已验收")
        result = compatibility.upgrade(self.root, task="docs/longdev/done")
        self.assertEqual(result["status"], "current")
        self.assertFalse((self.root / "docs/longdev/done/COMPATIBILITY.json").exists())

    def test_pending_acceptance_and_ambiguous_terminal_are_not_closed(self):
        for name, status, expected in [
            ("pending", "待验收", "upgraded"),
            ("qualified", "已完成（实现结束，待用户验收）", "needs_review"),
            ("english", "completed (pending acceptance)", "needs_review"),
        ]:
            with self.subTest(status=status):
                plan = self.plan(name, status)
                before = plan.read_bytes()
                result = compatibility.upgrade(self.root, task="docs/longdev/" + name)
                self.assertEqual(result["status"], expected)
                self.assertEqual(plan.read_bytes(), before)
                self.assertEqual((plan.parent / "COMPATIBILITY.json").exists(), expected == "upgraded")

    def test_declared_source_format_is_not_silently_treated_as_unversioned(self):
        for name, metadata in [
            ("schema", "---\nschema: 99\n---\n"),
            ("profile", "---\nworkflow_profile: future-v99\n---\n"),
            ("markdown", "**record_format**: future-markdown-v2\n"),
        ]:
            with self.subTest(metadata=metadata):
                plan = self.put("docs/longdev/" + name + "/PLAN.md", metadata + "**状态**：执行中\n")
                before = plan.read_bytes()
                result = compatibility.upgrade(self.root, task="docs/longdev/" + name)
                self.assertEqual(result["status"], "needs_review")
                self.assertEqual(plan.read_bytes(), before)
                self.assertFalse((plan.parent / "COMPATIBILITY.json").exists())

    def test_source_new_format_after_snapshot_is_reviewed_without_snapshot_rewrite(self):
        plan = self.plan("evolved")
        task = "docs/longdev/evolved"
        compatibility.upgrade(self.root, task=task)
        receipt = plan.parent / "COMPATIBILITY.json"
        before = receipt.read_bytes()
        plan.write_text("---\nschema: 99\n---\n**状态**：执行中\n", encoding="utf-8")
        self.assertEqual(compatibility.upgrade(self.root, task=task)["status"], "needs_review")
        self.assertEqual(receipt.read_bytes(), before)

    def test_future_receipt_schema_and_profile_are_never_overwritten(self):
        for name, field, value in [("schema", "schema", 99), ("profile", "workflow_profile", "future-v99")]:
            with self.subTest(field=field):
                plan = self.plan(name)
                task = "docs/longdev/" + name
                compatibility.upgrade(self.root, task=task)
                path = plan.parent / "COMPATIBILITY.json"
                receipt = json.loads(path.read_text(encoding="utf-8"))
                receipt[field] = value
                path.write_text(json.dumps(receipt), encoding="utf-8")
                before = path.read_bytes()
                self.assertEqual(compatibility.upgrade(self.root, task=task)["status"], "needs_review")
                self.assertEqual(path.read_bytes(), before)

    def test_check_and_dry_run_preserve_all_bytes_and_mtimes(self):
        self.plan("readonly")
        def snapshot():
            return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns)
                    for path in self.root.rglob("*") if path.is_file()}
        before = snapshot()
        for mode in ({"check": True}, {"dry_run": True}):
            self.assertEqual(compatibility.upgrade(self.root, task="docs/longdev/readonly", **mode)["status"], "pending")
            self.assertEqual(snapshot(), before)

    def test_unknown_status_encoding_and_future_receipt_are_reviewed(self):
        self.plan("status", "未完成")
        result = compatibility.upgrade(self.root, task="docs/longdev/status")
        self.assertEqual(result["status"], "needs_review")
        self.put("docs/longdev/future/PLAN.md", "**状态**：执行中\n")
        self.put("docs/longdev/future/COMPATIBILITY.json", json.dumps({"schema": 999}))
        result = compatibility.upgrade(self.root, task="docs/longdev/future")
        self.assertEqual(result["status"], "needs_review")
        self.put("docs/longdev/binary/PLAN.md", b"\xff\xfe")
        self.assertEqual(compatibility.upgrade(self.root, task="docs/longdev/binary")["status"], "needs_review")

    def test_manual_fields_or_target_edits_are_never_overwritten(self):
        self.plan("manual")
        target = self.root / "docs/longdev/manual/COMPATIBILITY.json"
        self.put("docs/longdev/manual/COMPATIBILITY.json", '{"manual": true}\n')
        result = compatibility.upgrade(self.root, task="docs/longdev/manual")
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(target.read_text(encoding="utf-8"), '{"manual": true}\n')

    def test_interrupted_upgrade_recovers_and_source_or_target_change_blocks(self):
        self.plan("recover")
        original_publish = compatibility._publish_new
        with mock.patch.object(compatibility, "_publish_new", side_effect=RuntimeError("interrupt")):
            with self.assertRaises(RuntimeError):
                compatibility.upgrade(self.root, task="docs/longdev/recover")
        journal = list((self.root / ".work/longdev-migration/compatibility").glob("*.json"))[0]
        self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["state"], "applying")
        recovered = compatibility.upgrade(self.root, task="docs/longdev/recover")
        self.assertEqual(recovered["status"], "upgraded")
        self.assertTrue((self.root / "docs/longdev/recover/COMPATIBILITY.json").is_file())

        self.plan("recover-source")
        with mock.patch.object(compatibility, "_publish_new", side_effect=RuntimeError("interrupt")):
            with self.assertRaises(RuntimeError):
                compatibility.upgrade(self.root, task="docs/longdev/recover-source")
        # A source edit invalidates the pending transaction and cannot be used to overwrite it.
        self.put("docs/longdev/recover-source/PLAN.md", "**状态**：执行中\nchanged\n")
        blocked = compatibility.upgrade(self.root, task="docs/longdev/recover-source")
        self.assertEqual(blocked["status"], "needs_review")
        # 恢复原始输入后，保留中的事务可继续，无需删除 journal。
        self.plan("recover-source")
        self.assertEqual(compatibility.upgrade(self.root, task="docs/longdev/recover-source")["status"], "upgraded")
        compatibility._publish_new = original_publish
        self.plan("recover2")
        with mock.patch.object(compatibility, "_publish_new", side_effect=RuntimeError("interrupt")):
            with self.assertRaises(RuntimeError):
                compatibility.upgrade(self.root, task="docs/longdev/recover2")
        target = self.root / "docs/longdev/recover2/COMPATIBILITY.json"
        target.write_text('{"user": true}\n', encoding="utf-8")
        self.assertEqual(compatibility.upgrade(self.root, task="docs/longdev/recover2")["status"], "needs_review")

    def test_interruption_after_publish_recovers_immutable_snapshot_after_source_evolution(self):
        plan = self.plan("published")
        task = "docs/longdev/published"
        original = compatibility.atomic_write
        def interrupt_complete(root, relative, data):
            if b'"state": "complete"' in data:
                raise RuntimeError("interrupted after publish")
            return original(root, relative, data)
        with mock.patch.object(compatibility, "atomic_write", side_effect=interrupt_complete):
            with self.assertRaises(RuntimeError):
                compatibility.upgrade(self.root, task=task)
        path = plan.parent / "COMPATIBILITY.json"
        snapshot = path.read_bytes()
        plan.write_text("**状态**：待验收\n后续正常演进\n", encoding="utf-8")
        self.assertEqual(compatibility.upgrade(self.root, task=task)["status"], "upgraded")
        self.assertEqual(path.read_bytes(), snapshot)
        journal_path = compatibility._paths(self.root, task)[2]
        self.assertEqual(json.loads((self.root / journal_path).read_text(encoding="utf-8"))["state"], "complete")

    def test_task_isolation_and_readonly_mtime(self):
        first = self.plan("one")
        second = self.plan("two")
        mtime = first.stat().st_mtime_ns
        compatibility.upgrade(self.root, task="docs/longdev/one")
        self.assertEqual(first.stat().st_mtime_ns, mtime)
        self.assertTrue((first.parent / "COMPATIBILITY.json").exists())
        self.assertFalse((second.parent / "COMPATIBILITY.json").exists())
        self.assertFalse((self.root / "docs/longdev/two/COMPATIBILITY.json").exists())

    def test_cli_exit_codes_and_selected_task(self):
        self.plan("cli")
        command = [sys.executable, "-B", str(SCRIPTS / "compatibility_upgrade.py"), "--project", str(self.root),
                   "--task", "docs/longdev/cli", "--check"]
        preview = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(preview.returncode, 1)
        applied = subprocess.run(command[:-1], capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        current = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(current.returncode, 0)

    def test_migrate_cli_selected_task_reports_pending_compatibility(self):
        self.plan("cli")
        command = [sys.executable, "-B", str(SCRIPTS / "migrate_workspace.py"), "--project", str(self.root),
                   "--task", "docs/longdev/cli", "--check"]
        preview = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(preview.returncode, 1, preview.stdout + preview.stderr)
        self.assertEqual(json.loads(preview.stdout)["compatibility"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
