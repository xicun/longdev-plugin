import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'skills/bug-reports/scripts/bug_reports.py'


class BugReportsTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / '.work'
        work.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=work)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.revision = 0
        self.serial = 0
        self.call('init')

    @property
    def database(self):
        return self.project / 'docs/bugs/reports.json'

    def data(self):
        return json.loads(self.database.read_text('utf-8'))

    def call(self, command, payload=None, extra=(), expected=0, revision=None):
        args = [sys.executable, '-B', str(CLI), '--project', str(self.project), command]
        if payload is not None:
            self.serial += 1
            source = self.project / f'input-{self.serial}.json'
            source.write_text(json.dumps(payload, ensure_ascii=False), 'utf-8')
            args += ['--input', str(source), '--expected-revision', str(self.revision if revision is None else revision)]
        result = subprocess.run(args + list(extra), capture_output=True, text=True, encoding='utf-8',
                                env=dict(os.environ, PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        output = json.loads(result.stdout if result.stdout else result.stderr)
        if expected == 0 and 'revision' in output:
            self.revision = output['revision']
        return output

    def create(self, title='保存后列表旧值'):
        return self.call('create', dict(title=title, goal='修改资料', expected='新值一致', actual='仍是旧值',
                  conditions='保存返回列表', scope='资料与列表', facts=['用户报告'], hypotheses=['缓存待查'],
                  next_step='复现', close_condition='两入口一致'))['id']

    def feedback(self, texts=('保存仍旧值',), source='用户第二轮'):
        return self.call('feedback', dict(raw='；'.join(texts), source=source,
                    items=[dict(id=str(i+1), text=t) for i, t in enumerate(texts)]))['id']

    def route(self, feedback, bug, item='1', **kwargs):
        return self.call('route', dict(feedback=feedback, item=item, route=dict(kind='bug', target=bug,
                            confidence='suspected', reason='目标和条件一致')), **kwargs)

    def repair(self, bug, version='build-1'):
        self.call('repair', dict(id=bug, version=version, summary='更新缓存', cause='缓存失效缺口', coverage='两入口'))

    def investigate(self, bug, previous_repair=None):
        issue = self.data()['issues'][bug]
        self.call('investigate', dict(id=bug, previous_repair=previous_repair or issue['recurrences'][-1]['repair'], old_cause='缓存',
                    support='请求新值', counterevidence='第二入口旧值', runtime_version='build-1', coverage='遗漏第二入口',
                    missed_validation='只测试接口', experiment='两入口回放', result='第二入口稳定失败'))

    def evidence(self, name, text):
        path = self.project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, 'utf-8')
        return dict(path=name, sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def verification(self, bug, run='1', version='build-1'):
        return dict(id=bug, method='两入口回放', expected='一致', actual='修复前失败后通过', runtime_version=version,
                    reproduced=True, result='pass', coverage='complete',
                    artifacts=[self.evidence('src/app.py', 'version=' + version)],
                    evidence=[self.evidence(f'docs/bugs/evidence/run-{run}.json', 'result-pass-' + run)])

    def close(self, bug):
        self.call('accept', dict(id=bug, kind='user', source='用户明确验收本问题', decision='accepted'))

    def test_independent_lifecycle_index_rebuild_and_history(self):
        bug = self.create()
        feedback = self.feedback()
        self.route(feedback, bug)
        self.repair(bug)
        self.call('verify', self.verification(bug))
        self.assertEqual(self.data()['issues'][bug]['status'], 'acceptance')
        self.close(bug)
        original = self.database.read_bytes()
        self.call('reindex')
        index = self.project / 'docs/bugs/index.json'
        previous = index.read_bytes()
        index.unlink()
        self.call('reindex')
        self.assertEqual(previous, index.read_bytes())
        self.assertEqual(original, self.database.read_bytes())
        shown = self.call('show', extra=['--id', feedback])['record']
        self.assertEqual(shown['raw'], '保存仍旧值')
        issue = self.call('show', extra=['--id', bug])['record']
        self.assertEqual(issue['facts'], ['用户报告'])
        self.assertEqual(issue['hypotheses'], ['缓存待查'])
        self.assertEqual([h['kind'] for h in issue['history']], ['create', 'feedback', 'repair', 'verify', 'accept'])
        self.call('check', extra=['--feedback', feedback, '--delivery'])
        self.assertEqual(self.call('search', extra=['--query', '旧值'])['results'][0]['status'], 'closed')

    def test_four_routes_and_missing_bad_reference_atomic(self):
        old, new = self.create(), self.create('导出报错')
        feedback = self.feedback(('还是旧值', '导出报错', '批量操作', '再补充'))
        self.route(feedback, old)
        self.route(feedback, new, '2')
        self.call('route', dict(feedback=feedback, item='3', route=dict(kind='requirement', destination='PLAN.md#R12', reason='新行为')))
        result = self.call('check', extra=['--feedback', feedback], expected=1)
        self.assertIn(feedback + '/4', result['errors'][0])
        before = self.database.read_bytes()
        self.route(feedback, 'BUG-9999', '4', expected=2)
        self.assertEqual(before, self.database.read_bytes())
        self.call('route', dict(feedback=feedback, item='4', route=dict(kind='clarify', destination='待提供页面', reason='信息缺少')))
        self.call('check', extra=['--feedback', feedback])
        self.assertEqual(len(self.data()['feedback'][feedback]['items']), 4)

    def test_duplicate_items_and_nonverbatim_input_rejected(self):
        before = self.database.read_bytes()
        for items in ([dict(id='1', text='原文'), dict(id='1', text='原文')], [dict(id='1', text='捏造')]):
            self.call('feedback', dict(raw='原文', source='用户', items=items), expected=2)
            self.assertEqual(before, self.database.read_bytes())

    def test_recurrence_same_round_dedup_and_next_repair(self):
        bug = self.create()
        old = self.feedback(('旧反馈', '同轮补述'))
        self.route(old, bug)
        self.repair(bug)
        self.call('verify', self.verification(bug))
        self.close(bug)
        self.route(old, bug, '2')
        self.assertEqual(self.data()['issues'][bug]['recurrences'], [])
        new = self.feedback(('还是旧值', '又没保存'))
        self.route(new, bug)
        self.route(new, bug, '2')
        self.route(new, bug)
        issue = self.data()['issues'][bug]
        self.assertEqual(len(issue['recurrences']), 1)
        self.assertEqual(issue['status'], 'investigating')
        self.assertIsNone(issue['verification'])
        self.call('accept', dict(id=bug, kind='user', source='旧验收', decision='accepted'), expected=2)
        self.call('check', extra=['--feedback', new, '--delivery'], expected=1)
        self.repair(bug, 'build-2')
        self.call('verify', self.verification(bug, '2', 'build-2'), expected=2)
        self.investigate(bug)
        self.call('verify', self.verification(bug, '2', 'build-2'))
        self.route(new, bug)
        self.assertEqual(len(self.data()['issues'][bug]['recurrences']), 1)
        later = self.feedback(('第二修复后仍旧值',))
        self.route(later, bug)
        self.assertEqual(len(self.data()['issues'][bug]['recurrences']), 2)

    def test_evidence_not_reused_after_repair_and_stale_artifact_detected(self):
        bug = self.create()
        self.repair(bug)
        old = self.verification(bug)
        self.call('verify', old)
        self.call('update', dict(id=bug, fields={'next_step': '另一个入口'}))
        self.call('verify', old, expected=2)
        self.repair(bug)
        self.call('verify', old, expected=2)
        self.call('verify', self.verification(bug, '2'))
        (self.project / 'src/app.py').write_text('changed', 'utf-8')
        self.call('check', extra=['--bug', bug], expected=1)
        self.call('accept', dict(id=bug, kind='user', source='用户', decision='accepted'), expected=2)

    def test_missing_unreproduced_partial_and_acceptance_gates(self):
        bug = self.create()
        self.call('accept', dict(id=bug, kind='user', source='用户', decision='accepted'), expected=2)
        self.repair(bug)
        good = self.verification(bug)
        for patch in ({'reproduced': False}, {'coverage': 'partial'}, {'result': 'fail'}, {'runtime_version': 'wrong'}, {'evidence': []}):
            self.call('verify', dict(good, **patch), expected=2)
        self.call('verify', good)
        self.call('accept', dict(id=bug, kind='authorized_auto', source='task', decision='accepted'), expected=2)
        self.call('accept', dict(id=bug, kind='authorized_auto', source='task', decision='accepted',
                  authorization='用户指定此问题按V01自动验收', criteria='V01回放通过', assessor='independent-agent'))
        self.call('check', extra=['--bug', bug, '--delivery'])

    def test_related_split_merge_keep_ids_and_history(self):
        first, second, third = self.create(), self.create('同现象另因'), self.create('第二入口子问题')
        self.call('relate', dict(id=first, target=second, kind='related', reason='现象相似不同根因'))
        self.call('relate', dict(id=first, target=third, kind='split', reason='独立入口独立修复'))
        self.assertEqual(self.data()['issues'][third]['relations'][0]['kind'], 'split_from')
        target = self.create('合并后的共同根因')
        old_history = self.data()['issues'][second]['history'][:]
        self.call('relate', dict(id=second, target=target, kind='merge', reason='进一步实验证明同根因'))
        old = self.call('show', extra=['--id', second])['record']
        self.assertEqual(old['alias_of'], target)
        self.assertEqual(old['history'][:len(old_history)], old_history)
        self.call('relate', dict(id=target, target=second, kind='merge', reason='循环'), expected=2)
        self.call('update', dict(id=second, fields={'next_step': '沿别名更新'}))
        self.assertEqual(self.data()['issues'][target]['next_step'], '沿别名更新')
        self.assertEqual(self.create(), 'BUG-0005')

    def test_split_invalidates_parent_and_requires_child_closure(self):
        parent, child = self.create(), self.create('子问题')
        feedback = self.feedback()
        self.route(feedback, parent)
        self.repair(parent)
        self.call('verify', self.verification(parent))
        self.call('relate', dict(id=parent, target=child, kind='split', reason='遗漏独立入口'))
        self.assertIsNone(self.data()['issues'][parent]['verification'])
        self.call('check', extra=['--feedback', feedback, '--delivery'], expected=1)
        self.call('relate', dict(id=child, target=parent, kind='split', reason='循环'), expected=2)
        self.repair(parent)
        self.call('verify', self.verification(parent, '2'), expected=2)
        self.repair(child)
        self.call('verify', self.verification(child, 'child'))
        self.call('verify', self.verification(parent, '2'))
        self.call('check', extra=['--feedback', feedback, '--delivery'])
        self.call('update', dict(id=child, fields={'next_step': '新发现'}))
        self.call('check', extra=['--bug', parent], expected=1)
        self.call('accept', dict(id=parent, kind='user', source='用户', decision='accepted'), expected=2)

    def test_merge_carries_unresolved_recurrence_gate(self):
        source, target = self.create(), self.create('合并目标')
        self.repair(source)
        feedback = self.feedback()
        self.route(feedback, source)
        self.call('relate', dict(id=source, target=target, kind='merge', reason='同根因'))
        issue = self.data()['issues'][target]
        self.assertEqual(issue['recurrences'][0]['repair'], source + '/FIX-0001')
        self.repair(target)
        self.call('verify', self.verification(target), expected=2)
        self.call('check', extra=['--bug', source, '--delivery'], expected=1)
        self.investigate(target)
        self.call('verify', self.verification(target))
        self.call('check', extra=['--feedback', feedback, '--delivery'])

    def test_merge_retains_prior_repair_for_future_recurrence_and_old_evidence(self):
        source, target = self.create(), self.create('新目标')
        self.repair(source)
        old = self.verification(source)
        self.call('verify', old)
        self.call('relate', dict(id=source, target=target, kind='merge', reason='同一根因'))
        self.call('verify', self.verification(target, 'before-new-repair'), expected=2)
        feedback = self.feedback()
        self.route(feedback, source)
        issue = self.data()['issues'][target]
        self.assertEqual(issue['recurrences'][-1]['repair'], source + '/FIX-0001')
        self.repair(target)
        self.call('verify', dict(old, id=target), expected=2)
        self.investigate(target)
        self.call('verify', dict(old, id=target), expected=2)
        self.call('verify', self.verification(target, 'merged-current'))

    def test_multiple_recurrences_each_require_analysis_after_merge(self):
        source, target = self.create(), self.create('另一个失败修复')
        for bug in (source, target):
            self.repair(bug)
            feedback = self.feedback()
            self.route(feedback, bug)
        self.call('relate', dict(id=source, target=target, kind='merge', reason='同根因但都有失败历史'))
        self.repair(target)
        self.investigate(target)
        verification = self.verification(target, 'merged')
        self.call('verify', verification, expected=2)
        self.investigate(target, 'FIX-0001')
        self.call('verify', verification)

    def test_revision_lock_and_corruption_protect_original(self):
        bug = self.create()
        before = self.database.read_bytes()
        self.call('update', dict(id=bug, fields={'next_step': 'stale'}), revision=0, expected=2)
        self.assertEqual(before, self.database.read_bytes())
        lock = self.project / 'docs/bugs/.write.lock'
        lock.write_text('other writer', 'utf-8')
        self.call('repair', dict(id=bug, version='v1', summary='s', cause='c', coverage='all'), expected=2)
        self.assertEqual(lock.read_text('utf-8'), 'other writer')
        self.assertEqual(before, self.database.read_bytes())
        lock.unlink()
        self.database.write_text('{broken', 'utf-8')
        self.call('reindex', expected=2)
        self.call('init', expected=2)
        self.assertEqual(self.database.read_text('utf-8'), '{broken')

    def test_path_escape_and_id_counter_corruption(self):
        bug = self.create()
        self.repair(bug)
        payload = self.verification(bug)
        payload['evidence'][0]['path'] = '../outside.json'
        before = self.database.read_bytes()
        self.call('verify', payload, expected=2)
        self.assertEqual(before, self.database.read_bytes())
        data = self.data()
        data['next_bug'] = 1
        self.database.write_text(json.dumps(data), 'utf-8')
        self.call('status', expected=2)

    def test_malformed_investigations_diagnosed_without_write(self):
        bug = self.create()
        data = self.data()
        data['issues'][bug]['investigations'] = []
        self.database.write_text(json.dumps(data), 'utf-8')
        before = self.database.read_bytes()
        result = self.call('check', expected=2)
        self.assertIn('investigations', result['error'])
        self.assertEqual(before, self.database.read_bytes())

    def test_scope_does_not_gate_unrelated_old_feedback(self):
        bug = self.create()
        self.feedback(('无关旧项',))
        current = self.feedback(('当前项',))
        self.route(current, bug)
        self.repair(bug)
        self.call('verify', self.verification(bug))
        self.call('check', extra=['--feedback', current, '--delivery'])
        self.call('check', expected=1)

    def test_quality_references_survive_and_do_not_imply_validation(self):
        bug = self.create()
        refs = [dict(kind='requirement', id='R01', reference='PLAN.md#R01'),
                dict(kind='test_case', id='TC-1', reference='tests/test_profile.py'),
                dict(kind='test_run', id='RUN-1', reference='docs/test-runs/1.json')]
        self.call('update', dict(id=bug, fields={'quality_refs': refs}))
        shown = self.call('show', extra=['--id', bug])['record']
        self.assertEqual(shown['quality_refs'], refs)
        self.assertEqual(shown['history'][-1]['data']['fields']['quality_refs'], refs)
        self.call('check', extra=['--bug', bug, '--delivery'], expected=1)
        self.call('update', dict(id=bug, fields={'quality_refs': [dict(kind='unknown', id='x', reference='x')]}), expected=2)

    def test_atomic_replace_failure_keeps_bytes_and_cleans_temporary(self):
        spec = importlib.util.spec_from_file_location('bug_reports_atomic_test', CLI)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        before = self.database.read_bytes()
        with patch.object(module.os, 'replace', side_effect=OSError('simulated replace failure')):
            with self.assertRaisesRegex(OSError, 'simulated replace failure'):
                module.atomic_json(self.database, {'not': 'committed'})
        self.assertEqual(before, self.database.read_bytes())
        self.assertEqual(list(self.database.parent.glob('.bug-*.tmp')), [])

    def test_linked_evidence_rejected(self):
        bug = self.create()
        self.repair(bug)
        payload = self.verification(bug)
        real = self.project / 'real-evidence'
        real.mkdir()
        linked = self.project / 'linked-evidence'
        file = real / 'result.json'
        file.write_text('actual-evidence', 'utf-8')
        if os.name == 'nt':
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(linked), str(real)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            linked.symlink_to(real, target_is_directory=True)
        self.addCleanup(lambda: linked.rmdir() if os.name == 'nt' else linked.unlink())
        payload['evidence'] = [dict(path='linked-evidence/result.json', sha256=hashlib.sha256(file.read_bytes()).hexdigest())]
        before = self.database.read_bytes()
        self.call('verify', payload, expected=2)
        self.assertEqual(before, self.database.read_bytes())


if __name__ == '__main__':
    unittest.main()
