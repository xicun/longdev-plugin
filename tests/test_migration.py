import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/longdev/scripts'
sys.path.insert(0, str(SCRIPTS))
import migrate_workspace as migration
import history_convergence as history
import workspace_common as common
import task_path


class MigrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / '.work').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / '.work')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git('init', '-q')
        self.put('.gitignore', '.claude/\n .claude/\n.longdev/\n.work/\n')

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], capture_output=True, check=True)

    def put(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding='utf-8')
        return path

    def task(self, directory='.claude/longdev/t', state='执行中', extra='', kind='longdev'):
        name = 'CHARTER.md' if kind == 'autopilot' else 'PLAN.md'
        fields = '**产品目标**：测试产品\n**执行状态**：' if kind == 'autopilot' else '**目标**：测试任务\n**状态**：'
        self.put(directory + '/' + name, '# Example\n' + fields + state + '\n' + extra)
        return directory

    def closed(self, directory, extra=''):
        self.task(directory, '已验收', extra)
        self.put(directory + '/reviews/final.md', '独立审查通过\n')
        self.put(directory + '/gates/final.md', '整体检查通过\n')

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): (p.read_bytes() if p.is_file() else None, p.stat().st_mtime_ns)
                for p in self.root.rglob('*')}

    def apply(self):
        return migration.migrate(self.root)

    def track(self):
        self.git('add', '--', 'docs')

    def test_active_migrate_then_index_verified_archive(self):
        self.task(extra='[stage](stages/1.md)\n')
        self.put('.claude/longdev/t/stages/1.md', 'implementation')
        result = self.apply()
        self.assertEqual(result['status'], 'awaiting_tracking')
        self.assertTrue((self.root / '.claude/longdev/t/PLAN.md').exists())
        self.assertIn('[stage](stages/1.md)', (self.root / 'docs/longdev/t/PLAN.md').read_text())
        self.track()
        result = self.apply()
        self.assertEqual(result['status'], 'converged')
        self.assertFalse((self.root / '.claude/longdev/t').exists())
        for action in result['actions']:
            self.assertEqual(common.digest((self.root / action['archive']).read_bytes()), action['source_sha256'])
        self.assertEqual(self.apply()['status'], 'no_legacy_records')

    def test_all_candidate_roots_content_identity_and_client_assets(self):
        self.task('.claude/longdev/a')
        self.task(' .claude/longdev/b')
        self.task('.longdev/c')
        self.task('.longdev/autopilot/product', kind='autopilot')
        assets = {'.claude/settings.json': '{"client":true}', '.claude/skills/x/SKILL.md': 'skill',
                  ' .claude/runtime/state': 'runtime', '.longdev-runtime/x': 'bundle',
                  '.longdev/unknown/config.json': '{}', '.claude/longdev/no-identity/PLAN.md': 'a grocery list'}
        for path, text in assets.items():
            self.put(path, text)
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        for kind, name in [('longdev','a'),('longdev','b'),('longdev','c'),('autopilot','product')]:
            self.assertTrue((self.root / 'docs' / kind / name).exists())
        self.track(); self.apply()
        for path, text in assets.items():
            self.assertEqual((self.root / path).read_text(), text)

    def test_true_closed_history_is_portable_archive(self):
        self.closed('.claude/longdev/done')
        self.apply()
        self.assertTrue((self.root / 'docs/longdev/archive/done/PLAN.md').exists())
        self.assertFalse((self.root / 'docs/longdev/done').exists())
        self.track(); self.apply()
        self.assertFalse((self.root / '.claude/longdev/done').exists())

    def test_closed_label_does_not_hide_open_work_failed_gate_or_pending_acceptance(self):
        self.closed('.claude/longdev/checklist', '- [ ] unfinished\n')
        self.closed('.claude/longdev/failed')
        self.put('.claude/longdev/failed/gates/final.md', '通过过一次，现在失败')
        self.task('.claude/longdev/no-proof', '已完成')
        self.task('.claude/autopilot/prod', '目标达成', '**验收状态**：待验收\n', kind='autopilot')
        result = self.apply()
        classified = {t['name']: t['classification'] for t in result['tasks']}
        self.assertEqual(classified, {'prod':'active','checklist':'retain','failed':'retain','no-proof':'retain'})
        self.assertTrue((self.root / 'docs/autopilot/prod/CHARTER.md').exists())
        self.assertFalse((self.root / 'docs/longdev/archive').exists())

    def test_budget_stop_is_active_not_complete(self):
        self.task('.claude/autopilot/prod', '预算停止', '**验收状态**：待检查', kind='autopilot')
        self.assertEqual(self.apply()['tasks'][0]['classification'], 'active')

    def test_active_dependency_transitive_closure_keeps_closed_records(self):
        self.task('.claude/longdev/a', extra='[b](../b/PLAN.md)')
        self.closed('.claude/longdev/b', '[c](../c/PLAN.md)')
        self.closed('.claude/longdev/c')
        result = self.apply()
        self.assertEqual({t['name']:t['classification'] for t in result['tasks']}, {'a':'active','b':'referenced_closed','c':'referenced_closed'})
        self.assertTrue((self.root / 'docs/longdev/c/PLAN.md').exists())
        self.assertFalse((self.root / 'docs/longdev/archive').exists())

    def test_new_docs_reference_is_updated_before_archival(self):
        self.closed('.claude/longdev/done')
        source = self.put('docs/longdev/live/PLAN.md', '**目标**：live\n**状态**：执行中\n[done](../../../.claude/longdev/done/PLAN.md)')
        result = self.apply()
        self.assertEqual(result['tasks'][0]['classification'], 'referenced_closed')
        self.assertIn('[done](../done/PLAN.md)', source.read_text())
        self.assertIn('docs/longdev/live/PLAN.md', result['tracking_pending'])
        self.track(); self.apply()
        self.assertTrue((source.parent / '../done/PLAN.md').resolve().is_file())

    def test_unknown_dependencies_and_missing_evidence_preserve_sources(self):
        self.task('.claude/longdev/a', extra='[b](../b/PLAN.md)')
        self.task('.claude/longdev/b', '已完成', '[evidence](evidence/missing.log)')
        result = self.apply()
        self.assertEqual({t['classification'] for t in result['tasks']}, {'retain'})
        self.assertFalse((self.root / 'docs/longdev/a').exists())
        self.assertTrue((self.root / '.claude/longdev/a/PLAN.md').exists())

    def test_identical_duplicates_deduplicate_but_conflicting_tasks_do_not_choose_winner(self):
        self.task('.claude/longdev/t')
        self.task(' .claude/longdev/t')
        result = self.apply()
        self.assertEqual([a['action'] for a in result['actions']].count('deduplicate'), 1)
        self.track(); self.apply()
        self.assertFalse((self.root / '.claude/longdev/t').exists())
        self.assertFalse((self.root / ' .claude/longdev/t').exists())
        self.task('.claude/longdev/x', extra='one')
        self.task(' .claude/longdev/x', extra='two')
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse((self.root / 'docs/longdev/x').exists())
        self.assertTrue((self.root / '.claude/longdev/x/PLAN.md').exists())

    def test_existing_destination_conflict_preserved(self):
        self.task()
        target = self.put('docs/longdev/t/PLAN.md', 'user-owned')
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(target.read_text(), 'user-owned')
        self.assertTrue((self.root / '.claude/longdev/t/PLAN.md').exists())

    def test_unknown_file_inside_task_is_not_archived(self):
        self.task()
        unknown = self.put('.claude/longdev/t/client.json', '{"secret":"preserve"}')
        self.apply(); self.track(); self.apply()
        self.assertEqual(unknown.read_text(), '{"secret":"preserve"}')
        self.assertFalse((self.root / '.claude/longdev/t/PLAN.md').exists())

    def test_index_exists_but_wrong_blob_prevents_archive(self):
        self.task(); self.apply(); self.track()
        current = self.put('docs/longdev/t/PLAN.md', 'new legitimate docs state')
        result = self.apply()
        self.assertEqual(result['status'], 'awaiting_tracking')
        self.assertTrue((self.root / '.claude/longdev/t/PLAN.md').exists())
        self.assertEqual(current.read_text(), 'new legitimate docs state')
        self.track(); self.apply()
        self.assertFalse((self.root / '.claude/longdev/t/PLAN.md').exists())

    def test_required_evidence_survives_git_only_machine_transfer(self):
        self.task(extra='[log](evidence/run.log)\n[image](evidence/image.png)')
        self.put('.claude/longdev/t/evidence/run.log', 'actual exit=0\n')
        self.put('.claude/longdev/t/evidence/image.png', b'\x89PNG\x00\xff')
        backup = self.put('.claude/longdev/t/baselines/original.txt', 'untouched .claude/longdev/t/PLAN.md')
        self.apply(); self.track()
        copied = self.root / 'other-machine'
        for path in self.git('ls-files', '-z').stdout.decode().split('\0'):
            if path:
                output = copied / path; output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(self.git('show', ':' + path).stdout)
        plan = (copied / 'docs/longdev/t/PLAN.md').read_text()
        for link in history.references(plan):
            self.assertTrue((copied / 'docs/longdev/t' / link).is_file(), link)
        self.assertFalse((copied / '.work').exists())
        self.assertEqual((self.root / '.work/longdev/t/baselines/original.txt').read_bytes(), backup.read_bytes())
        self.assertTrue((self.root / '.work/longdev/t/evidence/run.log').exists())

    def test_required_baseline_or_unsupported_reference_preserves_task(self):
        self.task(extra='[baseline](baselines/original.txt)')
        self.put('.claude/longdev/t/baselines/original.txt', 'private baseline')
        self.assertEqual(self.apply()['status'], 'needs_review')
        self.assertFalse((self.root / 'docs/longdev/t').exists())

    def test_external_work_evidence_is_reported_and_prevents_portable_claim(self):
        self.task(extra='[shared log](../../.work/shared/run.log)')
        self.put('.work/shared/run.log', 'exit=0')
        result=self.apply()
        self.assertEqual(result['status'],'needs_review')
        task=next(item for item in result['tasks'] if item['name']=='t')
        self.assertTrue(any('.work/shared' in reason for reason in task['reasons']))
        self.assertTrue((self.root/'.claude/longdev/t/PLAN.md').exists())

    def test_existing_external_work_evidence_reference_is_not_silently_portable(self):
        self.task(extra='[shared log](../../../.work/shared/run.log)')
        self.put('.work/shared/run.log', 'exit=0')
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        task = next(item for item in result['tasks'] if item['name'] == 't')
        self.assertTrue(any('external:' in reason or '.work' in reason for reason in task['reasons']))
        self.assertTrue((self.root / '.claude/longdev/t/PLAN.md').exists())

    def v013(self):
        self.task()
        source = '.claude/longdev/t/PLAN.md'
        data = (self.root / source).read_bytes()
        self.put('docs/longdev/t/PLAN.md', data)
        self.put(history.LEGACY_MARKER, json.dumps({'schema':1,'state':'complete','files':[
            {'source':source,'source_sha256':common.digest(data),'target':'docs/longdev/t/PLAN.md','sha256':common.digest(data)}]}))

    def test_v013_marker_allows_new_docs_evolution_and_reports_old_forks(self):
        self.v013()
        self.put('docs/longdev/t/PLAN.md', 'new canonical edits')
        result = self.apply()
        self.assertEqual(result['status'], 'awaiting_tracking')
        self.assertEqual((self.root / 'docs/longdev/t/PLAN.md').read_text(), 'new canonical edits')
        self.put('.claude/longdev/t/PLAN.md', '**目标**：old fork\n**状态**：执行中\n')
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual((self.root / 'docs/longdev/t/PLAN.md').read_text(), 'new canonical edits')

    def test_v013_new_file_is_not_silently_reimported(self):
        self.v013()
        self.put('.claude/longdev/t/stages/new.md', 'legacy new write')
        result = self.apply()
        self.assertEqual(result['status'], 'needs_review')
        self.assertFalse((self.root / 'docs/longdev/t/stages/new.md').exists())
        self.task('.claude/longdev/fresh')
        result = self.apply()
        self.assertTrue((self.root / 'docs/longdev/fresh/PLAN.md').exists())

    def test_dry_run_is_full_read_only_preview_with_matching_apply_mapping(self):
        self.task(extra='[log](evidence/run.log)')
        self.put('.claude/longdev/t/evidence/run.log', 'log')
        before = self.snapshot()
        preview = migration.migrate(self.root, dry_run=True)
        self.assertEqual(before, self.snapshot())
        self.assertTrue(all(a['reasons'] and a['target'] and a['archive_after'] for a in preview['actions']))
        self.assertTrue(preview['tracking_pending'])
        self.assertEqual(preview['mode'], 'dry_run')
        actual = self.apply()
        self.assertEqual([(a['source'],a['target'],a['action']) for a in preview['actions']],
                         [(a['source'],a['target'],a['action']) for a in actual['actions']])

    def test_dry_run_v013_and_check_cli_touch_neither_files_mtime_nor_index(self):
        self.v013(); self.track()
        before = self.snapshot()
        for option in ('--check','--dry-run'):
            result = subprocess.run([sys.executable,'-B',str(SCRIPTS/'migrate_workspace.py'),'--project',str(self.root),option],capture_output=True,text=True)
            self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
            parsed=json.loads(result.stdout)
            self.assertIn('summary',parsed)
            if option=='--dry-run':
                self.assertTrue(parsed['actions'])
                self.assertTrue(parsed['tasks'])
        self.assertEqual(before,self.snapshot())

    def test_archive_interruption_after_first_unlink_resumes(self):
        self.task(extra='[s](stages/1.md)'); self.put('.claude/longdev/t/stages/1.md','stage')
        self.apply(); self.track()
        original=Path.unlink
        counter=[]
        def interrupt(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if str(path).endswith('.claude/longdev/t/PLAN.md'):
                counter.append(str(path)); raise OSError('after source unlink')
            return result
        with patch.object(Path,'unlink',interrupt):
            with self.assertRaisesRegex(OSError,'after source unlink'):
                self.apply()
        self.assertTrue(counter)
        result=self.apply()
        self.assertFalse((self.root/'.claude/longdev/t').exists(),result)
        self.assertTrue((self.root/'docs/longdev/t/stages/1.md').exists())

    def test_copy_interruption_source_change_and_resume(self):
        self.task(); self.put('.claude/longdev/t/stages/1.md','stage')
        original=history.atomic_write
        def crash(root,path,data):
            if path.endswith('stages/1.md'): raise OSError('copy interrupted')
            return original(root,path,data)
        with patch.object(history,'atomic_write',crash):
            with self.assertRaisesRegex(OSError,'copy interrupted'): self.apply()
        self.put('.claude/longdev/t/stages/1.md','changed')
        with self.assertRaisesRegex(ValueError,'Source changed'): self.apply()
        self.put('.claude/longdev/t/stages/1.md','stage')
        self.assertEqual(self.apply()['status'],'awaiting_tracking')

    def test_archive_collision_preserved(self):
        self.task(); preview=migration.migrate(self.root,dry_run=True)
        self.put(preview['actions'][0]['archive'],'conflicting backup')
        result=self.apply()
        self.assertEqual(result['status'],'needs_review')
        self.assertTrue((self.root/'.claude/longdev/t/PLAN.md').exists())

    def test_negative_review_missing_link_and_retained_dependency_never_archive(self):
        self.closed('.claude/longdev/negative')
        self.put('.claude/longdev/negative/reviews/final.md','not passed\n')
        self.closed('.claude/longdev/missing','[proof](proof.md)')
        self.task('.claude/longdev/uncertain','已完成','[dep](../dependency/PLAN.md)')
        self.closed('.claude/longdev/dependency')
        result=self.apply()
        self.assertEqual({t['classification'] for t in result['tasks']},{'retain'})
        self.assertFalse((self.root/'docs/longdev/archive').exists())

    def test_directory_links_and_trailing_slash_point_to_migrated_directory(self):
        self.task('.claude/longdev/active',extra='[done](../done/)')
        self.closed('.claude/longdev/done')
        self.apply();self.track();self.apply()
        plan=(self.root/'docs/longdev/active/PLAN.md').read_text()
        self.assertIn('[done](../done)',plan)
        self.assertTrue((self.root/'docs/longdev/done').is_dir())

    def test_unknown_empty_directories_are_preserved_and_reported(self):
        self.task()
        empty=self.root/'.claude/longdev/t/custom-empty';empty.mkdir()
        unknown=self.root/'.longdev/unknown-empty';unknown.mkdir(parents=True)
        self.apply();self.track();result=self.apply()
        self.assertTrue(empty.is_dir());self.assertTrue(unknown.is_dir())
        self.assertEqual(result['status'],'needs_review')
        self.assertGreaterEqual(result['summary']['unknown_files'],2)

    def test_dry_run_exposes_local_evidence_conflict_before_copying(self):
        self.task(extra='[log](evidence/run.log)')
        self.put('.claude/longdev/t/evidence/run.log','new')
        self.put('.work/longdev/t/evidence/run.log','existing')
        preview=migration.migrate(self.root,dry_run=True)
        self.assertEqual(preview['status'],'needs_review')
        self.assertTrue(any(a['action']=='conflict' and 'local' in a.get('reason','') for a in preview['actions']))
        self.apply()
        self.assertFalse((self.root/'docs/longdev/t').exists())
        self.assertEqual((self.root/'.work/longdev/t/evidence/run.log').read_text(),'existing')

    def test_ignored_new_and_migrated_destinations_block_without_mutation(self):
        self.put('.gitignore','docs/\n')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'ignored'): self.apply()
        self.assertEqual(before,self.snapshot())
        self.put('.gitignore','.claude/\n.work/\n'); self.task(); self.apply()
        self.put('.gitignore','.claude/\n.work/\ndocs/\n')
        before=self.snapshot()
        with self.assertRaisesRegex(ValueError,'ignored'): self.apply()
        self.assertEqual(before,self.snapshot())

    def test_symlink_reparse_drive_and_concurrent_lock_protection(self):
        self.task()
        for relative in ('docs','.work','.claude/longdev/t/link'):
            target=self.root/relative; target.symlink_to(self.root,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'Symlink'): self.apply()
            target.unlink()
        for relative in ('','../outside','/outside','C:/outside','C:outside','\\\\server\\share'):
            with self.assertRaisesRegex(ValueError,'Unsafe'): common.safe(self.root,relative)
        original=Path.lstat
        def reparse(path):
            return SimpleNamespace(st_file_attributes=0x400,st_mode=0o40755) if path==self.root/'docs' else original(path)
        with patch.object(Path,'lstat',reparse):
            with self.assertRaisesRegex(ValueError,'Symlink'): common.safe(self.root,'docs/t')
        with common.migration_lock(self.root):
            result=subprocess.run([sys.executable,'-B',str(SCRIPTS/'migrate_workspace.py'),'--project',str(self.root)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('workspace lock',result.stdout)

    def test_guard_resolve_and_concrete_write_check(self):
        task=task_path.resolve(str(self.root),'longdev','sample')
        self.assertEqual(task,self.root/'docs/longdev/sample')
        before=self.snapshot()
        for output in (task/'PLAN.md',self.root/'.work/longdev/sample/evidence/run.log'):
            self.assertEqual(task_path.check(str(self.root),str(task),str(output))['status'],'allowed')
        for output in (self.root/'.claude/longdev/sample/PLAN.md',self.root/' .claude/longdev/sample/PLAN.md',self.root/'docs/longdev/other/PLAN.md',Path('relative.md')):
            with self.assertRaises(ValueError): task_path.check(str(self.root),str(task),str(output))
        for name in ('archive',' sample','../outside','sample/child'):
            with self.assertRaises(ValueError): task_path.resolve(str(self.root),'longdev',name)
        self.assertEqual(before,self.snapshot())
        link=self.root/'docs';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'Redirected'): task_path.check(str(self.root),str(task),str(task/'PLAN.md'))

    def test_guard_cli_and_sibling_workspace_untouched(self):
        self.task('sibling/.claude/longdev/other')
        before=self.snapshot()
        result=subprocess.run([sys.executable,'-B',str(SCRIPTS/'task_path.py'),'resolve','--project',str(self.root),'--name','task'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['task_dir'],str(self.root/'docs/longdev/task'))
        self.assertEqual(self.apply()['status'],'no_legacy_records')
        self.assertEqual(before,self.snapshot())

    def test_reference_rewrite_preserves_json_commands_spaces_and_windows(self):
        self.task(extra='`cat .claude/longdev/t/PLAN.md`\n[title](.claude/longdev/t/PLAN.md "plan")\n[space](<notes/my plan.md>)')
        self.put('.claude/longdev/t/notes/my plan.md','notes')
        original={'command':'cat ".claude/longdev/t/PLAN.md"','win':'C:\\old space\\.claude\\longdev\\t\\notes\\my plan.md','log':'../evidence/run.log','count':4,'passed':False}
        self.put('.claude/longdev/t/notes/config.json',json.dumps(original))
        self.put('.claude/longdev/t/evidence/run.log','log')
        result=self.apply()
        self.assertEqual(result['status'],'awaiting_tracking',result)
        text=(self.root/'docs/longdev/t/PLAN.md').read_text()
        self.assertIn('`cat docs/longdev/t/PLAN.md`',text)
        self.assertIn('[title](PLAN.md "plan")',text)
        actual=json.loads((self.root/'docs/longdev/t/notes/config.json').read_text())
        self.assertEqual(actual['command'],'cat "docs/longdev/t/PLAN.md"')
        self.assertEqual(actual['win'],'docs/longdev/t/notes/my plan.md')
        self.assertEqual(actual['count'],4);self.assertIs(actual['passed'],False)


if __name__=='__main__': unittest.main()
