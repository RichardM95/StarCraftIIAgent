#!/usr/bin/env python3
"""Analyze, plan and safely migrate custom unit data chains."""
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from contextlib import ExitStack

from sc2_i18n import UIArgumentParser, run_cli, tr
from sc2_components import component_session
from sc2_migrate import analyze, report_markdown
from sc2_migrate_package import export_package, preview_import, apply_import


@component_session
def main(argv=None):
    parser=UIArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('analyze','plan','export','preview','apply'))
    parser.add_argument('--source',type=Path,action='append',default=[],help='Source component (repeatable)')
    parser.add_argument('--target',type=Path,help='Target Components directory')
    parser.add_argument('--prefix',default='AmithImported_',help='Prefix for copied catalog objects')
    parser.add_argument('--max-objects',type=int,default=2000,help='Per-unit object budget; reaching it blocks export')
    parser.add_argument('--selection',type=Path,help='JSON unit source selections and exclusions')
    parser.add_argument('--mods-dir',type=Path,help='Dependency Mods root')
    parser.add_argument('--campaigns-dir',type=Path,help='Dependency Campaigns root')
    parser.add_argument('--official-cache',type=Path,help='Verified official dependency cache')
    parser.add_argument('--source-cache',action='append',default=[],help='SourceName.SC2Mod=official-cache-directory (repeatable)')
    parser.add_argument('--input',type=Path,help='Previously generated migration plan JSON')
    parser.add_argument('--package',type=Path,help='Migration package directory')
    parser.add_argument('--output',type=Path,help='Report directory or new package directory')
    parser.add_argument('--apply',action='store_true',help='Write the verified import transaction')
    parser.add_argument('--read-casc-assets',action='store_true',help='Explicitly read required official assets from local CASC')
    parser.add_argument('--casc-dll',type=Path,help='Explicit CascLib DLL for asset reads')
    parser.add_argument('--sc2-install-dir',type=Path,help='SC2 installation for explicit asset reads')
    parser.add_argument('--json',action='store_true',help='Print machine-readable JSON')
    args=parser.parse_args(argv)
    try:
        if args.apply and args.command!='apply':
            raise ValueError('--apply is only valid with the apply command')
        with ExitStack() as stack:
            casc=None
            if args.read_casc_assets:
                if args.command not in {'analyze','plan','export'} or not args.casc_dll or not args.sc2_install_dir:
                    raise ValueError('Explicit asset reads require analyze/plan/export, --casc-dll and --sc2-install-dir')
                from sc2_official import probe, identity, cache_for_mods
                from sc2_casc import CascProcess
                verified=probe(args.sc2_install_dir,args.casc_dll,60)
                if verified['status']!='read_verified':
                    raise ValueError('CASC probe did not verify local reads')
                mods=args.mods_dir or args.sc2_install_dir/'Mods'
                cache=cache_for_mods(mods,args.official_cache,allow_partial=True)
                if cache is None or cache.data['identity']!=verified['identity']:
                    raise ValueError('CASC asset installation/build differs from official metadata cache')
                casc=stack.enter_context(CascProcess(args.casc_dll,args.sc2_install_dir,verified['encoding'],60))
            if args.command in {'analyze','plan'}:
                if not args.source or not args.target:
                    raise ValueError('Analysis requires --source and --target')
                selection=json.loads(args.selection.read_text(encoding='utf-8-sig')) if args.selection else None
                source_caches={}
                for item in args.source_cache:
                    name,separator,path=item.partition('=')
                    if not separator or not name or not path or name in source_caches:
                        raise ValueError('Invalid or duplicate --source-cache binding')
                    source_caches[name]=Path(path)
                if set(source_caches)-{p.name for p in args.source}:
                    raise ValueError('--source-cache names must match an explicit source component')
                if args.output:
                    output=args.output.resolve()
                    for component in [*args.source,args.target]:
                        component=component.resolve()
                        if output==component or output.is_relative_to(component) or component.is_relative_to(output):
                            raise ValueError('Report output must be disjoint from source and target components')
                result=analyze(args.source,args.target,prefix=args.prefix,selection=selection,
                               mods_dir=args.mods_dir,campaigns_dir=args.campaigns_dir,
                               official_cache=args.official_cache,source_caches=source_caches,casc=casc,
                               max_objects=args.max_objects,
                               progress=lambda message:print(message,file=sys.stderr))
                if args.output:
                    args.output.mkdir(parents=True,exist_ok=True)
                    with (args.output/'migration-plan.json').open('w',encoding='utf-8') as stream:
                        json.dump(result,stream,ensure_ascii=False,indent=2)
                    (args.output/'report.md').write_text(report_markdown(result),encoding='utf-8')
                    choices={'units':{c['id']:None for c in result['collisions']},'exclude':[]}
                    (args.output/'selection-template.json').write_text(json.dumps(choices,ensure_ascii=False,indent=2),encoding='utf-8')
                printable=result if args.json else result['summary']
            elif args.command=='export':
                if not args.input or not args.output:
                    raise ValueError('Export requires --input and --output')
                result=export_package(json.loads(args.input.read_text(encoding='utf-8-sig')),args.output,casc=casc)
                printable=result if args.json else {'package':str(args.output),'files':len(result['files'])}
            else:
                if not args.package:
                    raise ValueError('Preview/import requires --package')
                preview=preview_import(args.package,args.target)
                result=apply_import(preview,apply=args.apply) if args.command=='apply' else {
                    k:v for k,v in preview.items() if k not in {'outputs','expected','manifest'}}
                printable=result
            print(json.dumps(printable,ensure_ascii=False,indent=2))
            if not args.json:
                print(tr('Migration operation completed; inspect unresolved issues before export.'))
            return int(bool(result.get('conflicts')))
    except (OSError,ValueError,KeyError,ET.ParseError) as exc:
        print(json.dumps({'status':'failed','error':str(exc)},ensure_ascii=False),file=sys.stderr)
        return 1


if __name__=='__main__':
    import xml.etree.ElementTree as ET
    sys.exit(run_cli(main))
