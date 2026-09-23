"""Conservative inventory, portable migration and tracked-source archival."""
import json
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote

from workspace_common import atomic_write, digest, files, git, ignored, migration_lock, redirected, rewrite, safe, RAW

MARKER = 'docs/longdev/.migration-v014.json'
LEGACY_MARKER = 'docs/longdev/.migration-v013.json'
JOURNAL = '.work/longdev-migration/convergence-journal.json'
KINDS = ('longdev', 'autopilot')
MAIN = ('PLAN.md', 'PLAN.draft.md', 'CHARTER.md')
TOP = {*MAIN, 'BACKLOG.md', 'README.md', 'notes.md', 'context.md', 'scout-repo.md'}
TREES = {'stages', 'reviews', 'gates', 'evidence', 'context', 'notes', 'decisions', 'scout',
         'iterations', 'acceptance', 'design', 'baselines'}
TEXT = {'.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.csv'}


def read_json(root, path):
    target = safe(root, path)
    return json.loads(target.read_text('utf-8')) if target.exists() else None


def text_file(root, path):
    if Path(path).suffix.lower() not in TEXT:
        return ''
    try:
        return safe(root, path).read_text('utf-8')
    except UnicodeDecodeError:
        return ''


def source_hash(root, paths):
    return {p: digest(safe(root, p).read_bytes()) for p in paths}


def owned_relative(relative):
    parts = PurePosixPath(relative).parts
    return len(parts) == 1 and parts[0] in TOP or len(parts) > 1 and parts[0] in TREES


def classify(root, directory, kind):
    entries = files(root, directory)
    relative = {p: PurePosixPath(p).relative_to(directory).as_posix() for p in entries}
    mains = [p for p, rel in relative.items() if rel in MAIN]
    metadata = '\n'.join(text_file(root, p) for p in mains)
    evidence = []
    identity = bool(re.search(r'(?i)longdev|autopilot|\b[RV]\d{2}\b|(?:目标|产品目标|goal)(?:\*\*)?\s*[：:]', metadata))
    states = re.findall(r'(?im)^\s*(?:\*\*)?(?:状态(?:/日期)?|任务状态|执行状态|验收状态|status)(?:\*\*)?\s*[：:]\s*(?:\*\*)?([^\n]+)', metadata)
    owned = [p for p, rel in relative.items() if owned_relative(rel)] if identity and mains else []
    unknown = [p for p in entries if p not in owned]
    for path in safe(root, directory).rglob('*'):
        if path.is_dir() and not owned_relative(path.relative_to(root / directory).as_posix() + '/placeholder'):
            unknown.append(path.relative_to(root).as_posix())
    if not owned and not unknown:
        unknown.append(directory)
    name = PurePosixPath(directory).name
    result = {'source': directory, 'kind': kind, 'name': name, 'files': owned,
              'unknown_files': unknown, 'classification': 'retain', 'reasons': evidence}
    if not owned or name != name.strip() or name in {'.', '..', 'archive'}:
        evidence.append('No unambiguous task identity/name; preserve unknown content')
        return result
    evidence.append('Task index contains goal/longdev/R-V identity and recognized task structure')
    if not states:
        evidence.append('No reliable current status field')
        return result
    status = ' / '.join(s.strip() for s in states)
    result['declared_status'] = status
    if re.search(r'待执行|执行中|待检查|待最终检查|待报告|检查通过|待验收|待用户验收|受阻|暂停|预算停止|候选耗尽|in.progress|pending|blocked', status, re.I):
        result['classification'] = 'active'
        evidence.append('Explicit active/review/acceptance status: ' + status)
        return result
    terminal = re.search(r'已验收|已完成|目标达成|已取消|已终止|accepted|completed|cancelled', status, re.I)
    if not terminal:
        evidence.append('Status cannot prove active or closed: ' + status)
        return result
    documents = '\n'.join(text_file(root, p) for p in owned if '/baselines/' not in p)
    open_work = re.search(r'\[[ ]\]|(?:状态|status)\s*[：:]\s*(?:待|受阻)|\|\s*(?:待执行|执行中|待检查|待验收|受阻|未验证|失败)\s*\|', documents, re.I)
    closure = [directory + '/reviews/final.md', directory + '/gates/final.md']
    if open_work:
        evidence.append('Terminal label conflicts with unresolved checklist/status/requirement')
    elif not all(p in owned and re.search(r'(?im)^(?:(?:结论|result|status)\s*[：:]\s*)?(?:独立审查通过|整体检查通过|检查通过|通过|passed|review passed|gate passed)[。.!]?\s*$', text_file(root, p).replace('**', ''), re.I) for p in closure):
        evidence.append('Terminal label alone is insufficient; final review/gate evidence missing')
    elif any(re.search(r'阻塞|失败|未验证|未解决|未验收|待验收|未通过|不通过|not\s+(?:passed|accepted)|failed|failure|unresolved|unverified|pending|blocked', text_file(root, p), re.I) for p in closure):
        evidence.append('Final review/gate contains unresolved or unverified claims')
    else:
        result['classification'] = 'closed'
        evidence.append('Terminal status plus final review/gate and no open checklist/status')
    return result


