from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from pathlib import Path

from .server import create_server
from .agent_bridge import runtime_base
from sc2_i18n import UIArgumentParser


def main():
    parser = UIArgumentParser(description='SC2 Editor MCP service')
    parser.add_argument('--state',type=Path)
    parser.add_argument('--project-states',action='store_true',help='Route explicit projects into their project runtime folders')
    parser.add_argument('--list-tools',action='store_true',help='输出工具 JSON 并退出（不运行协议）')
    parser.add_argument('--capabilities',action='store_true',help='输出能力 JSON 并退出')
    args=parser.parse_args()
    project_states=args.project_states or (args.state is None and 'SC2_EDITOR_STATE' not in os.environ)
    args.state=args.state or Path(os.environ.get('SC2_EDITOR_STATE',runtime_base()/'sc2'))
    args.state.mkdir(parents=True,exist_ok=True)
    log=args.state/'logs';log.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.WARNING,handlers=[logging.FileHandler(log/'service.log',encoding='utf-8')])
    server=create_server(args.state,project_states=project_states)
    try:
        if args.list_tools:
            tools=asyncio.run(server.list_tools())
            print(json.dumps([t.model_dump(mode='json') for t in tools],ensure_ascii=False,indent=2))
        elif args.capabilities:
            print(json.dumps(server.sc2_service.capabilities(),ensure_ascii=False,indent=2))
        else:
            server.run(transport='stdio')
    finally:
        server.sc2_dispatcher.close()


if __name__=='__main__':
    main()
