"""Shared bounded filesystem, Git and reference helpers for workspace migration."""
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

RAW = {'.pdf', '.gif', '.png', '.mp3', '.zip', '.log', '.jpg', '.mp4', '.patch', '.svg', '.diff', '.webp', '.wav', '.bmp', '.jpeg'}


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
        value = value.rstrip('/')
        candidates = [value, os.path.normpath(str(PurePosixPath(source).parent / value)).replace('\\', '/')]
        for old in sorted(mapping, key=len, reverse=True):
            if value.endswith('/' + old):
                prefix = value[:-len(old)]
                if ((prefix.startswith('/') or re.match(r'^[A-Za-z]:/', prefix))
                        and not re.search(r'["\x27]|\s(?:/|[A-Za-z]:/)', prefix)):
                    candidates.append(old)
        matched = next((candidate for candidate in candidates if candidate in mapping), None)
        if matched is None:
            return original
        new = mapping[matched]
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
                       r'(?:\.claude[/\\](?:longdev|autopilot)|\.longdev)[/\\][^\s`"<>()[\]]*')

    def inline(value):
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
