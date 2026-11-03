"""JSON adapter to the pinned standalone Galaxy parser/binder/type checker."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
from .agent_bridge import root as workspace
from .errors import SC2Error
from .storage import digest

REVISION='95d1ff82b8e89fb0078c4b8e5e6622271b927b94'


def check_files(files, entry, source_map=None, declarations=()):
    if entry not in files:raise SC2Error('galaxy_entry_missing','entry is not in controlled file set')
    checked_entry=entry
    if declarations:
        checked_entry='__agent_static_context__.galaxy'
        if checked_entry in files or any(p not in files or not p.endswith('.galaxy') for p in declarations):
            raise SC2Error('galaxy_static_context_invalid','invalid compile-only declaration files')
        files={**files,checked_entry:''.join('include '+json.dumps(p[:-7])+'\n' for p in [*declarations,entry])}
    bridge=workspace/'integrations/galaxy-frontend/dist/bridge.mjs'
    config=workspace/'.runtime/galaxy-frontend.json'
    local=json.loads(config.read_text('utf-8')) if config.is_file() else {}
    node=os.environ.get('SC2_GALAXY_NODE') or local.get('node') or shutil.which('node')
    if not node or not bridge.is_file():
        raise SC2Error('galaxy_frontend_unavailable','Build integrations/galaxy-frontend and configure SC2_GALAXY_NODE')
    try:
        version=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=10)
        if version.returncode or int(version.stdout.strip().lstrip('v').split('.')[0])<22:raise ValueError('Node 22+ required')
        proc=subprocess.run([node,str(bridge)],input=json.dumps({'files':files,'entry':checked_entry}),
                            capture_output=True,text=True,encoding='utf-8',timeout=120)
        if proc.returncode:raise ValueError(proc.stderr[:2000])
        result=json.loads(proc.stdout)
    except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
        raise SC2Error('galaxy_frontend_unavailable',str(exc)) from exc
    for diagnostic in result['diagnostics']:
        if diagnostic.get('file')==entry:
            matches=[m for m in source_map or [] if m['start']<=diagnostic['line']<=m['end']]
            if matches:diagnostic['gui']=matches[-1]
    result.update(status='failed' if any(d['severity']=='error' for d in result['diagnostics']) else 'static validation passed',
                  frontend={'name':'sc2-galaxy-lang','revision':REVISION,'node':version.stdout.strip()},
                  inputs={p:digest(t.encode('utf-8')) for p,t in files.items()},
                  static_context={'entry':entry,'declarations':list(declarations),'engine_abi_verified':False},
                  editor_accepted=False,packaged_runtime_passed=False)
    return result
