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

    def test_published_record_is_complete(self):
        # 原子发布：锁文件一旦存在，内容必然是完整 JSON 记录。
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token = WL.acquire(root, "testcases")
            path = WL.lock_path(root, "testcases")
            record, corrupt = WL.read_lock(path)
            self.assertFalse(corrupt)
            self.assertEqual(record["token"], token)
            self.assertEqual(record["gen"], 1)
            WL.release(root, "testcases", token)

    def test_stale_lease_is_not_reclaimed_automatically(self):
        # 契约修订（L01）：超龄只标疑似失联，acquire 不再自动删除或抢占。
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token0 = WL.acquire(root, "old")
            path = WL.lock_path(root, "old")
            record = json.loads(path.read_text("utf-8"))
            record["at"] = "2020-01-01T00:00:00+00:00"  # force stale
            path.write_text(json.dumps(record), encoding="utf-8")
            self.assertTrue(WL.stale(record))
            with self.assertRaises(RuntimeError):
                WL.acquire(root, "old")  # 不自动接管
            self.assertTrue(WL.status(root, "old")["held"])
            # 显式接管需匹配观察到的 state 与 token；调用者负责证明旧写入者已停止。
            with self.assertRaises(RuntimeError):
                WL.takeover(root, "old", "held", token0, "no diagnosis")
            token = WL.takeover(root, "old", "stale", record["token"], "verified writer stopped")
            new_record = json.loads(path.read_text("utf-8"))
            self.assertEqual(new_record["took_over_from"]["token"], token0)
            with self.assertRaises(RuntimeError):
                WL.renew(root, "old", record["token"])  # 旧 token 不能续租
            WL.release(root, "old", token)

    def test_corrupt_lease_is_not_reclaimed_automatically(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = WL.lock_path(root, "r")
            path.write_text("", encoding="utf-8")  # 空锁（如中断的写入）
            with self.assertRaises(RuntimeError):
                WL.acquire(root, "r")
            status = WL.status(root, "r")
            self.assertTrue(status["held"] and status["corrupt"])
            with self.assertRaises(RuntimeError):
                WL.takeover(root, "r", "stale", None, "wrong state")
            token = WL.takeover(root, "r", "corrupt", None, "scene inspected")
            self.assertTrue(WL.status(root, "r")["held"])
            WL.release(root, "r", token)

    def test_takeover_refuses_fresh_lease(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token0 = WL.acquire(root, "r")
            with self.assertRaises(RuntimeError):
                WL.takeover(root, "r", "stale", token0, "must refuse fresh lease")
            status = WL.status(root, "r")
            self.assertTrue(status["held"] and not status["stale"])
            WL.release(root, "r", token0)

    def test_renew_extends_and_bumps_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            token = WL.acquire(root, "r")
            result = WL.renew(root, "r", token)
            self.assertEqual(result["gen"], 2)
            status = WL.status(root, "r")
            self.assertEqual(status["gen"], 2)
            self.assertFalse(status["stale"])
            with self.assertRaises(RuntimeError):
                WL.renew(root, "r", "wrong-token")
            WL.release(root, "r", token)
            with self.assertRaises(RuntimeError):
                WL.renew(root, "r", token)  # 锁已释放

    def test_release_requires_matching_token(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            WL.acquire(root, "r")
            with self.assertRaises(RuntimeError):
                WL.release(root, "r", "wrong-token")


if __name__ == "__main__":
    unittest.main()
