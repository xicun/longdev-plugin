"""Inventory and safely converge legacy records in the selected workspace (Python 3.9+)."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

# 同一完整 skill bundle 内的模块，既可从 CLI 也可从隔离测试导入。
sys.path.insert(0, str(Path(__file__).resolve().parent))
from history_convergence import converge, MARKER, LEGACY_MARKER, JOURNAL


def migrate(project, check=False, dry_run=False):
    return converge(project, check=check, dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='Read-only compact status')
    mode.add_argument('--dry-run', action='store_true', help='Read-only complete task/file action preview')
    args = parser.parse_args()
    try:
        report = migrate(args.project, args.check, args.dry_run)
        result = report if not args.check else {key: report[key] for key in ('status', 'summary', 'tracking_pending')}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if report['status'] == 'needs_review':
            return 2
        if args.check or args.dry_run:
            return 1 if report['actions'] else 0
        return 0
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'blocked', 'error': str(error)}, ensure_ascii=False))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
