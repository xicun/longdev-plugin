#!/usr/bin/env python3
"""Cross-worktree write lease for longdev shared mutable state.

longdev's single source of truth (docs/longdev/, docs/bugs/, testcases/) are
tracked working-tree files. Git worktrees each have their own working tree but
share one object database, so a per-worktree lock (e.g. under .work/) would NOT
serialize writers. This lease places the lock under the Git **common dir**, which
every worktree of the repo shares, so concurrent writers across worktrees
serialize instead of silently overwriting / swallowing conflicts. stdlib only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

STALE_SECONDS = 1800


def git_common_dir(root: Path) -> Path:
    probe = subprocess.run(['git', '-C', str(root), 'rev-parse', '--git-common-dir'],
                           capture_output=True, text=True, timeout=15)
    if probe.returncode == 0 and probe.stdout.strip():
        path = Path(probe.stdout.strip())
        return path if path.is_absolute() else (root / path).resolve()
    # Not a git repo: worktrees are not a concern; keep a local lease dir.
    local = root / '.work' / 'longdev-lease'
    local.mkdir(parents=True, exist_ok=True)
    return local


def lease_dir(root: Path) -> Path:
    directory = git_common_dir(root) / 'longdev-lease'
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def lock_path(root: Path, resource: str) -> Path:
    digest = hashlib.sha256(resource.encode('utf-8')).hexdigest()[:16]
    return lease_dir(root) / f'{digest}.lock'


def read_lock(path: Path):
    try:
        return json.loads(path.read_text('utf-8'))
    except (OSError, ValueError):
        return None


def stale(record) -> bool:
    if not record:
        return True
    try:
        at = datetime.fromisoformat(record['at'])
        age = (datetime.now(timezone.utc) - at).total_seconds()
    except Exception:
        return True
    return age > STALE_SECONDS


def acquire(root: Path, resource: str, timeout: float = 0.0) -> str:
    path = lock_path(root, resource)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            record = read_lock(path)
            if stale(record):
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise RuntimeError(f'write lease held on resource {resource!r}: {record}')
            time.sleep(0.5)
            continue
        token = os.urandom(16).hex()
        record = {'token': token, 'pid': os.getpid(), 'host': socket.gethostname(),
                  'resource': resource, 'at': datetime.now(timezone.utc).isoformat()}
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        return token


def release(root: Path, resource: str, token: str):
    path = lock_path(root, resource)
    record = read_lock(path)
    if not record:
        return {'released': False, 'reason': 'no lease'}
    if record.get('token') != token:
        raise RuntimeError('lease token mismatch')
    path.unlink()
    return {'released': True}


def status(root: Path, resource: str):
    path = lock_path(root, resource)
    record = read_lock(path)
    if not record:
        return {'held': False}
    return {'held': True, 'stale': stale(record),
            **{key: record[key] for key in ('pid', 'host', 'at', 'resource') if key in record}}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('acquire', 'release', 'status'):
        p = sub.add_parser(name)
        p.add_argument('--project', required=True)
        p.add_argument('--resource', required=True)
        p.add_argument('--token')
        p.add_argument('--timeout', type=float, default=0.0)
    args = parser.parse_args(argv)
    root = Path(args.project).resolve()
    if not root.is_dir():
        print(json.dumps({'ok': False, 'error': 'project missing'}, ensure_ascii=False))
        return 2
    try:
        if args.command == 'acquire':
            token = acquire(root, args.resource, args.timeout)
            print(json.dumps({'ok': True, 'token': token, 'resource': args.resource}, ensure_ascii=False))
            return 0
        if args.command == 'release':
            result = release(root, args.resource, args.token)
            print(json.dumps({'ok': bool(result.get('released')), **result}, ensure_ascii=False))
            return 0 if result.get('released') else 1
        if args.command == 'status':
            print(json.dumps({'ok': True, 'resource': args.resource, **status(root, args.resource)}, ensure_ascii=False))
            return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())