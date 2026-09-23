"""Migrate only the selected workspace's legacy longdev records (Python 3.9+)."""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import stat
import subprocess
import tempfile

VERSION = 1
MARKER = 'docs/longdev/.migration-v013.json'
JOURNAL = '.work/longdev-migration/journal.json'
KINDS = ('longdev', 'autopilot')
TEXT = {'.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.csv'}
RAW = {'.log', '.patch', '.diff', '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.svg', '.pdf', '.zip', '.mp4', '.mp3', '.wav'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def redirected(path):
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), 'st_file_attributes', 0)
    except FileNotFoundError:
        return False
    return bool(attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def safe(root, relative):
    part = PurePosixPath(relative)
    if not relative or part.is_absolute() or PureWindowsPath(relative).drive or '..' in part.parts or '\\' in relative:
        raise ValueError('Unsafe path: ' + relative)
    path = root.joinpath(*part.parts)
    for ancestor in [path, *path.parents]:
        if redirected(ancestor):
            raise ValueError('Symlink path refused: ' + str(ancestor))
        if ancestor == root:
            break
    return path


def files(root, relative):
    folder = safe(root, relative)
    if not folder.exists():
        return []
    if not folder.is_dir():
        raise ValueError('Directory expected: ' + relative)
    result = []
    for path in sorted(folder.rglob('*')):
        rel = path.relative_to(root).as_posix()
        safe(root, rel)
        if path.is_file():
            result.append(rel)
        elif not path.is_dir():
            raise ValueError('Special file refused: ' + rel)
    return result


def git(root, args):
    return subprocess.run(['git', '-C', str(root), *args], capture_output=True, timeout=20)


def ignored(root, paths):
    probe = git(root, ['rev-parse', '--show-toplevel'])
    if probe.returncode:
        return None
    found = []
    for relative in sorted(set(paths)):
        result = git(root, ['check-ignore', '--no-index', '-v', '--', relative])
        if result.returncode == 0:
            # check-ignore -v also reports a matching negative pattern.
            rule = result.stdout.decode('utf-8', 'replace').split('\t', 1)[0]
            if not rule.rsplit(':', 1)[-1].startswith('!'):
                found.append({'path': relative, 'rule': rule})
        elif result.returncode != 1:
            raise ValueError(result.stderr.decode('utf-8', 'replace'))
    return found


def destination(source, data=b''):
    parts = PurePosixPath(source).parts
    kind, tail = parts[1], parts[2:]
    # 原始备份与日志不进入版本库；结构化 manifest 和报告保持可携带。
    try:
        data.decode('utf-8')
        binary = b'\x00' in data
    except UnicodeDecodeError:
        binary = True
    local = 'baselines' in tail or (Path(source).suffix.lower() in RAW) or binary
    return '/'.join(('.work' if local else 'docs', kind, *tail))


def rewrite(data, source, target, mapping):
    extension = Path(source).suffix.lower()
    if '/baselines/' in source or extension not in {'.md', '.txt', '.json'}:
        return data
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return data
    def resolve(value, link=False):
        original = value
        value = value.replace('\\\\', '/').replace('\\', '/')
        suffix = ''
        if '#' in value:
            value, fragment = value.split('#', 1)
            suffix = '#' + fragment
        legacy = re.search(r'\.claude/(longdev|autopilot)(?:/|$)', value)
        if legacy:
            prefix = value[:legacy.start()]
            if prefix and not (prefix.startswith('/') or re.match(r'^[A-Za-z]:/', prefix)
                               or re.fullmatch(r'(?:\.?\./)*', prefix)):
                return original
            if prefix and (not prefix.endswith('/') or re.search(r'["\x27]|\s(?:/|[A-Za-z]:/)', prefix)):
                return original
            old = value[legacy.start():]
        else:
            old = os.path.normpath(str(PurePosixPath(source).parent / value)).replace('\\', '/')
        if old in mapping:
            new = mapping[old]
        elif legacy:
            new = old.replace('.claude/', 'docs/', 1)
        else:
            return original
        if link:
            new = os.path.relpath(new, str(PurePosixPath(target).parent)).replace('\\', '/')
        return new + suffix

    if extension == '.json':
        # 先解析格式，避免正则把 JSON 的内嵌引号/反斜线转义破坏。
        def values(value):
            if isinstance(value, str):
                exact = resolve(value)
                if exact != value:
                    return exact
                return rewrite(value.encode('utf-8'), source + '.txt', target, mapping).decode('utf-8')
            if isinstance(value, list):
                return [values(item) for item in value]
            if isinstance(value, dict):
                return {key: values(item) for key, item in value.items()}
            return value
        return (json.dumps(values(json.loads(text)), ensure_ascii=False, indent=2) + '\n').encode('utf-8')

    # 只改路径 token，不把带路径的整条命令当成路径而丢掉命令前缀。
    token = re.compile(r'(?:[A-Za-z]:[/\\][^\s`"<>()[\]]*?|/[^\s`"<>()[\]]*?|(?:\.?\.[/\\])*)?'
                       r'\.claude[/\\](?:longdev|autopilot)[/\\][^\s`"<>()[\]]*')

    def inline(value):
        if not re.search(r'\s', value):
            changed = resolve(value)
            if changed != value:
                return changed
        return token.sub(lambda m: resolve(m[0]), value)

    # 先保护 Markdown 链接，避免随后把已重算的相对链接再改成项目相对路径。
    links = []

    def link(match):
        path = match[2]
        angle = path.startswith('<')
        path = resolve(path[1:-1] if angle else path, True)
        links.append(match[1] + ('<' + path + '>' if angle else path) + (match[3] or '') + match[4])
        return '\x00LONGDEV_LINK_' + str(len(links) - 1) + '\x00'

    text = re.sub(r'(\]\()(<[^>\n]+>|[^\s)]+)(\s+(?:"[^"\n]*"|\x27[^\x27\n]*\x27))?(\))', link, text)
    text = re.sub(r'`([^`\n]+)`', lambda m: '`' + inline(m[1]) + '`', text)
    text = re.sub(r'"([^"\n]+)"', lambda m: '"' + inline(m[1]) + '"', text)
    text = token.sub(lambda m: resolve(m[0]), text)
    text = re.sub(r'\x00LONGDEV_LINK_(\d+)\x00', lambda m: links[int(m[1])], text)
    return text.encode('utf-8')


def external_references(root):
    result = git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard'])
    if result.returncode:
        candidates = [p.name for p in root.glob('*.md')]
    else:
        candidates = result.stdout.decode('utf-8').split('\0')
    hits = []
    for relative in sorted(set(candidates)):
        if not relative or relative.startswith(('.claude/', '.work/', '.longdev-runtime/', 'docs/longdev/', 'docs/autopilot/')):
            continue
        if Path(relative).suffix.lower() not in {'.md', '.json'}:
            continue
        path = safe(root, relative)
        if path.is_file():
            text = path.read_text('utf-8', errors='replace').replace('\\', '/')
            if re.search(r'\.claude/+(longdev|autopilot)', text):
                hits.append(relative)
    return hits


def prepare(root):
    sources = [p for kind in KINDS for p in files(root, '.claude/' + kind)]
    if not sources:
        return None
    mapping = {p: destination(p, safe(root, p).read_bytes()) for p in sources}
    operations = []
    local = []
    for source, target in mapping.items():
        data = safe(root, source).read_bytes()
        content = rewrite(data, source, target, mapping)
        operations.append({'source': source, 'source_sha256': digest(data), 'target': target,
                           'sha256': digest(content), 'data': base64.b64encode(content).decode('ascii')})
        if target.startswith('.work/'):
            local.append({'path': target, 'sha256': digest(content), 'bytes': len(content)})
    report = {
        'schema': VERSION, 'state': 'complete', 'authority': ['docs/' + k for k in KINDS],
        'legacy_policy': 'Legacy directories are read-only backups; never import them again after this marker.',
        'files': [{k: v for k, v in item.items() if k != 'data'} for item in operations],
        'local_evidence': local, 'external_references': external_references(root),
        'manual_review': [target for source, target in mapping.items()
                          if Path(source).suffix.lower() not in {'.md', '.txt', '.json'}
                          and target.startswith('docs/')
                          and b'.claude' in safe(root, source).read_bytes()],
        'evidence_limit': 'Historical statuses are preserved, not revalidated. Missing local evidence requires targeted revalidation; migration is not task acceptance.',
    }
    return {'schema': VERSION, 'operations': operations, 'report': report}


def preflight(root, journal):
    if journal.get('schema') != VERSION:
        raise ValueError('Unsupported migration journal schema')
    current_sources = {p for kind in KINDS for p in files(root, '.claude/' + kind)}
    if current_sources != {item['source'] for item in journal['operations']}:
        raise ValueError('Legacy source file set changed during migration; preserve journal and reconcile')
    for item in journal['operations']:
        source, target = safe(root, item['source']), safe(root, item['target'])
        content = base64.b64decode(item['data'], validate=True)
        if digest(content) != item['sha256']:
            raise ValueError('Corrupt journal content: ' + item['target'])
        if not source.is_file() or digest(source.read_bytes()) != item['source_sha256']:
            raise ValueError('Legacy source changed during migration: ' + item['source'])
        if target.exists() and (not target.is_file() or target.read_bytes() != content):
            raise ValueError('Destination conflict; preserved: ' + item['target'])
    durable = [item['target'] for item in journal['operations'] if item['target'].startswith('docs/')]
    blocked = ignored(root, [MARKER, *durable])
    if blocked:
        raise ValueError('Persistent records ignored; fix project rules narrowly and retry: ' + json.dumps(blocked, ensure_ascii=False))
    return blocked is not None


def atomic_write(root, relative, data):
    target = safe(root, relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    scratch = safe(root, '.work/longdev-migration')
    scratch.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='write-', dir=scratch)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def migration_lock(root):
    path = safe(root, '.work/longdev-migration/lock')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as stream:
        try:
            if os.name == 'nt':
                import msvcrt
                stream.seek(0)
                if not stream.read(1):
                    stream.write(b'0')
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise ValueError('Another migration holds the workspace lock') from error
        try:
            yield
        finally:
            if os.name == 'nt':
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def completed(root):
    marker = safe(root, MARKER)
    if not marker.exists():
        return None
    report = json.loads(marker.read_text('utf-8'))
    if report.get('schema') != VERSION or report.get('state') != 'complete':
        raise ValueError('Invalid completion marker; preserve and inspect: ' + MARKER)
    current = [p for kind in KINDS for p in files(root, 'docs/' + kind)]
    blocked = ignored(root, [MARKER, *current])
    if blocked:
        raise ValueError('Persistent records ignored after migration: ' + json.dumps(blocked, ensure_ascii=False))
    return {'status': 'already_migrated', 'marker': MARKER, 'git': blocked is not None,
            'external_references': report.get('external_references', []),
            'manual_review': report.get('manual_review', []),
            'local_evidence': report.get('local_evidence', []), 'authority': report['authority']}


def migrate(project, check=False):
    root = Path(project).absolute()
    if not root.is_dir() or any(redirected(p) for p in [root, *root.parents]):
        raise ValueError('Workspace must be an existing real directory')
    result = completed(root)
    if result:
        return result
    journal_path = safe(root, JOURNAL)
    journal = json.loads(journal_path.read_text('utf-8')) if journal_path.exists() else prepare(root)
    if journal is None:
        current = [p for kind in KINDS for p in files(root, 'docs/' + kind)]
        blocked = ignored(root, [MARKER, 'docs/autopilot/.longdev-portability-probe', *current])
        if blocked:
            raise ValueError('Persistent record destinations ignored: ' + json.dumps(blocked, ensure_ascii=False))
        return {'status': 'no_legacy_records', 'git': blocked is not None}
    is_git = preflight(root, journal)
    if check:
        return {'status': 'migration_pending', 'files': len(journal['operations']),
                'git': is_git, 'external_references': journal['report']['external_references'],
                'manual_review': journal['report']['manual_review']}
    with migration_lock(root):
        result = completed(root)
        if result:
            return result
        # 锁内重新读现场；中断时旧数据和 journal 保留，已写目标须完全相同。
        journal = json.loads(journal_path.read_text('utf-8')) if journal_path.exists() else prepare(root)
        preflight(root, journal)
        atomic_write(root, JOURNAL, json.dumps(journal, ensure_ascii=False, indent=2).encode('utf-8'))
        for item in journal['operations']:
            if not safe(root, item['target']).exists():
                atomic_write(root, item['target'], base64.b64decode(item['data']))
        preflight(root, journal)
        for item in journal['operations']:
            if not safe(root, item['target']).is_file():
                raise ValueError('Missing migrated target: ' + item['target'])
        atomic_write(root, MARKER, json.dumps(journal['report'], ensure_ascii=False, indent=2).encode('utf-8'))
    return {'status': 'migrated', 'marker': MARKER, 'files': len(journal['operations']),
            'git': is_git, 'external_references': journal['report']['external_references'],
            'manual_review': journal['report']['manual_review'],
            'local_evidence': journal['report']['local_evidence']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--check', action='store_true', help='Read-only probe; never create files')
    args = parser.parse_args()
    try:
        result = migrate(args.project, args.check)
        print(json.dumps(result, ensure_ascii=False))
        if args.check and result['status'] == 'migration_pending':
            return 1
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'blocked', 'error': str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
