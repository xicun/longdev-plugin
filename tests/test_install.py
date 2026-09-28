import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / '.work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def test_full_bundle_three_clients_and_repeat(self):
        bundles = set()
        for client, entry in installer.ROOTS.items():
            result = installer.install(self.project, client)
            bundle = Path(result['bundle'])
            bundles.add(bundle)
            for name in installer.SKILLS:
                entry_text = (self.project / entry / name / 'SKILL.md').read_text('utf-8')
                self.assertIn(bundle.as_posix(), entry_text)
                self.assertTrue((bundle / 'skills' / name / '../../.claude-plugin/plugin.json').resolve().is_file())
                if name in ('longdev', 'autopilot'):
                    protocol = (bundle / 'skills' / 'longdev' / 'references' / 'execution-protocol.md').as_posix()
                    self.assertIn(protocol, entry_text)
                    self.assertIn('不从版本目录直接拼接 references', entry_text)
            self.assertTrue((bundle / 'agents/longdev-reviewer.md').is_file())
            script = bundle / 'skills/longdev/scripts/migrate_workspace.py'
            self.assertEqual(script.read_bytes(), (ROOT / 'skills/longdev/scripts/migrate_workspace.py').read_bytes())
            for helper in ('history_convergence.py', 'workspace_common.py', 'task_path.py'):
                self.assertEqual((bundle / 'skills/longdev/scripts' / helper).read_bytes(),
                                 (ROOT / 'skills/longdev/scripts' / helper).read_bytes())
            self.assertIn('docs/longdev/', (self.project / entry / 'longdev/SKILL.md').read_text('utf-8'))
            bug_entry = (self.project / entry / 'bug-reports/SKILL.md').read_text('utf-8')
            self.assertIn('docs/bugs/reports.json', bug_entry)
            self.assertNotIn('启动/续接先按完整技能调用包内迁移脚本', bug_entry)
            self.assertEqual((bundle / 'skills/bug-reports/scripts/bug_reports.py').read_bytes(),
                             (ROOT / 'skills/bug-reports/scripts/bug_reports.py').read_bytes())
            installer.install(self.project, client)
            installer.install(self.project, client, check=True)
        self.assertEqual(len(bundles), 1)

    def test_unknown_and_edited_skills_preserved(self):
        entry = self.project / '.agents/skills/longdev/SKILL.md'
        entry.parent.mkdir(parents=True)
        entry.write_text('user content')
        with self.assertRaises(ValueError):
            installer.install(self.project, 'codex')
        self.assertEqual(entry.read_text(), 'user content')
        self.assertFalse((self.project / '.longdev-runtime').exists())
        installer.install(self.project, 'dsh')
        edited = self.project / '.dsh/skills/autopilot/SKILL.md'
        edited.write_text('local edits')
        with self.assertRaises(ValueError):
            installer.install(self.project, 'dsh')
        self.assertEqual(edited.read_text(), 'local edits')

    def test_corrupt_bundle_fails_check(self):
        result = installer.install(self.project, 'dsh')
        path = Path(result['bundle']) / 'agents/longdev-reviewer.md'
        path.write_text('changed')
        with self.assertRaises(ValueError):
            installer.install(self.project, 'dsh', check=True)

    def snapshot(self):
        return {p.relative_to(self.project).as_posix(): (p.stat().st_mtime_ns, p.read_bytes())
                for p in self.project.rglob('*') if p.is_file()}

    def test_legacy_two_skill_receipt_upgrade_and_unknown_third(self):
        installer.install(self.project, 'codex')
        entry = self.project / '.agents/skills/bug-reports/SKILL.md'
        entry.unlink()
        receipt = self.project / '.longdev-runtime/codex.json'
        old = json.loads(receipt.read_bytes())
        old['entries'].pop('.agents/skills/bug-reports/SKILL.md')
        old['files'] = {k: v for k, v in old['files'].items() if not k.startswith('skills/bug-reports/')}
        old['bundle'] = 'legacy-two-skills'
        receipt.write_text(json.dumps(old), encoding='utf-8')
        archive = self.project / 'docs/bugs/reports.json'
        archive.parent.mkdir(parents=True)
        archive.write_bytes(b'user reports')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            installer.install(self.project, 'codex', check=True)
        self.assertEqual(before, self.snapshot())
        entry.write_bytes(b'unknown third skill')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            installer.install(self.project, 'codex')
        self.assertEqual(before, self.snapshot())
        entry.unlink()
        installer.install(self.project, 'codex')
        before = self.snapshot()
        installer.install(self.project, 'codex', check=True)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(archive.read_bytes(), b'user reports')
        entry.write_bytes(b'user edited bug skill')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            installer.install(self.project, 'codex')
        self.assertEqual(before, self.snapshot())

    def test_missing_bug_script_source_or_cache_is_rejected_readonly(self):
        source = self.project / 'source'
        for name in ('skills', 'agents', '.claude-plugin', '.codex-plugin'):
            shutil.copytree(ROOT / name, source / name)
        result = installer.install(self.project, 'claude', source=source)
        script = Path(result['bundle']) / 'skills/bug-reports/scripts/bug_reports.py'
        script.unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Installation mismatch'):
            installer.install(self.project, 'claude', source=source, check=True)
        self.assertEqual(before, self.snapshot())
        (source / 'skills/bug-reports/scripts/bug_reports.py').unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Missing dependency'):
            installer.install(self.project, 'claude', source=source)
        self.assertEqual(before, self.snapshot())

    def test_update_and_move_preserve_old_bundle(self):
        source = self.project / 'source'
        for name in ('skills', 'agents', '.claude-plugin', '.codex-plugin'):
            shutil.copytree(ROOT / name, source / name)
        first = installer.install(self.project, 'codex', source=source)
        with (source / 'agents/longdev-reviewer.md').open('a', encoding='utf-8') as f:
            f.write('\nNew reviewer revision\n')
        second = installer.install(self.project, 'codex', source=source)
        self.assertNotEqual(first['bundle'], second['bundle'])
        self.assertTrue(Path(first['bundle']).exists())
        moved = self.project / 'moved'
        shutil.copytree(self.project / '.agents', moved / '.agents')
        shutil.copytree(self.project / '.longdev-runtime', moved / '.longdev-runtime')
        installer.install(moved, 'codex', source=source)
        installer.install(moved, 'codex', source=source, check=True)

    def test_missing_cli_contract_source_and_cache_are_rejected(self):
        source = self.project / 'source'
        for name in ('skills', 'agents', '.claude-plugin', '.codex-plugin'):
            shutil.copytree(ROOT / name, source / name)
        result = installer.install(self.project, 'codex', source=source)
        relative = 'skills/bug-reports/references/cli.md'
        (Path(result['bundle']) / relative).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'Installation mismatch'):
            installer.install(self.project, 'codex', source=source, check=True)
        self.assertEqual(before, self.snapshot())
        (source / relative).unlink()
        before = self.snapshot()
        for check in (False, True):
            with self.assertRaisesRegex(ValueError, 'Missing dependency'):
                installer.install(self.project, 'codex', source=source, check=check)
            self.assertEqual(before, self.snapshot())


if __name__ == '__main__':
    unittest.main()
