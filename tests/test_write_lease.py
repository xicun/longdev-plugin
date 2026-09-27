import json
import tempfile
import unittest
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("write_lease", ROOT / "skills" / "longdev" / "scripts" / "write_lease.py")
WL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(WL)


class WriteLeaseTests(unittest.TestCase):
    def test_acquire_status_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token = WL.acquire(root, "testcases")
            self.assertTrue(WL.status(root, "testcases")["held"])
            self.assertTrue(WL.release(root, "testcases", token)["released"])
            self.assertFalse(WL.status(root, "testcases")["held"])

    def test_contention_is_raised(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token0 = WL.acquire(root, "testcases")
            with self.assertRaises(RuntimeError):
                WL.acquire(root, "testcases")
            WL.release(root, "testcases", token0)

    def test_stale_lease_is_reclaimed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            WL.acquire(root, "old")
            path = WL.lock_path(root, "old")
            record = json.loads(path.read_text("utf-8"))
            record["at"] = "2020-01-01T00:00:00+00:00"  # force stale
            path.write_text(json.dumps(record), encoding="utf-8")
            self.assertTrue(WL.stale(record))
            token = WL.acquire(root, "old")  # should reclaim stale
            self.assertTrue(WL.status(root, "old")["held"])
            WL.release(root, "old", token)

    def test_release_requires_matching_token(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            WL.acquire(root, "r")
            with self.assertRaises(RuntimeError):
                WL.release(root, "r", "wrong-token")


if __name__ == "__main__":
    unittest.main()