"""Shared project installer; Python 3.9+, no third-party dependencies."""
import argparse
import hashlib
import json
import os
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
ROOTS = {'codex': '.agents/skills', 'dsh': '.dsh/skills', 'claude': '.claude/skills'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.longdev-new')
    with tmp.open('xb') as stream:
        stream.write(data)
    os.replace(tmp, path)


def install(project, client, source=SOURCE, check=False):
    project = Path(project).resolve()
    files = {p.relative_to(source).as_posix(): p.read_bytes()
             for folder in ('skills', 'agents', '.claude-plugin', '.codex-plugin')
             for p in sorted((source / folder).rglob('*')) if p.is_file()}
    for required in ('agents/longdev-reviewer.md', 'skills/autopilot/SKILL.md',
                     'skills/longdev/SKILL.md', '.claude-plugin/plugin.json', '.codex-plugin/plugin.json'):
        if required not in files:
            raise ValueError('Missing dependency: ' + required)
    if json.loads(files['.claude-plugin/plugin.json'])['version'] != json.loads(files['.codex-plugin/plugin.json'])['version']:
        raise ValueError('Version mismatch')
    hashes = {k: sha(v) for k, v in files.items()}
    identity = sha(json.dumps(hashes, sort_keys=True).encode())[:20]
    bundle = project / '.longdev-runtime' / identity
    receipt = project / '.longdev-runtime' / (client + '.json')
    old = json.loads(receipt.read_text('utf-8')) if receipt.exists() else {}
    entries = {}
    for name in ('longdev', 'autopilot'):
        header = files[f'skills/{name}/SKILL.md'].decode('utf-8').split('---', 2)[1]
        text = ('---' + header + '---\n\n<!-- longdev managed entry -->\n'
                f'客户端：{client}。先读完整技能：\n\n'
                f'[{name}]({(bundle / "skills" / name / "SKILL.md").as_posix()})\n\n'
                f'插件根目录：`{bundle.as_posix()}`。相对引用以完整技能所在目录为准。'
                '角色定义在插件根目录 agents/；任务记录仍在项目 .claude/longdev/。'
                '无独立审查能力时保持待检查，不以同一会话换角色代替。\n')
        entries[f'{ROOTS[client]}/{name}/SKILL.md'] = text.encode('utf-8')
    targets = {bundle / k: v for k, v in files.items()}
    targets.update({project / k: v for k, v in entries.items()})
    # 写入前核对全部冲突；既有未知内容和手工编辑都保留。
    for path, data in targets.items():
        if path.is_symlink() or any(p.is_symlink() for p in path.parents):
            raise ValueError('Symlink destination: ' + str(path))
        if path.exists() and path.read_bytes() != data:
            expected = old.get('entries', {}).get(path.relative_to(project).as_posix())
            if expected != sha(path.read_bytes()):
                raise ValueError('Existing or modified file preserved: ' + str(path))
        if check and (not path.exists() or path.read_bytes() != data):
            raise ValueError('Installation mismatch: ' + str(path))
    if check:
        if old.get('bundle') != identity:
            raise ValueError('Receipt mismatch')
    else:
        for path, data in targets.items():
            if not path.exists() or path.read_bytes() != data:
                write(path, data)
        write(receipt, json.dumps({'bundle': identity, 'files': hashes,
              'entries': {k: sha(v) for k, v in entries.items()}}, indent=2).encode())
    return {'client': client, 'bundle': str(bundle), 'files': len(files),
            'status': 'checked' if check else 'installed', 'model_execution': 'not_tested'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client', choices=[*ROOTS, 'all'], required=True)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    for client in ROOTS if args.client == 'all' else [args.client]:
        print(json.dumps(install(args.project, client, check=args.check), ensure_ascii=False))
