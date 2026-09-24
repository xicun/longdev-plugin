"""项目问题记录：标准库、单文件事务、乐观版本检查。"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from datetime import datetime, timezone


class ReportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReportError(message)


def nonempty(data, *keys):
    require(isinstance(data, dict), '预期 JSON object')
    for key in keys:
        require(isinstance(data.get(key), str) and data[key].strip(), f"缺少非空文本: {key}")


def quality_refs(refs):
    require(isinstance(refs, list), 'quality_refs 须为数组')
    for ref in refs:
        nonempty(ref, 'kind', 'id', 'reference')
        require(ref['kind'] in ('requirement', 'acceptance', 'test_case', 'test_run'), '未知 quality_refs kind')


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    require(isinstance(relative, str) and relative.strip() == relative, "路径须非空且无首尾空白")
    path = Path(relative)
    require(relative and not path.is_absolute() and not path.drive and '..' not in path.parts,
            f"须为项目内相对路径: {relative}")
    target = root / path
    for part in [target, *target.parents]:
        if part == root:
            break
        if part.exists() or part.is_symlink():
            flags = part.lstat()
            require(not part.is_symlink() and not (getattr(flags, 'st_file_attributes', 0) &
                    getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 1024)), f"拒绝链接/reparse: {part}")
    require(target.resolve().is_relative_to(root), f"项目外路径: {relative}")
    return target


def atomic_json(path, data):
    fd, temporary = tempfile.mkstemp(prefix='.bug-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def blank():
    return dict(schema=1, revision=0, next_bug=1, next_feedback=1, issues={}, feedback={})


def resolve(db, bug):
    require(bug in db['issues'], f"不存在问题: {bug}")
    visited = set()
    while db['issues'][bug].get('alias_of'):
        require(bug not in visited, "别名循环")
        visited.add(bug)
        bug = db['issues'][bug]['alias_of']
        require(bug in db['issues'], f"别名目标不存在: {bug}")
    return db['issues'][bug]


def structural(db):
    require(isinstance(db, dict) and db.get('schema') == 1, "不支持或损坏的 schema")
    for field in ('revision', 'next_bug', 'next_feedback'):
        require(type(db.get(field)) is int and db[field] >= (0 if field == 'revision' else 1), f"损坏字段: {field}")
    for field in ('issues', 'feedback'):
        require(isinstance(db.get(field), dict), f"损坏字段: {field}")
    for ident, issue in db['issues'].items():
        require(isinstance(issue, dict), f'损坏问题结构: {ident}')
        require(re.fullmatch(r'BUG-\d{4,}', ident) and issue['id'] == ident, f"无效问题 ID: {ident}")
        require(int(ident[4:]) < db['next_bug'], "next_bug 会重用已有编号")
        require(issue['status'] in ('triage', 'investigating', 'verification', 'acceptance', 'closed', 'merged'), "无效问题状态")
        for field in ('history', 'repairs', 'recurrences', 'relations'):
            require(isinstance(issue.get(field), list) and all(isinstance(row, dict) for row in issue[field]), f'损坏问题字段: {field}')
        require(isinstance(issue.get('investigations'), dict) and all(isinstance(row, dict) for row in issue['investigations'].values()), '损坏 investigations')
        for field in ('verification', 'acceptance', 'investigation'):
            require(issue.get(field) is None or isinstance(issue[field], dict), f'损坏问题字段: {field}')
        quality_refs(issue.get('quality_refs', []))
        resolve(db, ident)
        for relation in issue['relations']:
            require(relation['target'] in db['issues'], "关联目标不存在")
    for ident, feedback in db['feedback'].items():
        require(re.fullmatch(r'FB-\d{4,}', ident) and feedback['id'] == ident, f"无效反馈 ID: {ident}")
        require(int(ident[3:]) < db['next_feedback'], "next_feedback 会重用已有编号")
        nonempty(feedback, 'raw', 'source')
        require(isinstance(feedback['items'], list) and feedback['items'], "反馈条目为空")
        ids = [item['id'] for item in feedback['items']]
        require(len(set(ids)) == len(ids), "反馈条目 ID 重复")
        for item in feedback['items']:
            nonempty(item, 'id', 'text')
            route = item.get('route')
            if route:
                nonempty(route, 'kind', 'reason')
                require(route['kind'] in ('bug', 'requirement', 'clarify'), "未知反馈路由")
                if route['kind'] == 'bug':
                    resolve(db, route['target'])
                else:
                    nonempty(route, 'destination')


def event(issue, kind, data):
    issue['history'].append(dict(at=now(), epoch=issue['epoch'], kind=kind, data=copy.deepcopy(data)))


def invalidate(issue):
    issue['epoch'] += 1
    issue['verification'] = None
    issue['acceptance'] = None
    issue['status'] = 'investigating'


def evidence(root, entries):
    require(isinstance(entries, list) and entries, "至少提供一个证据/产物文件")
    for item in entries:
        nonempty(item, 'path', 'sha256')
        path = safe_path(root, item['path'])
        require(path.is_file(), f"证据/产物不存在: {item['path']}")
        require(digest(path) == item['sha256'], f"证据/产物哈希失效: {item['path']}")


ANALYSIS = ('previous_repair', 'old_cause', 'support', 'counterevidence',
            'runtime_version', 'coverage', 'missed_validation', 'experiment', 'result')


def investigation_errors(issue):
    missing = []
    for recurrence in issue['recurrences']:
        repair = recurrence['repair']
        analysis = issue.get('investigations', {}).get(repair, {})
        missing.extend(repair + '/' + key for key in ANALYSIS if not isinstance(analysis.get(key), str) or not analysis[key].strip())
        if analysis.get('previous_repair') != repair:
            missing.append(repair + '/previous_repair_binding')
    return missing


def verification_errors(root, issue):
    errors = []
    verification = issue.get('verification')
    if not verification:
        return ['缺少当前验证']
    if verification.get('result') != 'pass' or verification.get('reproduced') is not True or verification.get('coverage') != 'complete':
        errors.append('验证未复现、失败或覆盖不完整')
    if verification.get('epoch') != issue['epoch']:
        errors.append('验证版本失效')
    if not issue['repairs'] or verification.get('repair') != issue['repairs'][-1]['id']:
        errors.append('验证修复绑定失效')
    try:
        evidence(root, verification['evidence'])
        evidence(root, verification['artifacts'])
    except (ReportError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    errors.extend('复发调查缺项: ' + key for key in investigation_errors(issue))
    return errors


def audit(root, db, bugs=None, feedback=None, delivery=False):
    errors = []
    scoped = bugs is not None or feedback is not None
    selected = ([] if scoped else db['feedback'].keys()) if feedback is None else feedback
    selected_bugs = set(([] if scoped else db['issues']) if bugs is None else bugs)
    for ident in selected:
        require(ident in db['feedback'], f"不存在反馈: {ident}")
        for item in db['feedback'][ident]['items']:
            if not item.get('route'):
                errors.append(f"{ident}/{item['id']}: 缺处理去向")
            elif item['route']['kind'] == 'bug':
                selected_bugs.add(resolve(db, item['route']['target'])['id'])
    pending = list(selected_bugs)
    while pending:
        current = resolve(db, pending.pop())
        for relation in current['relations']:
            if relation['kind'] == 'split' and relation['target'] not in selected_bugs:
                selected_bugs.add(relation['target'])
                pending.append(relation['target'])
    for ident in sorted(selected_bugs):
        issue = resolve(db, ident)
        if issue['status'] in ('acceptance', 'closed'):
            errors.extend(f"{ident}: {error}" for error in verification_errors(root, issue))
            for relation in issue['relations']:
                if relation['kind'] == 'split' and resolve(db, relation['target'])['status'] not in ('acceptance', 'closed'):
                    errors.append(f"{ident}: 拆分子问题 {relation['target']} 未闭环")
        if delivery:
            errors.extend(f"{ident}: 复发调查缺项 {key}" for key in investigation_errors(issue))
            if issue['status'] not in ('acceptance', 'closed'):
                errors.append(f"{ident}: 尚未完成验证 ({issue['status']})")
        if issue['status'] == 'closed':
            acceptance = issue.get('acceptance') or {}
            if acceptance.get('decision') != 'accepted' or acceptance.get('kind') not in ('user', 'authorized_auto') or not acceptance.get('source'):
                errors.append(f"{ident}: 缺验收依据")
            if acceptance.get('kind') == 'authorized_auto' and not all(acceptance.get(k) for k in ('authorization', 'criteria', 'assessor')):
                errors.append(f"{ident}: 缺自动验收授权范围/标准/验收者")
    return errors


def mutate(root, db, command, payload):
    p = payload
    if command == 'create':
        nonempty(p, 'title', 'goal', 'expected', 'actual', 'conditions', 'scope', 'next_step', 'close_condition')
        ident = f"BUG-{db['next_bug']:04d}"
        db['next_bug'] += 1
        issue = dict(id=ident, status='triage', epoch=0, facts=p.get('facts', []), hypotheses=p.get('hypotheses', []), quality_refs=p.get('quality_refs', []),
                     history=[], repairs=[], recurrences=[], relations=[], verification=None, acceptance=None,
                     investigation=None, investigations={}, **{key: p[key] for key in ('title', 'goal', 'expected', 'actual', 'conditions', 'scope', 'next_step', 'close_condition')})
        require(isinstance(issue['facts'], list) and isinstance(issue['hypotheses'], list), 'facts/hypotheses 须为数组')
        db['issues'][ident] = issue
        event(issue, 'create', p)
        return {'id': ident}
    if command == 'feedback':
        nonempty(p, 'raw', 'source')
        require(isinstance(p.get('items'), list) and p['items'], 'items 须为非空数组')
        ident = f"FB-{db['next_feedback']:04d}"
        items = []
        for item in p['items']:
            nonempty(item, 'id', 'text')
            require(item['text'] in p['raw'], '条目 text 须保留原始反馈中的原文片段')
            items.append(dict(id=item['id'], text=item['text'], route=None, history=[]))
        db['next_feedback'] += 1
        db['feedback'][ident] = dict(id=ident, raw=p['raw'], source=p['source'], at=now(), created_revision=db['revision']+1, items=items)
        return {'id': ident}
    if command == 'route':
        require(p.get('feedback') in db['feedback'], '反馈不存在')
        candidates = [i for i in db['feedback'][p['feedback']]['items'] if i['id'] == p.get('item')]
        require(len(candidates) == 1, '反馈条目不存在')
        item = candidates[0]
        route = p.get('route', {})
        nonempty(route, 'kind', 'reason')
        require(route['kind'] in ('bug', 'requirement', 'clarify'), '未知路由')
        if route['kind'] == 'bug':
            nonempty(route, 'target', 'confidence')
            require(route['confidence'] in ('confirmed', 'suspected'), 'confidence 须 confirmed/suspected')
            issue = resolve(db, route['target'])
            if issue['repairs'] and db['feedback'][p['feedback']]['created_revision'] > issue['repairs'][-1]['revision']:
                repair = issue['repairs'][-1]['id']
                if repair not in [r['repair'] for r in issue['recurrences']]:
                    issue['recurrences'].append(dict(repair=repair, feedback=p['feedback'], item=p['item'], at=now()))
                    invalidate(issue)
                    issue['investigation'] = None
                    event(issue, 'recurrence', issue['recurrences'][-1])
            event(issue, 'feedback', dict(feedback=p['feedback'], item=p['item'], route=route))
        else:
            nonempty(route, 'destination')
        item['history'].append(dict(at=now(), previous=item['route'], route=copy.deepcopy(route)))
        item['route'] = copy.deepcopy(route)
        return {'feedback': p['feedback'], 'item': p['item']}
    nonempty(p, 'id')
    issue = resolve(db, p['id'])
    if command == 'update':
        fields = p.get('fields', {})
        allowed = {'title', 'goal', 'expected', 'actual', 'conditions', 'scope', 'facts', 'hypotheses', 'next_step', 'close_condition', 'quality_refs'}
        require(fields and set(fields) <= allowed, 'fields 为空或包含非可编辑字段')
        for key, value in fields.items():
            if key == 'quality_refs':
                quality_refs(value)
            elif key in ('facts', 'hypotheses'):
                require(isinstance(value, list), f'{key} 须数组')
            else:
                nonempty(fields, key)
        issue.update(copy.deepcopy(fields))
        invalidate(issue)
    elif command == 'repair':
        nonempty(p, 'version', 'summary', 'cause', 'coverage')
        invalidate(issue)
        issue['repairs'].append(dict(id=f"FIX-{len(issue['repairs'])+1:04d}", at=now(), epoch=issue['epoch'], revision=db['revision']+1,
                                     recurrence=len(issue['recurrences']), **{k: p[k] for k in ('version', 'summary', 'cause', 'coverage')}))
        issue['status'] = 'verification'
    elif command == 'investigate':
        require(issue['recurrences'], '没有复发记录')
        nonempty(p, *ANALYSIS)
        require(p['previous_repair'] in [r['repair'] for r in issue['recurrences']], 'previous_repair 不匹配复发修复')
        issue['investigation'] = dict(recurrence=len(issue['recurrences']), **{k: p[k] for k in ANALYSIS})
        issue.setdefault('investigations', {})[p['previous_repair']] = copy.deepcopy(issue['investigation'])
    elif command == 'verify':
        require(issue['repairs'], '缺少修复尝试')
        require(not issue['repairs'][-1].get('inherited_from'), '合并后必须登记本问题的新修复，不能直接验证继承修复')
        require(issue['repairs'][-1]['epoch'] == issue['epoch'], '当前改动尚未登记新的修复尝试')
        require(issue['repairs'][-1]['recurrence'] == len(issue['recurrences']), '复发后尚未登记新修复')
        require(not investigation_errors(issue), '复发调查不完整: ' + ', '.join(investigation_errors(issue)))
        children = [r['target'] for r in issue['relations'] if r['kind'] == 'split']
        child_errors = audit(root, db, bugs=children, delivery=True) if children else []
        require(not child_errors, '拆分子问题未闭环: ' + '; '.join(child_errors))
        nonempty(p, 'method', 'expected', 'actual', 'runtime_version')
        require(p['runtime_version'] == issue['repairs'][-1]['version'], '实际运行版本不匹配修复版本')
        require(p.get('reproduced') is True and p.get('result') == 'pass' and p.get('coverage') == 'complete', '未复现、失败或局部验证不能进入待验收')
        evidence(root, p.get('evidence'))
        evidence(root, p.get('artifacts'))
        old_hashes = {e['sha256'] for h in issue['history'] if h['kind'] in ('verify', 'inherited_verify') and h['epoch'] != issue['epoch'] for e in h['data']['evidence']}
        require(any(e['sha256'] not in old_hashes for e in p['evidence']), '不能复用旧轮验证证据；重新运行并记录当前产物结果')
        issue['verification'] = dict(copy.deepcopy(p), epoch=issue['epoch'], repair=issue['repairs'][-1]['id'])
        issue['acceptance'] = None
        issue['status'] = 'acceptance'
    elif command == 'accept':
        require(issue['status'] == 'acceptance', '必须先进入待验收')
        require(not verification_errors(root, issue), '验证已失效: ' + '; '.join(verification_errors(root, issue)))
        child_errors = audit(root, db, bugs=[issue['id']], delivery=True)
        require(not child_errors, '验收依赖未闭环: ' + '; '.join(child_errors))
        nonempty(p, 'kind', 'source', 'decision')
        require(p['kind'] in ('user', 'authorized_auto') and p['decision'] == 'accepted', '无有效验收结论')
        if p['kind'] == 'authorized_auto':
            nonempty(p, 'authorization', 'criteria', 'assessor')
        issue['acceptance'] = copy.deepcopy(p)
        issue['status'] = 'closed'
    elif command == 'relate':
        nonempty(p, 'target', 'kind', 'reason')
        other = resolve(db, p['target'])
        require(other['id'] != issue['id'], '不能关联自身或建立别名循环')
        require(p['kind'] in ('related', 'split', 'merge'), 'kind 须 related/split/merge')
        if p['kind'] == 'split':
            seen, pending = set(), [other['id']]
            while pending:
                current = resolve(db, pending.pop())
                require(current['id'] != issue['id'], '拆分依赖不能成环')
                if current['id'] not in seen:
                    seen.add(current['id'])
                    pending.extend(r['target'] for r in current['relations'] if r['kind'] == 'split')
            invalidate(issue)
        issue['relations'].append(dict(target=other['id'], kind=p['kind'], reason=p['reason']))
        other['relations'].append(dict(target=issue['id'], kind='split_from' if p['kind'] == 'split' else 'related', reason=p['reason']))
        if p['kind'] == 'merge':
            require(not any(r['kind'] in ('split', 'split_from') for r in issue['relations'] + other['relations']),
                    '含拆分依赖的问题不能直接合并；先明确依赖与范围，保留为 related')
            issue['alias_of'] = other['id']
            issue['status'] = 'merged'
            for repair in issue['repairs']:
                other['repairs'].append(dict(copy.deepcopy(repair), id=issue['id'] + '/' + repair['id'], inherited_from=issue['id']))
            other['repairs'].sort(key=lambda r: r['revision'])
            for history in issue['history']:
                if history['kind'] in ('verify', 'inherited_verify'):
                    event(other, 'inherited_verify', dict(evidence=history['data']['evidence'], source=issue['id']))
            for recurrence in issue['recurrences']:
                inherited = dict(copy.deepcopy(recurrence), repair=issue['id'] + '/' + recurrence['repair'], inherited_from=issue['id'])
                other['recurrences'].append(inherited)
                prior = issue.get('investigations', {}).get(recurrence['repair'])
                if prior:
                    other.setdefault('investigations', {})[inherited['repair']] = dict(copy.deepcopy(prior), previous_repair=inherited['repair'])
            if issue['recurrences']:
                other['investigation'] = None
            invalidate(other)
        event(other, 'relation', p)
    else:
        raise ReportError(f'未知命令: {command}')
    event(issue, command, p)
    return {'id': issue['id'], 'status': issue['status']}


def summary(db):
    return dict(schema=1, revision=db['revision'], issues=[dict(id=i['id'], title=i['title'], status=i['status'],
                goal=i['goal'], conditions=i['conditions'], actual=i['actual'], next_step=i['next_step'],
                recurrence_count=len(i['recurrences']), alias_of=i.get('alias_of')) for i in db['issues'].values()],
                feedback=[dict(id=f['id'], source=f['source'], unrouted=[i['id'] for i in f['items'] if not i['route']]) for f in db['feedback'].values()])


WRITES = ('init', 'create', 'feedback', 'route', 'update', 'repair', 'investigate', 'verify', 'accept', 'relate', 'reindex')


def execute(args):
    root = Path(args.project)
    require(root.is_absolute() and root.is_dir(), '--project 须为已存在绝对目录')
    root = root.resolve()
    base = safe_path(root, 'docs/bugs')
    path = safe_path(root, 'docs/bugs/reports.json')
    index = safe_path(root, 'docs/bugs/index.json')
    lock = safe_path(root, 'docs/bugs/.write.lock')
    writing = args.command in WRITES
    locked = False
    try:
        if writing:
            base.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                raise ReportError('档案写锁存在；检查写入者/中断现场，不自动抢锁')
            with os.fdopen(fd, 'w') as stream:
                stream.write(str(os.getpid()))
            locked = True
        if args.command == 'init':
            require(not path.exists(), '档案已存在，不覆盖')
            db = blank()
            atomic_json(path, db)
            return dict(revision=0)
        require(path.is_file(), '没有问题档案；先 init')
        original = path.read_bytes()
        db = json.loads(original.decode('utf-8-sig'))
        structural(db)
        if args.command in WRITES and args.command != 'reindex':
            require(args.expected_revision is not None and args.expected_revision == db['revision'], f"revision 冲突；当前 {db['revision']}")
            require(args.input, '写操作需要 --input JSON文件')
            payload = json.loads(Path(args.input).read_text('utf-8-sig'))
            require(isinstance(payload, dict), 'input 须 JSON object')
            result = mutate(root, db, args.command, payload)
            db['revision'] += 1
            structural(db)
            require(path.read_bytes() == original, '写入期间档案被外部修改')
            atomic_json(path, db)
            return dict(result, revision=db['revision'], index_stale=True)
        if args.command == 'reindex':
            atomic_json(index, summary(db))
            return dict(revision=db['revision'], index='docs/bugs/index.json')
        if args.command == 'status':
            data = summary(db)
            data['issues'] = [i for i in data['issues'] if i['status'] not in ('closed', 'merged')]
            return data
        if args.command == 'show':
            require(args.id, 'show 需要 --id BUG/FB编号')
            require(args.id in db['issues'] or args.id in db['feedback'], '编号不存在')
            return dict(revision=db['revision'], record=db['issues'].get(args.id, db['feedback'].get(args.id)))
        if args.command == 'search':
            terms = (args.query or '').casefold().split()
            rows = []
            for issue in db['issues'].values():
                hay = json.dumps(issue, ensure_ascii=False).casefold()
                score = sum(term in hay for term in terms)
                if score or not terms:
                    rows.append(dict(id=issue['id'], title=issue['title'], status=issue['status'], score=score, alias_of=issue.get('alias_of')))
            rows.sort(key=lambda x: (-x['score'], x['id']))
            return dict(revision=db['revision'], kind='lexical_candidates_only', results=rows[args.offset:args.offset+args.limit], total=len(rows))
        if args.command == 'check':
            errors = audit(root, db, args.bug, args.feedback, args.delivery)
            return dict(revision=db['revision'], ok=not errors, errors=errors)
        raise ReportError('未知命令')
    finally:
        if locked:
            lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('command', choices=(*WRITES, 'status', 'show', 'search', 'check'))
    parser.add_argument('--input')
    parser.add_argument('--expected-revision', type=int)
    parser.add_argument('--id')
    parser.add_argument('--query')
    parser.add_argument('--offset', type=int, default=0)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--bug', action='append')
    parser.add_argument('--feedback', action='append')
    parser.add_argument('--delivery', action='store_true')
    args = parser.parse_args()
    try:
        require(args.offset >= 0 and 1 <= args.limit <= 100, 'offset >= 0; limit 1..100')
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get('ok', True) else 1
    except (ReportError, OSError, ValueError, KeyError, TypeError, AttributeError, IndexError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
