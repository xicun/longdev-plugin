import importlib.util
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
            for name in ('longdev', 'autopilot'):
                self.assertIn(bundle.as_posix(), (self.project / entry / name / 'SKILL.md').read_text('utf-8'))
                self.assertTrue((bundle / 'skills' / name / '../../.claude-plugin/plugin.json').resolve().is_file())
            self.assertTrue((bundle / 'agents/longdev-reviewer.md').is_file())
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


if __name__ == '__main__':
    unittest.main()
