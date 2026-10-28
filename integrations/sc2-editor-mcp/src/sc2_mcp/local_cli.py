"""JSON CLI using the exact same dispatcher and validation as the MCP adapter."""
from __future__ import annotations
import argparse
import inspect
import json
from pathlib import Path
import sys
import time
from .agent_bridge import runtime_base
from sc2_i18n import UIArgumentParser
from .dispatch import Dispatcher
from .errors import SC2Error


def main(argv=None):
    parser = UIArgumentParser(description='SC2 shared local tools')
    parser.add_argument('--state', type=Path, help='Explicit isolated state; otherwise use project runtime routing')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('capabilities')
    tools = commands.add_parser('tools')
    tools.add_argument('--operation', help='Return only one operation schema')
    tools.add_argument('--names-only', action='store_true')
    call = commands.add_parser('call')
    call.add_argument('operation')
    group = call.add_mutually_exclusive_group()
    group.add_argument('--arguments', help='JSON object; use a file for multiline or shell-sensitive values')
    group.add_argument('--arguments-file', type=Path)
    args = parser.parse_args(argv)
    dispatcher = None
    try:
        dispatcher = Dispatcher(args.state or runtime_base() / 'sc2', project_states=args.state is None)
        if args.command == 'tools':
            selected = {n: value for n, value in dispatcher.operations.items() if not args.operation or n == args.operation}
            if args.operation and not selected:
                raise SC2Error('unsupported_operation', 'Unknown operation', operation=args.operation)
            result = {'ok': True, 'result': list(selected) if args.names_only else [{'name': n, 'read_only': readonly,
                       'description': inspect.getdoc(fn), 'parameters': dispatcher.schemas[n].model_json_schema()}
                       for n, (fn, readonly) in selected.items()]}
        else:
            arguments = json.loads(args.arguments_file.read_text('utf-8-sig') if args.command == 'call' and args.arguments_file
                                   else (args.arguments or '{}') if args.command == 'call' else '{}')
            operation = 'sc2_capabilities' if args.command == 'capabilities' else args.operation
            # The CLI process owns jobs until completion; callers can run it in an exec session.
            if operation in dispatcher.schemas and 'background' in dispatcher.schemas[operation].model_fields:
                arguments.setdefault('background', False)
            result = dispatcher.call(operation, arguments)
            if isinstance(result['result'], dict) and result['result'].get('job_id'):
                job_id = result['result']['job_id']
                while True:
                    status = dispatcher.call('sc2_job_status', {'job_id': job_id})
                    if status['result'].get('state') not in ('queued', 'running', 'cancelling'):
                        result = status
                        break
                    time.sleep(0.1)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except SC2Error as exc:
        print(json.dumps({'ok': False, 'error': exc.as_dict()}, ensure_ascii=False))
        return 2 if exc.code in ('invalid_request', 'unsupported_operation') else 1
    except (ValueError, OSError) as exc:
        print(json.dumps({'ok': False, 'error': {'code': 'invalid_request', 'message': str(exc)}}, ensure_ascii=False))
        return 2
    finally:
        if dispatcher:
            dispatcher.close()


if __name__ == '__main__':
    sys.exit(main())