def inventory(root):
    candidates, unknown, untouched = [], [], []
    roots = []
    for child in sorted(root.iterdir()):
        if child.name.strip() == '.claude':
            safe(root, child.name)
            if not child.is_dir():
                unknown.append(child.name)
                continue
            for kind in KINDS:
                branch = child.name + '/' + kind
                if safe(root, branch).exists():
                    roots.append((branch, kind))
            untouched.extend(p.relative_to(root).as_posix() for p in child.iterdir() if p.name not in KINDS)
        elif child.name == '.longdev':
            safe(root, child.name)
            if not child.is_dir():
                unknown.append(child.name)
            elif any((child / name).is_file() for name in MAIN):
                candidates.append(classify(root, child.name, 'longdev'))
            else:
                roots.append((child.name, 'longdev'))
        elif child.name == '.longdev-runtime':
            untouched.append(child.name)
    for branch, kind in roots:
        folder = safe(root, branch)
        if not folder.is_dir():
            unknown.append(branch)
            continue
        for child in sorted(folder.iterdir()):
            path = child.relative_to(root).as_posix()
            safe(root, path)
            if child.is_dir():
                if branch == '.longdev' and child.name in KINDS:
                    for nested in sorted(child.iterdir()):
                        relative = nested.relative_to(root).as_posix()
                        safe(root, relative)
                        if nested.is_dir():
                            candidates.append(classify(root, relative, child.name))
                        else:
                            unknown.append(relative)
                else:
                    candidates.append(classify(root, path, kind))
            else:
                unknown.append(path)
    return candidates, sorted(unknown), sorted(untouched)


def references(text):
    values = []
    values.extend(m[1].strip('<>') for m in re.finditer(r'\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)', text))
    values.extend(re.findall(r'`([^`\n]+)`', text))
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        parsed = None
    def strings(value):
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                strings(item)
    strings(parsed)
    values.extend(re.findall(r'(?:\.claude/(?:longdev|autopilot)|\.longdev|docs/(?:longdev|autopilot))/[^\s`"<>()[\]]+', text.replace('\\', '/')))
    return sorted(set(values))


def resolve_reference(root, source, value, known):
    value = unquote(value).replace('\\', '/').split('#', 1)[0].rstrip('/')
    if not value or re.match(r'^[a-z]+://|^mailto:', value, re.I):
        return None
    possibilities = [value, os.path.normpath(str(PurePosixPath(source).parent / value)).replace('\\', '/')]
    possibilities.extend(p for p in sorted(known, key=len, reverse=True) if value.endswith('/' + p))
    for path in possibilities:
        if path in known:
            return path
        if not PurePosixPath(path).is_absolute() and '..' not in PurePosixPath(path).parts and not re.match(r'^[A-Za-z]:', path):
            try:
                if safe(root, path).is_file():
                    return path
            except ValueError:
                raise
    return None


def raw_file(root, source):
    data = safe(root, source).read_bytes()
    try:
        data.decode('utf-8')
        binary = b'\0' in data
    except UnicodeDecodeError:
        binary = True
    return '/baselines/' in source or Path(source).suffix.lower() in RAW or binary


def previous_sources(root):
    previous = read_json(root, MARKER)
    if previous and previous.get('schema') != 2:
        raise ValueError('Unsupported convergence marker')
    old = read_json(root, LEGACY_MARKER)
    records = {}
    if old:
        if old.get('schema') != 1 or old.get('state') != 'complete':
            raise ValueError('Invalid v0.13 marker; inspect before convergence')
        for item in old['files']:
            records[item['source']] = {**item, 'origin': 'v013'}
    if previous:
        records.update(previous.get('sources', {}))
    return previous or {}, records


