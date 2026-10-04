#!/usr/bin/env python3
"""Cross-worktree write lease for longdev shared mutable state.

longdev's single source of truth (docs/longdev/, docs/bugs/, testcases/) are
tracked working-tree files. Git worktrees each have their own working tree but
share one object database, so a per-worktree lock (e.g. under .work/) would NOT
serialize writers. This lease places the lock under the Git **common dir**, which
every worktree of the repo shares, so concurrent writers across worktrees
serialize instead of silently overwriting / swallowing conflicts. stdlib only.

Lease safety contract (matches session-runtime.md: "lease_expires 只用于发现
失联会话，不能自动证明旧客户端已经停止"):

- Locks are published atomically (temp file + os.link), so another process never
  observes an empty or half-written lock file.
- A held lease is never deleted automatically — not on age, not on corruption.
  ``status`` flags suspicious records; reclaiming one requires the explicit
  ``takeover`` command, whose caller is responsible for having verified that the
  previous writer stopped (process check, file changes, command results), or for
  carrying explicit user authorization to take over.
- ``renew`` lets a live writer extend its lease; each renew bumps a generation
  counter so an old token cannot silently regain write access after a takeover.
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
    """Return (record, corrupt); corrupt=True when the file exists but is unreadable."""
    try:
        text = path.read_text('utf-8')
    except OSError:
        return None, False
    try:
        record = json.loads(text)
    except ValueError:
        return None, True
    if not isinstance(record, dict) or not record.get('token'):
        return None, True
    return record, False


def stale(record) -> bool:
    if not record:
        return True
    try:
        at = datetime.fromisoformat(record['at'])
        age = (datetime.now(timezone.utc) - at).total_seconds()
    except Exception:
        return True
    return age > STALE_SECONDS


def _write_record(path: Path, record) -> None:
    temp = path.with_name(f'.{path.name}.{os.urandom(6).hex()}.tmp')
    try:
        with open(temp, 'w', encoding='utf-8', newline='\n') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # Atomic publish: readers see either no lock or a complete record.
            os.link(str(temp), str(path))
        except OSError:
            if path.exists():
                raise
            # Filesystems without hard-link support: fall back to O_EXCL create;
            # an interrupted write then leaves a record treated as corrupt below.
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
    finally:
        try:
            temp.unlink()
        except OSError:
            pass


def _new_record(token: str, resource: str, **extra) -> dict:
    record = {'token': token, 'pid': os.getpid(), 'host': socket.gethostname(),
              'resource': resource, 'gen': 1,
              'at': datetime.now(timezone.utc).isoformat()}
    record.update(extra)
    return record


def acquire(root: Path, resource: str, timeout: float = 0.0) -> str:
    path = lock_path(root, resource)
    deadline = time.monotonic() + timeout
    while True:
        record, corrupt = read_lock(path)
        if corrupt:
            raise RuntimeError(
                f'write lease record on resource {resource!r} is empty or corrupt: {path}; '
                f'inspect the scene, then reclaim via `takeover` if confirmed abandoned')
        if record is not None:
            if stale(record):
                raise RuntimeError(
                    f'write lease on resource {resource!r} looks stale; diagnose the previous '
                    f'writer first, then reclaim via `takeover`: {record}')
            if time.monotonic() >= deadline:
                raise RuntimeError(f'write lease held on resource {resource!r}: {record}')
            time.sleep(0.5)
            continue
        token = os.urandom(16).hex()
        try:
            _write_record(path, _new_record(token, resource))
            return token
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f'write lease held on resource {resource!r}') from None
            time.sleep(0.5)
            continue


def renew(root: Path, resource: str, token: str) -> dict:
    """Extend the caller's lease; bumps the generation counter."""
    path = lock_path(root, resource)
    record, corrupt = read_lock(path)
    if not record:
        raise RuntimeError('write lease lost on resource %r: lock file missing or unreadable'
                           % resource)
    if record.get('token') != token:
        raise RuntimeError('lease token mismatch')
    record['at'] = datetime.now(timezone.utc).isoformat()
    record['gen'] = int(record.get('gen', 1)) + 1
    temp = path.with_name(f'.{path.name}.{os.urandom(6).hex()}.tmp')
    with open(temp, 'w', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(str(temp), str(path))
    return {'renewed': True, 'gen': record['gen'], 'at': record['at']}


def takeover(root: Path, resource: str, expect_state: str,
             expect_token: str | None, reason: str) -> str:
    """Reclaim a suspicious lease after the caller verified the old writer stopped.

    Caller responsibility (session-runtime.md): confirm via process state, file
    changes and command results that no concurrent writer remains — or carry
    explicit user authorization to take over. Only stale or corrupt records may
    be taken over; the observed state/token must match what the caller saw.
    """
    path = lock_path(root, resource)
    if not path.exists():
        raise RuntimeError(f'no lease present on resource {resource!r}; nothing to take over')
    record, corrupt = read_lock(path)
    if record is None and not corrupt:
        raise RuntimeError(f'no lease present on resource {resource!r}; nothing to take over')
    state = 'corrupt' if record is None else ('stale' if stale(record) else 'held')
    if state == 'held':
        raise RuntimeError(f'lease is held and fresh; takeover requires a stale or corrupt '
                           f'record: {record}')
    if expect_state != state:
        raise RuntimeError(f'lease state changed: expected {expect_state!r}, current is {state!r}; '
                           're-diagnose before takeover')
    if state == 'stale' and record.get('token') != expect_token:
        raise RuntimeError('lease token mismatch')
    try:
        path.unlink()
    except OSError as error:
        raise RuntimeError(f'cannot remove suspicious lease {path}: {error}') from error
    token = os.urandom(16).hex()
    _write_record(path, _new_record(token, resource,
                                    took_over_from={'token': expect_token, 'reason': reason}))
    return token


def release(root: Path, resource: str, token: str):
    path = lock_path(root, resource)
    record, corrupt = read_lock(path)
    if not record:
        return {'released': False, 'reason': 'no lease'}
    if record.get('token') != token:
        raise RuntimeError('lease token mismatch')
    path.unlink()
    return {'released': True}


def status(root: Path, resource: str):
    path = lock_path(root, resource)
    record, corrupt = read_lock(path)
    if record is None and not corrupt:
        return {'held': False}
    info = {'held': True, 'stale': stale(record), 'corrupt': corrupt}
    if record:
        info.update({key: record[key] for key in ('pid', 'host', 'at', 'resource', 'gen')
                     if key in record})
    return info


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('acquire', 'release', 'status'):
        p = sub.add_parser(name)
        p.add_argument('--project', required=True)
        p.add_argument('--resource', required=True)
        p.add_argument('--token')
        p.add_argument('--timeout', type=float, default=0.0)
    take = sub.add_parser('takeover')
    take.add_argument('--project', required=True)
    take.add_argument('--resource', required=True)
    take.add_argument('--expect-state', required=True, choices=('stale', 'corrupt'))
    take.add_argument('--expect-token')
    take.add_argument('--reason', required=True)
    rn = sub.add_parser('renew')
    rn.add_argument('--project', required=True)
    rn.add_argument('--resource', required=True)
    rn.add_argument('--token', required=True)
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
        if args.command == 'renew':
            result = renew(root, args.resource, args.token)
            print(json.dumps({'ok': True, 'resource': args.resource, **result}, ensure_ascii=False))
            return 0
        if args.command == 'takeover':
            token = takeover(root, args.resource, args.expect_state, args.expect_token, args.reason)
            print(json.dumps({'ok': True, 'token': token, 'resource': args.resource}, ensure_ascii=False))
            return 0
        if args.command == 'status':
            info = status(root, args.resource)
            print(json.dumps({'ok': True, 'resource': args.resource, **info}, ensure_ascii=False))
            return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
