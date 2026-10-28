"""JSON CLI sharing the task router and manager with the MCP adapter."""
import argparse
import asyncio
import json
from pathlib import Path
from .manager import TaskSpec
from sc2_i18n import UIArgumentParser
from .router import TaskRouter
from .configuration import capabilities, diagnose, available_models


async def run_command(args):
    router = TaskRouter()
    try:
        if args.command in ('run', 'followup'):
            if args.command == 'run':
                spec = TaskSpec.model_validate_json(Path(args.packet).read_text(encoding='utf-8-sig'))
                record = await router.submit(spec)
            else:
                record = await router.continue_task(args.task_id, args.prompt)
            print(json.dumps({'ok': True, 'result': record}, ensure_ascii=False), flush=True)
            manager = router.for_task(record['task_id'])
            job = manager.jobs.get(record['task_id'])
            if job:
                await job
            result = router.result(record['task_id'])
        elif args.command == 'list':
            result = router.list_tasks(args.limit)
        elif args.command == 'status':
            result = router.status(args.task_id)
        elif args.command == 'result':
            result = router.result(args.task_id)
        elif args.command == 'cancel':
            result = await router.cancel(args.task_id)
        elif args.command == 'integrate':
            result = router.integrate(args.task_id, args.review_note)
        elif args.command == 'capabilities':
            result = capabilities()
        elif args.command == 'models':
            result = available_models()
        else:
            result = diagnose()
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False), flush=True)
        if args.command == 'diagnose' and not result['ok']:
            return 1
        if args.command in ('run', 'followup'):
            state = result.get('status', {}).get('state')
            return 1 if state in ('failed', 'timed_out', 'cancelled', 'interrupted') else 0
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'invalid_request', 'message': str(exc)}}, ensure_ascii=False))
        return 2
    finally:
        await router.close()


def main(argv=None):
    parser = UIArgumentParser(description='Isolated SC2 model tasks')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('serve')
    run = commands.add_parser('run')
    run.add_argument('--packet', required=True)
    commands.add_parser('capabilities')
    commands.add_parser('diagnose')
    commands.add_parser('models')
    listing = commands.add_parser('list')
    listing.add_argument('--limit', type=int, default=20)
    followup = commands.add_parser('followup')
    followup.add_argument('task_id')
    followup.add_argument('--prompt', required=True)
    for name in ('status', 'result', 'cancel'):
        commands.add_parser(name).add_argument('task_id')
    integrate = commands.add_parser('integrate')
    integrate.add_argument('task_id')
    integrate.add_argument('--review-note', required=True)
    args = parser.parse_args(argv)
    if args.command == 'serve':
        from .server import main as serve
        serve()
        return 0
    return asyncio.run(run_command(args))


if __name__ == '__main__':
    raise SystemExit(main())