def tracked(root, paths, outputs=None):
    pending = []
    for path in sorted(set(paths)):
        file = safe(root, path)
        index = git(root, ['show', ':' + path])
        expected = (outputs or {}).get(path, file.read_bytes() if file.is_file() else None)
        if expected is None or index.returncode or digest(index.stdout) != digest(expected):
            pending.append(path)
    return pending


def build_plan(root):
    candidates, unknown, untouched = inventory(root)
    previous, prior = previous_sources(root)
    prior_tasks = {t['source']: t for t in previous.get('tasks', [])}
    # 归档中断可能已移走 PLAN/gate；已登记且指纹未变的余项仍属于同一任务。
    for task in candidates:
        original_task = prior_tasks.get(task['source'])
        if original_task and task['classification'] == 'retain':
            remaining = [p for p in files(root, task['source']) if p in prior]
            if remaining and all(digest(safe(root, p).read_bytes()) == prior[p]['source_sha256'] for p in remaining):
                task.update({k: original_task[k] for k in ('classification', 'reasons')})
                task['files'] = remaining
                task['unknown_files'] = [p for p in files(root, task['source']) if p not in remaining]
    known = {p for task in candidates for p in task['files']}
    known.update(task['source'] for task in candidates)
    durable = [p for kind in KINDS for p in files(root, 'docs/' + kind)]
    blocked = ignored(root, [MARKER, 'docs/autopilot/.longdev-portability-probe', *durable])
    if blocked:
        raise ValueError('Persistent destinations ignored: ' + json.dumps(blocked, ensure_ascii=False))
    owner = {p: task['source'] for task in candidates for p in [task['source'], *task['files']]}
    edges = {task['source']: set() for task in candidates}
    referenced_files, external_refs, missing = set(), set(), {}
    external_mapping = {}
    for task in candidates:
        for source in task['files']:
            if '/baselines/' in source:
                continue
            source_text = text_file(root, source)
            explicit_links = {m[1].strip('<>') for m in re.finditer(r'\]\((<[^>\n]+>|[^\s)]+)(?:\s+"[^"\n]*")?\)', source_text)}
            for ref in references(source_text):
                resolved = resolve_reference(root, source, ref, known)
                if resolved:
                    referenced_files.add(resolved)
                    if resolved in owner:
                        edges[task['source']].add(owner[resolved])
                    else:
                        external_mapping[resolved] = resolved
                        if '/.work/' in ('/' + resolved) or resolved.startswith('.work/') or resolved not in known:
                            missing.setdefault(task['source'], []).append('external:' + resolved)
                elif ((ref in explicit_links and not re.match(r'^[a-z]+://|^mailto:|^#', ref, re.I))
                      or re.match(r'^(?:\s*\.claude/|\.longdev/|\.work/|work/|evidence/|baselines/)', ref.replace('\\', '/'))):
                    missing.setdefault(task['source'], []).append(ref)
    # 新权威任务也参与引用闭包；历史 archive 不充当活动根。
    external_seeds = set()
    for source in durable:
        if '/archive/' in source or source == MARKER or source == LEGACY_MARKER:
            continue
        for ref in references(text_file(root, source)):
            resolved = resolve_reference(root, source, ref, known)
            if resolved in owner:
                external_seeds.add(owner[resolved])
                referenced_files.add(resolved)
                external_refs.add(source)
    # 先完成不确定项分类，再计算保护闭包；不让后来保留的任务失去依赖。
    for task in candidates:
        unsupported = [p for p in task['files'] if Path(p).suffix.lower() not in {'.md', '.txt', '.json'}
                       and not raw_file(root, p) and re.search(r'\.claude|\.longdev', text_file(root, p))]
        local_required = [p for p in task['files'] if p in referenced_files and ('/baselines/' in p or prior.get(p, {}).get('target', '').startswith('.work/'))]
        if task['source'] in missing or unsupported or local_required:
            task['classification'] = 'retain'
            task['reasons'].append('Unresolved references/required local evidence/unsupported format: ' + repr(missing.get(task['source'], []) + unsupported + local_required))
    unsafe = {t['source'] for t in candidates if t['classification'] in {'retain', 'conflict'}}
    changed = True
    while changed:
        changed = False
        for task in candidates:
            if task['source'] not in unsafe and edges[task['source']] & unsafe:
                task['classification'] = 'retain'
                task['reasons'].append('Referenced task is unresolved; preserve dependency chain')
                unsafe.add(task['source'])
                changed = True
    protected = {task['source'] for task in candidates if task['classification'] != 'closed'} | external_seeds
    frontier = list(protected)
    while frontier:
        node = frontier.pop()
        for dependency in edges.get(node, set()):
            if dependency not in protected:
                protected.add(dependency)
                frontier.append(dependency)
    mapping = dict(external_mapping)
    prior_roots = {str(PurePosixPath(source).parent) for source in prior if PurePosixPath(source).name in MAIN}
    for task in candidates:
        if task['classification'] == 'closed' and task['source'] in protected:
            task['classification'] = 'referenced_closed'
            task['reasons'].append('Referenced by active/uncertain task or new docs task (transitive closure)')
        if task['source'] in missing:
            task['classification'] = 'retain'
            task['reasons'].append('Unresolved evidence/dependency references: ' + repr(missing[task['source']]))
        if task['source'] in prior_roots and any(p not in prior or digest(safe(root, p).read_bytes()) != prior[p]['source_sha256'] for p in task['files']):
            task['classification'] = 'conflict'
            task['reasons'].append('Legacy source changed/new after recorded migration; preserve docs authority')
        prefix = 'docs/' + task['kind'] + ('/archive/' if task['classification'] == 'closed' else '/') + task['name']
        task['target'] = prefix
        if task['classification'] in {'retain', 'conflict'}:
            continue
        mapping[task['source']] = prefix
        for source in task['files']:
            relative = PurePosixPath(source).relative_to(task['source']).as_posix()
            if source in prior and safe(root, prior[source]['target']).is_file():
                target = prior[source]['target']
            elif raw_file(root, source):
                if source in referenced_files and '/baselines/' not in source:
                    target = prefix + '/evidence/portable/' + relative
                else:
                    target = '.work/' + task['kind'] + '/' + task['name'] + '/' + relative
            else:
                target = prefix + '/' + relative
            mapping[source] = target
        # 原始基线不能被当作可公开版本化的必需证据；保留待提供摘要。
        required_local = [p for p in task['files'] if p in referenced_files and mapping.get(p, '').startswith('.work/')]
        unsupported = [p for p in task['files'] if Path(p).suffix.lower() not in {'.md', '.txt', '.json'}
                       and not raw_file(root, p) and re.search(r'\.claude|\.longdev', text_file(root, p))]
        if required_local or unsupported:
            task['classification'] = 'retain'
            task['reasons'].append('Required evidence has no portable replacement or unsupported reference format: ' + repr(required_local + unsupported))
            for source in task['files']:
                mapping.pop(source, None)
    actions, outputs, conflicting_targets = [], {}, set()
    hashes = source_hash(root, [p for task in candidates for p in task['files']])
    for task in candidates:
        for source in task['files']:
            action = {'source': source, 'task': task['source'], 'classification': task['classification'],
                      'source_sha256': hashes[source], 'reasons': task['reasons']}
            if task['classification'] in {'retain', 'conflict'}:
                actions.append({**action, 'action': task['classification'], 'target': None})
                continue
            target = mapping[source]
            original = safe(root, source).read_bytes()
            archive = '.work/longdev-migration/archive/' + digest(source.encode())[:16] + '/' + hashes[source] + '/' + PurePosixPath(source).name
            existing = prior.get(source)
            # 已迁移的新记录正常演进不应被旧保护副本覆盖。
            if existing and safe(root, target).is_file():
                content = safe(root, target).read_bytes()
                operation = 'deduplicate'
            else:
                content = original if raw_file(root, source) else rewrite(original, source, target, mapping)
                current = safe(root, target)
                if current.exists() and (not current.is_file() or current.read_bytes() != content):
                    actions.append({**action, 'action': 'conflict', 'target': target, 'reason': 'Different destination content preserved'})
                    continue
                if target in outputs and outputs[target] != content:
                    conflicting_targets.add(target)
                    actions.append({**action, 'action': 'conflict', 'target': target, 'reason': 'Different candidates claim the same target'})
                    continue
                operation = 'deduplicate' if current.exists() or target in outputs else ('archive_history' if task['classification'] == 'closed' else 'migrate')
            outputs[target] = content
            backups = []
            if raw_file(root, source) and target.startswith('docs/'):
                relative = PurePosixPath(source).relative_to(task['source']).as_posix()
                local = '.work/' + task['kind'] + '/' + task['name'] + '/' + relative
                if safe(root, local).exists() and (not safe(root, local).is_file() or safe(root, local).read_bytes() != original):
                    actions.append({**action, 'action': 'conflict', 'target': target,
                                    'local_copies': [local], 'reason': 'Different local evidence copy preserved'})
                    continue
                outputs[local] = original
                backups.append(local)
            if safe(root, archive).exists() and safe(root, archive).read_bytes() != original:
                actions.append({**action, 'action': 'conflict', 'target': target, 'reason': 'Archive conflict; source preserved'})
                continue
            actions.append({**action, 'action': operation, 'target': target, 'sha256': digest(content),
                            'archive': archive, 'local_copies': backups,
                            'archive_after': 'all task outputs and inventory tracked with index blobs matching working content'})
    # 同一个任务有冲突时不形成半套可被误续接的记录。
    for action in actions:
        if action['target'] in conflicting_targets:
            action['action'] = 'conflict'
            action['reason'] = 'Multiple different candidates claim the same destination; all preserved'
    blocked_tasks = {t['source'] for t in candidates if t['classification'] in {'conflict', 'retain'}}
    blocked_tasks.update(a['task'] for a in actions if a['action'] in {'conflict', 'retain'})
    changed = True
    while changed:
        changed = False
        for node, dependencies in edges.items():
            if node in blocked_tasks or dependencies & blocked_tasks:
                before = len(blocked_tasks)
                blocked_tasks.update({node, *dependencies})
                changed |= len(blocked_tasks) != before
    for action in actions:
        if action['task'] in blocked_tasks and action['action'] not in {'conflict', 'retain'}:
            action['action'] = 'retain'
            action['reason'] = 'Another file in this task is unresolved/conflicting'
    for task in candidates:
        if task['source'] in blocked_tasks and task['classification'] not in {'retain', 'conflict'}:
            task['classification'] = 'retain'
            task['reasons'].append('Preserve dependency component containing a retained/conflicting source')
    allowed_targets = {p for a in actions if a['action'] not in {'conflict', 'retain'} for p in [a['target'], *a.get('local_copies', [])]}
    outputs = {p: data for p, data in outputs.items() if p in allowed_targets}
    valid_mapping = {old: new for old, new in mapping.items() if new in allowed_targets or old in external_mapping
                     or old in edges and old not in blocked_tasks}
    reference_updates = {}
    for source in sorted(external_refs):
        original = safe(root, source).read_bytes()
        updated = rewrite(original, source, source, valid_mapping)
        if updated != original:
            outputs[source] = updated
            reference_updates[source] = digest(original)
    blocked = ignored(root, [MARKER, *[p for p in outputs if p.startswith('docs/')]])
    if blocked:
        raise ValueError('Migration outputs ignored: ' + json.dumps(blocked, ensure_ascii=False))
    needed = [MARKER, *[p for p in outputs if p.startswith('docs/')]]
    tracking = tracked(root, needed, outputs) if actions else []
    for action in actions:
        if action['action'] not in {'conflict', 'retain'}:
            action['tracking_pending'] = tracking
            action['old_entry_action'] = 'retain_until_tracked' if tracking else 'archive_verified_source'
    summary = {'tasks': len(candidates), 'files': len(actions), 'unknown_files': len(unknown) + sum(len(t['unknown_files']) for t in candidates),
               'conflicts': sum(a['action'] == 'conflict' for a in actions), 'retained': sum(a['action'] == 'retain' for a in actions)}
    report = {'schema': 2, 'tasks': candidates, 'actions': actions, 'unknown': unknown, 'untouched_client_assets': untouched,
              'external_references': sorted(external_refs), 'tracking_pending': tracking, 'summary': summary,
              'reference_updates': reference_updates,
              'sources': dict(prior), 'authority': ['docs/longdev', 'docs/autopilot'],
              'limitations': 'Classification does not confer acceptance. Unknown content and unresolved references remain in place.'}
    return report, outputs, hashes


