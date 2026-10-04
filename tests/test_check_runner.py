import json
import sys
import tempfile
import unittest
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_runner", ROOT / "skills" / "checks" / "scripts" / "check_runner.py")
RUNNER = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(RUNNER)


def _source_catalog(root: Path) -> Path:
    catalog = root / "catalog"
    catalog.mkdir()
    cases = {"schema": 1, "cases": [{
        "id": "probe", "title": "probe", "profile": "smoke",
        "command": [sys.executable, "-B", "-c", "import sys; print('ok'); sys.exit(0)"],
        "cwd": ".", "expected_exit": 0, "source": "sample", "quality_refs": ["requirement:R-1", "test_case:T-1", "bug:B-1"],
    }]}
    matrix = {"schema": 1, "profiles": {"smoke": ["probe"], "full": [], "failure-probe": []}}
    refs = {"schema": 1, "references": [
        {"kind": "requirement", "id": "R-1", "reference": "req/R-1"},
        {"kind": "test_case", "id": "T-1", "reference": "tests/T-1"},
        {"kind": "bug", "id": "B-1", "reference": "bugs/B-1"},
    ]}
    (catalog / "cases.json").write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    (catalog / "matrix.json").write_text(json.dumps(matrix, ensure_ascii=False), encoding="utf-8")
    (catalog / "quality_refs.json").write_text(json.dumps(refs, ensure_ascii=False), encoding="utf-8")
    return catalog


class CheckRunnerTests(unittest.TestCase):
    def test_validate_generic_catalog_all_profiles(self):
        with tempfile.TemporaryDirectory() as temp:
            cases, matrix, refs = RUNNER.validate_catalog(_source_catalog(Path(temp)))
            self.assertEqual(cases["schema"], 1)
            self.assertEqual(set(matrix["profiles"]), set(RUNNER.PROFILES))
            self.assertGreaterEqual(len(refs["references"]), 1)

    def test_validate_accepts_bug_kind(self):
        with tempfile.TemporaryDirectory() as temp:
            RUNNER.validate_catalog(_source_catalog(Path(temp)))

    def test_unique_output_preserves_existing_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "run"
            base.mkdir()
            (base / "manifest.json").write_text("old", encoding="utf-8")
            self.assertEqual(RUNNER.unique_output(base).name, "run-001")

    def test_run_subset_writes_manifest_and_fingerprints(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            source = Path(temp) / "source"
            source.mkdir()
            catalog = _source_catalog(Path(temp))
            result = RUNNER.run_cases(catalog, source, "smoke", None, ["probe"], out)
            self.assertEqual(result, 0)
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["exit_code"], 0)
            self.assertEqual([c["id"] for c in manifest["cases"]], ["probe"])
            self.assertTrue((out / "fingerprints.json").exists())

    def test_run_subset_rejects_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            source.mkdir()
            catalog = _source_catalog(Path(temp))
            with self.assertRaises(RUNNER.CatalogError):
                RUNNER.run_cases(catalog, source, "smoke", None, ["nope"], Path(temp) / "run")

    def test_unsafe_case_ids_are_rejected(self):
        # L02：case ID 会成为 run 目录下的路径段，穿越/分隔符/保留名必须在校验层拒绝。
        unsafe = ["../evil", "../../outside", "a/b", "a\\b", "/abs", "..", ".", "aux", "com1", "-lead"]
        for bad in unsafe:
            with tempfile.TemporaryDirectory() as temp:
                catalog = _source_catalog(Path(temp))
                payload = json.loads((catalog / "cases.json").read_text(encoding="utf-8"))
                payload["cases"][0]["id"] = bad
                (catalog / "cases.json").write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaises(RUNNER.CatalogError):
                    RUNNER.validate_catalog(catalog)

    def test_safe_case_ids_are_kept(self):
        for good in ("probe", "R01", "case-2_x.y", "z" * 128):
            self.assertTrue(RUNNER.safe_case_id(good))
        for bad in ("../evil", "a/b", "a\\b", "/abs", "..", ".", "", "-lead", "con", "com1", "x" * 129):
            self.assertFalse(RUNNER.safe_case_id(bad), bad)


if __name__ == "__main__":
    unittest.main()