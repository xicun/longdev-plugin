"""Resolve one canonical task directory and validate a role's concrete write path."""
import argparse
import json
import os
from pathlib import Path
import stat


def clean_absolute(value):
    path = Path(value)
    if not path.is_absolute() or str(path) != str(value):
        raise ValueError('An explicit normalized absolute path is required: ' + str(value))
    if any(part != part.strip() or part in {'.', '..'} for part in path.parts):
        raise ValueError('Whitespace or traversal path component refused: ' + str(value))
    for ancestor in [path, *path.parents]:
        try:
            info = ancestor.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Redirected path refused: ' + str(ancestor))
    return path


def resolve(project, kind, name):
    root = clean_absolute(project)
    if not root.is_dir() or kind not in {'longdev', 'autopilot'}:
        raise ValueError('Existing project and known task kind required')
    if not name or name != name.strip() or name in {'.', '..', 'archive'} or '/' in name or '\\' in name:
        raise ValueError('One task name without whitespace padding or separators required')
    return clean_absolute(str(root / 'docs' / kind / name))


def check(project, task, target):
    root, task_dir, output = map(clean_absolute, (project, task, target))
    try:
        relative = task_dir.relative_to(root)
    except ValueError as error:
        raise ValueError('Task is outside project') from error
    if len(relative.parts) != 3 or relative.parts[0] != 'docs' or relative.parts[1] not in {'longdev', 'autopilot'}:
        raise ValueError('TASK_DIR must be project/docs/{longdev,autopilot}/<name>')
    expected = resolve(str(root), relative.parts[1], relative.parts[2])
    if task_dir != expected:
        raise ValueError('Task directory differs from canonical TASK_DIR')
    local = root / '.work' / relative.parts[1] / relative.parts[2]
    if not (output == task_dir or task_dir in output.parents or output == local or local in output.parents):
        raise ValueError('Write target is outside TASK_DIR and its task-local .work directory')
    return {'status': 'allowed', 'task_dir': str(task_dir), 'target': str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    resolver = sub.add_parser('resolve')
    resolver.add_argument('--project', required=True)
    resolver.add_argument('--kind', choices=['longdev', 'autopilot'], default='longdev')
    resolver.add_argument('--name', required=True)
    guard = sub.add_parser('check')
    guard.add_argument('--project', required=True)
    guard.add_argument('--task', required=True)
    guard.add_argument('--target', required=True)
    args = parser.parse_args()
    try:
        result = ({'status': 'resolved', 'task_dir': str(resolve(args.project, args.kind, args.name))}
                  if args.command == 'resolve' else check(args.project, args.task, args.target))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({'status': 'blocked', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
