#!/usr/bin/env python3
"""Merge local mod catalogs, assets and text without copying official layers."""
import json
from pathlib import Path
from sc2_i18n import UIArgumentParser,run_cli
from sc2_mod_layers import build_plan,apply_plan


def main():
    parser=UIArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('plan','prune','apply'))
    parser.add_argument('--source',type=Path,action='append',default=[],help='Local source component; later sources have higher priority')
    parser.add_argument('--target',type=Path,help='Target Components directory')
    parser.add_argument('--output',type=Path,help='New work directory for the staged merge')
    parser.add_argument('--input',type=Path,help='Previously generated local-layer plan')
    parser.add_argument('--apply',action='store_true',help='Publish the verified local-layer merge')
    parser.add_argument('--source-cache',action='append',default=[],metavar='SOURCE=CACHE')
    args=parser.parse_args()
    try:
        if args.command=='plan':
            if args.apply or not args.source or not args.target or not args.output:
                raise ValueError('Plan requires sources, target and output, without --apply')
            plan=build_plan(args.source,args.target,args.output)
            result={'plan':str(args.output/'layer-plan.json'),'summary':plan['summary'],'validation':plan['validation']}
        elif args.command=='prune':
            from sc2_migrate_prune import build_prune_plan
            if args.apply or not args.input or not args.output:
                raise ValueError('Prune requires original merge input and new output, without --apply')
            caches=dict(value.split('=',1) for value in args.source_cache)
            plan=build_prune_plan(args.input,caches,args.output)
            result={'plan':str(args.output/'layer-plan.json'),'summary':plan['summary'],'validation':plan['validation']}
        else:
            if not args.input:
                raise ValueError('Apply requires --input')
            result=apply_plan(args.input,apply=args.apply)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False))
        return 1


if __name__=='__main__':
    raise SystemExit(run_cli(main))