def report_status(report, changed=False):
    if report['summary']['conflicts'] or report['summary']['retained'] or report['summary']['unknown_files']:
        return 'needs_review'
    if report['tracking_pending']:
        return 'awaiting_tracking'
    return 'converged' if changed or report['actions'] else 'no_legacy_records'


def converge(project, check=False, dry_run=False):
    root = Path(project).absolute()
    if not root.is_dir() or any(redirected(p) for p in [root, *root.parents]):
        raise ValueError('Workspace must be an existing real directory')
    report, outputs, hashes = build_plan(root)
    report['status'] = report_status(report)
    if check or dry_run:
        report['mode'] = 'dry_run' if dry_run else 'check'
        return report
    if not report['tasks'] and not report['unknown']:
        return report
    with migration_lock(root):
        # 锁内重新盘点，禁止用预演结果直接写入变化后的现场。
        report, outputs, hashes = build_plan(root)
        pending_journal = read_json(root, JOURNAL)
        if pending_journal and pending_journal.get('state') == 'applying':
            for source, previous_hash in pending_journal['source_hashes'].items():
                current = safe(root, source)
                if current.exists() and digest(current.read_bytes()) != previous_hash:
                    raise ValueError('Source changed during interrupted convergence: ' + source)
            if set(hashes) - set(pending_journal['source_hashes']):
                raise ValueError('Source file set changed during interrupted convergence')
        else:
            marker_index = git(root, ['show', ':' + MARKER])
            pending_journal = {'state': 'applying', 'source_hashes': hashes,
                               'tracked_marker': digest(marker_index.stdout) if not marker_index.returncode and not report['tracking_pending'] else None}
        atomic_write(root, JOURNAL, json.dumps(pending_journal, indent=2).encode())
        for target, data in outputs.items():
            current = safe(root, target)
            if current.exists():
                if current.read_bytes() != data:
                    if digest(current.read_bytes()) != report['reference_updates'].get(target):
                        raise ValueError('Output changed after inventory: ' + target)
                    atomic_write(root, target, data)
            else:
                atomic_write(root, target, data)
            if current.read_bytes() != data:
                raise ValueError('Output verification failed: ' + target)
        for source, expected in hashes.items():
            if not safe(root, source).is_file() or digest(safe(root, source).read_bytes()) != expected:
                raise ValueError('Source changed after inventory: ' + source)
        marker_index = git(root, ['show', ':' + MARKER])
        receipt_valid = (pending_journal.get('tracked_marker') is not None and not marker_index.returncode
                         and digest(marker_index.stdout) == pending_journal['tracked_marker'])
        may_archive = not report['tracking_pending'] or (receipt_valid and not tracked(root, [p for p in outputs if p.startswith('docs/')], outputs))
        archived_sources = []
        for action in report['actions']:
            if action['action'] in {'retain', 'conflict'}:
                continue
            source = action['source']
            report['sources'][source] = {key: action[key] for key in ('source', 'source_sha256', 'target', 'sha256', 'archive')}
            report['sources'][source]['state'] = 'awaiting_tracking'
            if may_archive:
                original = safe(root, source).read_bytes()
                backup = safe(root, action['archive'])
                if not backup.exists():
                    atomic_write(root, action['archive'], original)
                if backup.read_bytes() != original or digest(original) != action['source_sha256']:
                    raise ValueError('Archive verification failed: ' + source)
                # 先持久写下已校验保护副本的对应关系，删除中断后仍可重入。
                report['sources'][source]['state'] = 'archive_verified'
                atomic_write(root, MARKER, json.dumps(report, ensure_ascii=False, indent=2).encode())
                safe(root, source).unlink()
                archived_sources.append(source)
                report['sources'][source]['state'] = 'archived'
                action['old_entry_action'] = 'archived'
        # 仅收掉本次确认任务的空目录，不触碰未知文件或客户端根。
        for source in archived_sources:
            task_root = next(t['source'] for t in report['tasks'] if source.startswith(t['source'] + '/'))
            path = safe(root, source).parent
            boundary = safe(root, task_root)
            while path == boundary or boundary in path.parents:
                if path.exists() and path.is_dir() and not any(path.iterdir()):
                    path.rmdir()
                else:
                    break
                path = path.parent
        report['status'] = report_status(report, changed=True)
        encoded = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
        marker = safe(root, MARKER)
        if not marker.exists() or marker.read_bytes() != encoded:
            atomic_write(root, MARKER, encoded)
        atomic_write(root, JOURNAL, json.dumps({'state': 'complete', 'source_hashes': hashes}, indent=2).encode())
    return report
