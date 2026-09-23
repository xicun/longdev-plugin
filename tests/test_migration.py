import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/longdev/scripts/migrate_workspace.py'
spec = importlib.util.spec_from_file_location('migration', SCRIPT)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.put('.gitignore', '.claude/\n.work/\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file() and '.git' not in p.parts}

    def test_full_migration_paths_states_binary_and_portable_marker(self):
        plan = ('状态：待验收\n'
                '[stage](stages/1.md) [log](evidence/run.log)\n'
                '[product](../../autopilot/prod/CHARTER.md)\n'
                '[absolute](/old/machine/repo/.claude/longdev/task/stages/1.md)\n'
                '`C:\\old\\repo\\.claude\\longdev\\task\\PLAN.md`\n'
                '`.claude/autopilot/prod/CHARTER.md`\n')
        legacy = self.put('.claude/longdev/task/PLAN.md', plan)
        self.put('.claude/longdev/task/stages/1.md', '已检查，未验收')
        self.put('.claude/longdev/task/evidence/run.log', 'original stdout\n')
        self.put('.claude/longdev/task/evidence/manifest.json', '{"path": ".claude/longdev/task/PLAN.md", "sha256": "unchanged"}')
        self.put('.claude/longdev/task/baselines/start/file.txt', 'original backup')
        blob = self.root / '.claude/longdev/task/evidence/image.png'
        blob.write_bytes(b'\x89PNG\x00\xff')
        self.put('.claude/autopilot/prod/CHARTER.md', 'authorized scope')
        external = self.put('PLAN.md', '[legacy](.claude/longdev/task/PLAN.md)')
        before = self.snapshot()
        probe = migration.migrate(self.root, check=True)
        self.assertEqual(probe['status'], 'migration_pending')
        self.assertEqual(self.snapshot(), before)
        result = migration.migrate(self.root)
        self.assertEqual(result['status'], 'migrated')
        self.assertEqual(result['external_references'], ['PLAN.md'])
        migrated = (self.root / 'docs/longdev/task/PLAN.md').read_text()
        self.assertIn('状态：待验收', migrated)
        self.assertIn('[stage](stages/1.md)', migrated)
        self.assertIn('[product](../../autopilot/prod/CHARTER.md)', migrated)
        self.assertIn('[log](../../../.work/longdev/task/evidence/run.log)', migrated)
        self.assertIn('[absolute](stages/1.md)', migrated)
        self.assertIn('`docs/longdev/task/PLAN.md`', migrated)
        self.assertNotIn('.claude', migrated)
        self.assertEqual(legacy.read_text(), plan)
        self.assertEqual(external.read_bytes(), before['PLAN.md'])
        self.assertEqual((self.root / '.work/longdev/task/evidence/image.png').read_bytes(), blob.read_bytes())
        self.assertEqual((self.root / '.work/longdev/task/baselines/start/file.txt').read_text(), 'original backup')
        marker = (self.root / migration.MARKER).read_text()
        self.assertNotIn(str(self.root), marker)
        self.assertIn('Historical statuses are preserved', marker)
        after = self.snapshot()
        self.assertEqual(migration.migrate(self.root)['status'], 'already_migrated')
        self.assertEqual(self.snapshot(), after)

    def test_marker_survives_machine_move_without_local_files_or_legacy(self):
        self.put('.claude/longdev/t/PLAN.md', 'old status')
        self.put('.claude/longdev/t/evidence/x.log', 'old evidence')
        migration.migrate(self.root)
        shutil.rmtree(self.root / '.claude')
        shutil.rmtree(self.root / '.work')
        current = self.put('docs/longdev/t/PLAN.md', 'new authorized state')
        self.assertEqual(migration.migrate(self.root)['status'], 'already_migrated')
        self.assertEqual(current.read_text(), 'new authorized state')
        self.assertFalse((self.root / '.work').exists())

    def test_rewrites_only_path_tokens_preserving_commands_titles_and_backups(self):
        content = ('`cat .claude/longdev/t/PLAN.md`\n'
                   '`python .claude/longdev/t/test.py --check`\n'
                   '`/usr/bin/python .claude/longdev/t/test.py --check`\n'
                   '[title](.claude/longdev/t/PLAN.md "read plan")\n'
                   '[space](<.claude/longdev/t/my plan.md> "title")\n')
        self.put('.claude/longdev/t/PLAN.md', content)
        self.put('.claude/longdev/t/my plan.md', 'space name')
        self.put('.claude/longdev/t/test.py', 'print(1)')
        self.put('.claude/longdev/t/config.json', json.dumps({'command': 'cat .claude/longdev/t/PLAN.md'}))
        self.put('.claude/longdev/t/baselines/original.md', content)
        migration.migrate(self.root)
        actual = (self.root / 'docs/longdev/t/PLAN.md').read_text()
        self.assertIn('`cat docs/longdev/t/PLAN.md`', actual)
        self.assertIn('`python docs/longdev/t/test.py --check`', actual)
        self.assertIn('`/usr/bin/python docs/longdev/t/test.py --check`', actual)
        self.assertIn('[title](PLAN.md "read plan")', actual)
        self.assertIn('[space](<my plan.md> "title")', actual)
        self.assertEqual(json.loads((self.root / 'docs/longdev/t/config.json').read_text())['command'], 'cat docs/longdev/t/PLAN.md')
        self.assertEqual((self.root / '.work/longdev/t/baselines/original.md').read_text(), content)

    def test_json_embedded_quotes_windows_and_nonpath_values_preserved(self):
        value = {'command': 'cat ".claude/longdev/t/PLAN.md"',
                 'windows': 'cat "C:\\old\\repo\\.claude\\longdev\\t\\PLAN.md"',
                 'status': '待验收', 'count': 4, 'passed': False,
                 'nested': ['python .claude/longdev/t/test.py --check', None],
                 'log': 'evidence/run.log',
                 'space': 'C:\\old project\\.claude\\longdev\\t\\my plan.md'}
        self.put('.claude/longdev/t/PLAN.md', 'plan')
        self.put('.claude/longdev/t/my plan.md', 'space name')
        self.put('.claude/longdev/t/evidence/run.log', 'actual output')
        self.put('.claude/longdev/t/info.json', json.dumps(value))
        migration.migrate(self.root)
        actual = json.loads((self.root / 'docs/longdev/t/info.json').read_text())
        self.assertEqual(actual['command'], 'cat "docs/longdev/t/PLAN.md"')
        self.assertEqual(actual['windows'], 'cat "docs/longdev/t/PLAN.md"')
        self.assertEqual(actual['status'], value['status'])
        self.assertEqual(actual['count'], 4)
        self.assertIs(actual['passed'], False)
        self.assertEqual(actual['nested'], ['python docs/longdev/t/test.py --check', None])
        self.assertEqual(actual['log'], '.work/longdev/t/evidence/run.log')
        self.assertEqual(actual['space'], 'docs/longdev/t/my plan.md')

    def test_unknown_binary_goes_local_and_unsupported_text_is_reported(self):
        self.put('.claude/longdev/t/PLAN.md', '[blob](evidence/blob.dat)')
        blob = self.root / '.claude/longdev/t/evidence/blob.dat'
        blob.parent.mkdir()
        blob.write_bytes(b'\xff\xfe\x00')
        yaml = self.put('.claude/longdev/t/info.yaml', 'path: .claude/longdev/t/PLAN.md\n')
        migration.migrate(self.root)
        self.assertEqual((self.root / '.work/longdev/t/evidence/blob.dat').read_bytes(), blob.read_bytes())
        self.assertEqual((self.root / 'docs/longdev/t/info.yaml').read_bytes(), yaml.read_bytes())
        report = json.loads((self.root / migration.MARKER).read_text())
        self.assertEqual(report['manual_review'], ['docs/longdev/t/info.yaml'])

    def test_new_workspace_ignored_docs_is_blocked_without_writing(self):
        self.put('.gitignore', 'docs/\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'destinations ignored'):
            migration.migrate(self.root)
        self.assertEqual(before, self.snapshot())

    def test_old_records_never_reimported_after_completion(self):
        old = self.put('.claude/longdev/t/PLAN.md', 'initial')
        migration.migrate(self.root)
        old.write_text('stale client write')
        self.put('.claude/longdev/other/PLAN.md', 'stale new record')
        migration.migrate(self.root)
        self.assertEqual((self.root / 'docs/longdev/t/PLAN.md').read_text(), 'initial')
        self.assertFalse((self.root / 'docs/longdev/other').exists())

    def test_conflict_is_detected_before_writes(self):
        self.put('.claude/longdev/t/PLAN.md', 'legacy')
        self.put('.claude/longdev/t/stages/1.md', 'stage')
        self.put('docs/longdev/t/PLAN.md', 'newer')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Destination conflict'):
            migration.migrate(self.root)
        self.assertEqual(before, self.snapshot())

    def test_matching_existing_file_is_safe(self):
        self.put('.claude/longdev/t/PLAN.md', 'same')
        self.put('docs/longdev/t/PLAN.md', 'same')
        self.assertEqual(migration.migrate(self.root)['status'], 'migrated')

    def test_interrupted_write_resumes_with_journal(self):
        self.put('.claude/longdev/t/PLAN.md', 'plan')
        self.put('.claude/longdev/t/stages/1.md', 'stage')
        original = migration.atomic_write

        def crash(root, path, data):
            if path.endswith('stages/1.md'):
                raise OSError('simulated interruption')
            original(root, path, data)

        with patch.object(migration, 'atomic_write', crash):
            with self.assertRaisesRegex(OSError, 'simulated interruption'):
                migration.migrate(self.root)
        self.assertTrue((self.root / migration.JOURNAL).exists())
        self.assertFalse((self.root / migration.MARKER).exists())
        self.assertEqual(migration.migrate(self.root)['status'], 'migrated')
        self.assertEqual((self.root / 'docs/longdev/t/stages/1.md').read_text(), 'stage')

    def test_changed_source_or_target_after_interruption_blocked(self):
        old = self.put('.claude/longdev/t/PLAN.md', 'plan')
        original = migration.atomic_write

        def crash(root, path, data):
            if path == migration.MARKER:
                raise OSError('stop before completion')
            original(root, path, data)

        with patch.object(migration, 'atomic_write', crash):
            with self.assertRaises(OSError):
                migration.migrate(self.root)
        old.write_text('changed')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            migration.migrate(self.root)
        old.write_text('plan')
        self.put('docs/longdev/t/PLAN.md', 'newer')
        with self.assertRaisesRegex(ValueError, 'Destination conflict'):
            migration.migrate(self.root)

    def test_ignored_destination_marker_and_later_ignore_are_blocked(self):
        self.put('.claude/longdev/t/PLAN.md', 'plan')
        ignore = self.put('.gitignore', '.claude/\ndocs/\n.work/\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'ignored'):
            migration.migrate(self.root)
        self.assertEqual(before, self.snapshot())
        ignore.write_text('.claude/\n.work/\n.migration-v013.json\n')
        with self.assertRaisesRegex(ValueError, 'ignored'):
            migration.migrate(self.root)
        ignore.write_text('.claude/\n.work/\ndocs/\n!/docs/\n!/docs/longdev/\n!/docs/longdev/**\n')
        self.assertEqual(migration.migrate(self.root)['status'], 'migrated')
        ignore.write_text('.claude/\n.work/\ndocs/\n')
        with self.assertRaisesRegex(ValueError, 'ignored after migration'):
            migration.migrate(self.root, check=True)

    def test_symlinks_in_source_destination_and_scratch_refused(self):
        self.put('.claude/longdev/t/PLAN.md', 'plan')
        for relative in ('docs', '.work', '.claude/longdev/t/link'):
            target = self.root / relative
            target.symlink_to(self.root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                migration.migrate(self.root)
            target.unlink()

    def test_windows_reparse_attribute_is_rejected(self):
        original = Path.lstat

        def attributes(path):
            if path == self.root / 'docs':
                return SimpleNamespace(st_file_attributes=0x400, st_mode=0o40755)
            return original(path)

        with patch.object(Path, 'lstat', attributes):
            with self.assertRaisesRegex(ValueError, 'Symlink'):
                migration.safe(self.root, 'docs/longdev/t/PLAN.md')

    def test_unsafe_posix_and_windows_paths_refused(self):
        for relative in ('', '../outside', '/outside', 'C:/outside', 'C:outside', '\\\\server\\share\\outside'):
            with self.subTest(path=relative):
                with self.assertRaisesRegex(ValueError, 'Unsafe path'):
                    migration.safe(self.root, relative)

    def test_no_records_creates_nothing_and_sibling_is_untouched(self):
        sibling = self.root / 'other-workspace'
        sibling.mkdir()
        self.put('other-workspace/.claude/longdev/t/PLAN.md', 'other')
        before = self.snapshot()
        self.assertEqual(migration.migrate(self.root)['status'], 'no_legacy_records')
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / 'docs').exists())

    def test_cli_reports_blocked_with_nonzero_status(self):
        self.put('.claude/longdev/t/PLAN.md', 'old')
        self.put('docs/longdev/t/PLAN.md', 'new')
        result = subprocess.run(['python3', '-B', str(SCRIPT), '--project', str(self.root), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)['status'], 'blocked')

    def test_cli_pending_is_read_only_and_nonzero(self):
        self.put('.claude/longdev/t/PLAN.md', 'old')
        before = self.snapshot()
        result = subprocess.run(['python3', '-B', str(SCRIPT), '--project', str(self.root), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)['status'], 'migration_pending')
        self.assertEqual(before, self.snapshot())

    def test_new_legacy_file_after_interruption_requires_reconciliation(self):
        self.put('.claude/longdev/t/PLAN.md', 'old')
        journal = migration.prepare(self.root)
        migration.atomic_write(self.root, migration.JOURNAL, json.dumps(journal).encode())
        self.put('.claude/longdev/t/stages/new.md', 'added by another client')
        with self.assertRaisesRegex(ValueError, 'file set changed'):
            migration.migrate(self.root)
        self.assertFalse((self.root / migration.MARKER).exists())

    def test_concurrent_migration_is_rejected(self):
        self.put('.claude/longdev/t/PLAN.md', 'old')
        with migration.migration_lock(self.root):
            result = subprocess.run(['python3', '-B', str(SCRIPT), '--project', str(self.root)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('workspace lock', result.stdout)
        self.assertFalse((self.root / migration.MARKER).exists())


if __name__ == '__main__':
    unittest.main()
