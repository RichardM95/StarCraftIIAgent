#!/usr/bin/env python3
"""Install/build the pinned Galaxy frontend and save its local Node selection."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node',default=os.environ.get('SC2_GALAXY_NODE') or shutil.which('node'))
    parser.add_argument('--pnpm',default=shutil.which('pnpm'))
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    if not args.node or not args.pnpm:parser.error('provide --node and --pnpm')
    node=str(Path(args.node).resolve()); pnpm=str(Path(args.pnpm).resolve())
    version=subprocess.run([node,'--version'],check=True,capture_output=True,text=True).stdout.strip()
    if int(version.lstrip('v').split('.')[0])<22:parser.error('Node 22+ required')
    env=dict(os.environ);env['PATH']=str(Path(node).parent)+os.pathsep+env.get('PATH','')
    directory=ROOT/'integrations/galaxy-frontend'
    # Windows .cmd launchers must be invoked by cmd; subprocess handles their
    # native batch dispatch. Arguments here are fixed, never shell-built input.
    command=[pnpm,'install','--frozen-lockfile','--ignore-scripts']
    if args.offline:command.append('--offline')
    subprocess.run(command,cwd=directory,env=env,check=True)
    subprocess.run([pnpm,'run','build'],cwd=directory,env=env,check=True)
    config=ROOT/'.runtime/galaxy-frontend.json';config.parent.mkdir(parents=True,exist_ok=True)
    config.write_text(json.dumps({'node':node,'version':version}),encoding='utf-8')
    print(json.dumps({'status':'frontend built','node':node,'version':version}))


if __name__=='__main__':main()
