"""Compile-output packaging into NEW runtime artifacts, never project sources."""
from __future__ import annotations
import json
from pathlib import Path
import re
import uuid
from . import archives
from .agent_bridge import project_runtime
from .errors import SC2Error
from .storage import digest, guard_absolute_path, write_json
from .trigger_pipeline import check_build, controlled_files, target_for


def package_build(service,project_id,build_id,installation=None):
    _,root=service.record(project_id)
    from .dependencies import decode_declarations
    from .shell import header_dependencies
    info=decode_declarations((root/'DocumentInfo').read_bytes())
    header=root/'DocumentHeader'
    if not header.is_file() or header_dependencies(header.read_bytes())['values']!=info:
        raise SC2Error('offline_shell_mismatch','DocumentInfo and DocumentHeader dependencies differ; synchronize via dependency tools before packaging')
    if not re.fullmatch('[0-9a-f]{32}',build_id):raise SC2Error('galaxy_build_invalid','invalid build ID')
    folder=guard_absolute_path(project_runtime(root)/'galaxy-builds'/build_id)
    manifest=json.loads((folder/'manifest.json').read_text('utf-8'))
    marker=manifest.get('runtime_marker')
    if not marker or not re.fullmatch('GUI_OFFLINE_EXEC_[0-9a-f]{12}',marker):
        raise SC2Error('offline_runtime_proof_required','generate with runtime_probe=true before packaging')
    if manifest.get('native_supplements') and not manifest.get('compile_only_files'):
        raise SC2Error('offline_legacy_native_context','regenerate: legacy build emits GUI-derived native declarations at runtime')
    checked=check_build(service,project_id,build_id)
    if checked['status']!='static validation passed':
        raise SC2Error('offline_compile_failed','build has compiler errors',diagnostics=checked['diagnostics'])
    if root.suffix.lower()!='.sc2map':raise SC2Error('offline_map_required','runtime artifact requires an explicit map shell')
    output=guard_absolute_path(project_runtime(root)/'galaxy-runtime'/uuid.uuid4().hex[:12])
    if output.is_relative_to(root):raise SC2Error('unsafe_build_root','runtime package must be outside source')
    assembly=output/'assembly';assembly.mkdir(parents=True,exist_ok=False)
    entries,_=archives._collect_export_members(root)
    source_hashes={};excluded=[]
    for relative,path in entries:
        if path.name.casefold()=='mapscript.galaxy' or re.fullmatch(r'Lib[0-9A-Fa-f]{8}(?:_h)?\.galaxy',path.name,re.I):
            excluded.append(relative);continue
        raw=path.read_bytes();source_hashes[relative]=digest(raw)
        target=assembly/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    code=manifest['files'][manifest['entry']].encode('utf-8')
    if header_dependencies((assembly/'DocumentHeader').read_bytes())['values']!=decode_declarations((assembly/'DocumentInfo').read_bytes()):
        raise SC2Error('offline_shell_mismatch','assembly DocumentHeader dependencies differ from DocumentInfo')
    # This is an automatically emitted build artifact. The original map's
    # generated file is neither opened for writing nor passed to transactions.
    (assembly/'MapScript.galaxy').write_bytes(code)
    for virtual,text in manifest['files'].items():
        if virtual==manifest['entry'] or virtual in manifest['scripts'] or virtual in manifest.get('compile_only_files',[]):continue
        relative=archives._validate_member_name(virtual)
        p=assembly/relative
        if p.exists() and p.read_bytes()!=text.encode('utf-8'):
            raise SC2Error('offline_virtual_collision','private compiler file collides with source',path=relative)
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')
    artifact=output/('GuiOffline_'+build_id[:12]+'.SC2Map')
    exported=archives.export_archive(assembly,artifact)
    verified=next((f for f in exported['files'] if f['path'].casefold()=='mapscript.galaxy'),None)
    if not verified or verified['sha256']!=digest(code):
        raise SC2Error('offline_entry_mismatch','MPQ entry differs from compiler output')
    for relative,expected in source_hashes.items():
        if digest((root/relative).read_bytes())!=expected:
            raise SC2Error('offline_source_changed','source changed during packaging',path=relative)
    current=target_for(root,manifest['mods_dir'])
    _,scripts=controlled_files(current,skip_generated=True)
    if current.problems or current.inputs!=manifest['inputs'] or scripts!=manifest['scripts']:
        raise SC2Error('offline_source_changed','dependency inputs changed during packaging')
    result={'schema':1,'status':'static validation passed','project_id':project_id,'build_id':build_id,
            'archive':str(artifact),'archive_sha256':digest(artifact.read_bytes()),
            'entry_sha256':digest(code),'runtime_marker':marker,'verified_archive':exported,
            'source':str(root),'source_hashes':source_hashes,'excluded_editor_outputs':excluded,
            'compile_only_files':manifest.get('compile_only_files',[]),'engine_abi_verified':False,
            'source_generated_files_modified':False,'packaged_runtime_passed':False}
    if installation:
        from .editor import build_launch_command
        plan=build_launch_command(artifact,Path(installation),'test','s2_cn')
        # Fixed, validated local paths only. Refuse cmd expansion characters.
        if any(any(c in str(arg) for c in '%!\r\n&|<>^') for arg in [*plan['argv'],plan['cwd']]):
            raise SC2Error('unsafe_launcher_path','launcher paths contain cmd expansion characters')
        launcher=output/'RunOfflineTest.cmd'
        from .editor import write_test_launcher
        write_test_launcher(launcher, artifact, Path(installation))
        result['launcher']=str(launcher);result['launch_plan']=plan
    write_json(output/'runtime-package.json',result)
    return result
