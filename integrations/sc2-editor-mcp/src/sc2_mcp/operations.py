"""Transport-independent operations shared by CLI and MCP; no MCP SDK imports."""
from __future__ import annotations
import uuid
from pathlib import Path
from . import assets, casc, catalog, dependencies, editor, localization, script, spatial
from .errors import SC2Error
from .storage import safe_path
from .terrain import Terrain, render_terrain

DISABLED = {'sc2_script_replace', 'sc2_script_guarded_replace', 'sc2_script_build'}


def create_operations(service):
    operations = {}
    def register(readonly=False):
        def decorate(fn):
            if not fn.__name__.startswith('sc2_keystone_') and fn.__name__ not in DISABLED:
                operations[fn.__name__] = (fn, readonly)
            return fn
        return decorate

    @register(True)
    def sc2_capabilities() -> dict:
        """返回真实支持范围、实验功能、未完成项、版本与验证层级。"""
        result = service.capabilities()
        result['integration'] = {'implementation': 'shared-cli-mcp',
            'exposed_operations': list(operations), 'excluded_profiles': ['keystone'],
            'generated_galaxy': 'read_only', 'existing_workspace_tools_remain_default': True}
        return result


    @register(False)
    def sc2_project_open(path: str, writable: bool=False, profile: str='auto', search_roots: list[str]|None=None) -> dict:
        """打开组件地图/模组或隔离解包 MPQ；写操作需显式 writable=true。"""
        return service.projects.open(path,writable,profile,search_roots)


    @register(True)
    def sc2_project_list() -> dict:
        """列出此服务独立注册的项目。"""
        return {'projects':service.projects.list()}


    @register(True)
    def sc2_project_inspect(project_id: str) -> dict:
        """识别组件、地区、地形版本、地图指纹及当前适配层。"""
        return service.info(project_id)


    @register(True)
    def sc2_validate_map_shell(project_id: str, installation: str|None=None,
                               product: str|None=None, branch: str|None=None,
                               locale: str='zhCN') -> dict:
        """只读审计地图外壳、版本旁车，并可核对地区客户端环境。"""
        return service.map_shell_audit(project_id,installation,product,branch,locale)


    @register(True)
    def sc2_cliff_capability_status() -> dict:
        """返回原生悬崖/坡道能力的固定科研边界；不生成写入候选。"""
        return service.cliff_capability_status()


    @register(True)
    def sc2_validate_data_warnings(project_id: str, log_path: str|None=None, log_text: str|None=None) -> dict:
        """解析 SC2 XML/USER 警告，绑定本地 Catalog 证据并区分候选修复、依赖审计和运行时检查；只读。"""
        return service.data_warnings_audit(project_id,log_path,log_text)


    @register(False)
    def sc2_plan_data_warning_repairs(project_id: str, log_path: str|None=None,
                                       log_text: str|None=None, repair_ids: list[str]|None=None,
                                       include_inferred: bool=False) -> dict:
        """根据已绑定的本地 XML 警告生成字节保留事务候选；官方依赖、重复 ID 和运行时警告保持阻断。"""
        return service.prepare_data_warning_repairs(
            project_id,log_path,log_text,repair_ids,include_inferred)


    @register(True)
    def sc2_project_read_text(project_id: str, path: str, offset: int=0, limit: int=16000) -> dict:
        """分段读取项目内 UTF-8 文本，返回精确修改所需 SHA-256。"""
        return service.read_text(project_id,path,offset,limit)


    @register(False)
    def sc2_project_clone(project_id: str, destination: str) -> dict:
        """克隆为独立工作副本；目标必须不存在。"""
        return service.projects.clone(project_id,destination)


    @register(False)
    def sc2_project_register_template(project_id: str, name: str, evidence_id: str) -> dict:
        """将具备匹配当前指纹的编辑器载入证据的项目注册为模板。"""
        return service.register_template(project_id,name,evidence_id)


    @register(False)
    def sc2_project_create(template: str, destination: str) -> dict:
        """从已注册且指纹未变的模板创建新组件项目；不猜测地图外壳。"""
        return service.create_from_template(template,destination)


    @register(False)
    def sc2_project_export(project_id: str, destination: str, background: bool=True) -> dict:
        """导出全新真实 MPQ 并回读全部成员哈希，默认后台任务。"""
        if background: return service.jobs.submit('export',lambda cancel:service.export(project_id,destination,cancel))
        return service.export(project_id,destination)


    @register(True)
    def sc2_terrain_inspect(project_id: str) -> dict:
        """读取高度/悬崖层级/坡道/纹理信息；不把离线分析当引擎验证。"""
        return Terrain(service.record(project_id)[1]).summary()


    @register(True)
    def sc2_terrain_preview(project_id: str) -> dict:
        """输出离线高度、材质权重、绘制通行限制、几何立体诊断 PNG。"""
        return render_terrain(service.record(project_id)[1],service.state/'previews'/uuid.uuid4().hex)


    @register(False)
    def sc2_terrain_edit(project_id: str, operations: list[dict], preview_only: bool=True, experimental_write: bool=False, background: bool=False) -> dict:
        """实验地形操作。op: raise/set_height/smooth/paint_texture/block_ground/block_building/clear_*_paint；rect=[x0,y0,x1,y1]。独立测试图可显式 experimental_write；默认仅候选。"""
        fn=lambda cancel:service.edit(project_id,'terrain',{'operations':operations},preview_only,experimental_write,cancel)
        return service.jobs.submit('terrain',fn) if background else fn(None)


    @register(False)
    def sc2_terrain_flatten_protected(project_id: str, rect: list[int], protected_rects: list[list[int]]|None=None, protected_mask: list[list[bool]]|None=None, brush_value: int|None=None, preview_only: bool=True, experimental_write: bool=False) -> dict:
        """实验：只整平未保护笔刷顶点，保留悬崖/坡道结构，必须再原生同步。"""
        return service.edit(project_id,'terrain_flatten_protected',{'rect':rect,'protected_rects':protected_rects,'protected_mask':protected_mask,'brush_value':brush_value},preview_only,experimental_write)


    @register(False)
    def sc2_spatial_ground_offsets(project_id: str, placements: list[dict], preview_only: bool=True, experimental_write: bool=False) -> dict:
        """实验：显式world_z_offset加已同步地面高度，未知装饰物坐标模式拒绝。"""
        return service.edit(project_id,'ground_offsets',{'placements':placements},preview_only,experimental_write)


    @register(False)
    def sc2_terrain_native_sync(project_id: str, control_archive: str, candidate_archive: str, destination: str, installation: str, expected_editor_sha256: str, timeout: float=120, background: bool=True) -> dict:
        """仅复制独立单归档后串行原生重存对照/候选；已有编辑器阻塞，完成仍需语义门禁。"""
        fn=lambda cancel:service.native_sync(project_id,control_archive,candidate_archive,destination,installation,expected_editor_sha256,timeout,cancel)
        return service.jobs.submit('terrain_native_sync',fn) if background else fn(None)


    @register(False)
    def sc2_terrain_native_candidate(project_id: str, control_before: str, control_after: str, candidate_before: str, candidate_after: str, protected_mask: list[list[bool]]|None=None, support_radius: int=3) -> dict:
        """将成对原生结果通过保护与邻域检查后转换为白名单地形候选。"""
        return service.prepare_native_result(project_id,control_before,control_after,candidate_before,candidate_after,protected_mask,support_radius)


    @register(True)
    def sc2_dependencies_inspect(project_id: str) -> dict:
        """按真实 DocumentInfo 解析递归依赖、文件/Battle.net来源、顺序、缺失与循环。"""
        return service.roots(project_id)[1]


    @register(False)
    def sc2_terrain_fields(project_id: str, source: str, texture_palette: dict[str,str]|None=None, preview_only: bool=True, experimental_write: bool=False) -> dict:
        """实验：应用NPZ连续高度/八层权重/限制网格；纹理槽位0..7。默认候选，保留头部与其他通道。"""
        return service.edit(project_id,'terrain_fields',{'source':source,'texture_palette':texture_palette},preview_only,experimental_write)


    @register(False)
    def sc2_terrain_environment(project_id: str, settings: dict[str,str], preview_only: bool=True, experimental_write: bool=False) -> dict:
        """精确修改当前地形类型的灯光、天空盒、雾等环境字段；保留菌毯、重力、镜头和几何。资源ID需按当前依赖核验，默认仅候选。"""
        return service.edit(project_id,'terrain_environment',{'settings':settings},preview_only,experimental_write)


    @register(False)
    def sc2_spatial_place_batch(project_id: str, objects: list[dict], ground_doodads: bool=True, preview_only: bool=False) -> dict:
        """批量放置单位、点和装饰；每项kind/attributes。装饰Position.z作贴地偏移，写入真实HeightAbsolute标记。"""
        return service.edit(project_id,'object_batch',{'objects':objects,'ground_doodads':ground_doodads},preview_only)


    @register(True)
    def sc2_validate_pathing_grid(project_id: str, starts: list[list[float]], clearance: float=1.5) -> dict:
        """仅检查绘制限制网格的静态连通，不含引擎碰撞、悬崖、装饰Footprint或实际单位寻路。"""
        from .pathing_audit import audit_grid
        layer=Terrain(service.record(project_id)[1]).pathing_layer('CellAttribute_Pnp')
        return audit_grid(layer==0,starts,clearance)


    @register(True)
    def sc2_dependencies_impact(project_id: str, values: list[str], catalogs: list[str]|None=None, limit: int=10000) -> dict:
        """只读分析拟定依赖集合造成的对象和字段变化，未知合并明确保留。"""
        return service.dependency_impact(project_id,values,catalogs,limit)


    @register(False)
    def sc2_dependencies_set(project_id: str, values: list[str], preview_only: bool=False) -> dict:
        """精确同步 DocumentInfo 与已验证版本 DocumentHeader 的依赖列表，自动备份。"""
        result=service.edit(project_id,'dependencies_set',{'values':values},preview_only)
        return result


    @register(True)
    def sc2_catalog_search(project_id: str, catalog_type: str, query: str='', limit: int=100) -> dict:
        """查询实际加载顺序中的 Catalog 对象，返回来源；依赖不完整时不声称最终值。"""
        roots,dep=service.roots(project_id)
        return {'objects':catalog.search_catalog(roots,catalog_type,query,limit),'dependencies_complete':dep['complete']}


    @register(True)
    def sc2_catalog_inspect(project_id: str, catalog_type: str, object_id: str) -> dict:
        """解释字段、继承、数组合并及来源；输出为静态近似，未知规则单列。"""
        roots,dep=service.roots(project_id)
        return {**catalog.inspect_catalog(roots,catalog_type,object_id),'dependencies':dep}


    @register(True)
    def sc2_catalog_references(project_id: str, catalog_type: str, object_id: str) -> dict:
        """查询入向/出向引用及可达链；动态 Actor 事件和脚本引用不伪装已解析。"""
        roots,dep=service.roots(project_id)
        return {**catalog.trace_references(roots,catalog_type,object_id),'dependencies_complete':dep['complete']}


    @register(False)
    def sc2_catalog_set(project_id: str, catalog_type: str, object_id: str, field_path: str, value: str, expected: str|None=None, preview_only: bool=False) -> dict:
        """按对象和字段上下文精确修改本地数据；如 LifeMax 或 WeaponArray[0].Link。"""
        return service.edit(project_id,'catalog_set',{'catalog':catalog_type,'object_id':object_id,'field_path':field_path,'value':value,'expected':expected},preview_only)


    @register(True)
    def sc2_spatial_inspect(project_id: str, kind: str='all') -> dict:
        """读取单位、装饰、点、组、镜头和区域的实际 XML 属性与稳定 ID。"""
        return spatial.inspect_spatial(service.record(project_id)[1],kind)


    @register(False)
    def sc2_spatial_edit(project_id: str, object_id: str, attributes: dict[str,str], preview_only: bool=False) -> dict:
        """修改空间对象属性；Position、Rotation、Scale 等按原 schema 校验。"""
        return service.edit(project_id,'object_edit',{'object_id':object_id,'attributes':attributes},preview_only)


    @register(False)
    def sc2_spatial_add(project_id: str, kind: str, attributes: dict[str,str], preview_only: bool=False) -> dict:
        """新增支持的空间对象，分配稳定唯一 ID；不生成未知相机格式。"""
        return service.edit(project_id,'object_add',{'kind':kind,'attributes':attributes},preview_only)


    @register(False)
    def sc2_spatial_remove(project_id: str, object_id: str, preview_only: bool=False) -> dict:
        """删除对象前检查 Galaxy/Triggers/组引用；有引用则拒绝。"""
        return service.edit(project_id,'object_remove',{'object_id':object_id},preview_only)


    @register(False)
    def sc2_spatial_region(project_id: str, region_id: int, name: str|None=None, rect: list[float]|None=None, preview_only: bool=False) -> dict:
        """精确修改区域名称或矩形边界，保护脚本绑定。"""
        return service.edit(project_id,'region_edit',{'region_id':region_id,'name':name,'rect':rect},preview_only)


    @register(True)
    def sc2_war3_inspect(project_id: str, source_directory: str) -> dict:
        """只读索引真实解包JASS的源指纹、调用、回调、随机顺序及完整选族分支；不是移植完成。"""
        return service.war3_inspect(project_id,source_directory)


    @register(True)
    def sc2_war3_plan(project_id: str, source_directory: str) -> dict:
        """生成绑定当前原始JASS的任务与明确阻塞；不生成占位实现。"""
        return service.war3_plan(project_id,source_directory)


    @register(True)
    def sc2_war3_coverage(project_id: str, source_directory: str, implementations: list[dict]|None=None) -> dict:
        """核对函数来源SHA及非作者审查绑定，未知和未实施功能仍为未完成。"""
        return service.war3_coverage(project_id,source_directory,implementations)


    @register(True)
    def sc2_script_guard(project_id: str, old: str, new: str, expected_sha256: str) -> dict:
        """检查精确修改是否删除/重排Galaxy结构、等待、触发器阶段及字符串回调；非语义编译。"""
        from .script_guard import guard
        _,root=service.record(project_id)
        changes=script.plan_script_replace(root,old,new,expected_sha256)
        return {'files':{relative:guard((root/relative).read_bytes(),data) for relative,data in changes.items()},
                'native_compile':'not_run','semantic_equivalence':'requires_non_author_review'}


    @register(False)
    def sc2_script_guarded_replace(project_id: str, old: str, new: str, expected_sha256: str, preview_only: bool=False, review: dict|None=None) -> dict:
        """使用有序结构守卫和现有多文件事务精确修改Galaxy，不绕过备份/冲突/恢复。"""
        return service.edit(project_id,'script_guarded_replace',{'old':old,'new':new,'expected_sha256':expected_sha256,'review':review},preview_only)


    @register(True)
    def sc2_script_build_inspect(project_id: str, manifest_path: str, expected_manifest_sha256: str|None=None) -> dict:
        """只读核验完整有序来源、初始化与基线；保全旧逻辑，不代表原生编译或运行通过。"""
        from .script_build import inspect_script_build
        return inspect_script_build(service.record(project_id)[1],manifest_path,expected_manifest_sha256)


    @register(False)
    def sc2_script_build(project_id: str, manifest_path: str, expected_manifest_sha256: str, preview_only: bool=False) -> dict:
        """从同一完整有序清单构建MapScript与Triggers，复用备份/冲突/回滚；既有来源仅可尾部追加。"""
        return service.edit(project_id,'script_build',{'manifest_path':manifest_path,'expected_manifest_sha256':expected_manifest_sha256},preview_only)


    @register(True)
    def sc2_script_inspect(project_id: str, symbol: str='') -> dict:
        """Galaxy 函数、声明、调用、初始化和字面空间引用；不宣称编译成功。"""
        return script.inspect_script(service.record(project_id)[1],symbol)


    @register(False)
    def sc2_script_replace(project_id: str, old: str, new: str, expected_sha256: str, preview_only: bool=False) -> dict:
        """唯一精确上下文替换，要求 SHA-256；保持结构、编码、换行和钥石保护。"""
        return service.edit(project_id,'script_replace',{'old':old,'new':new,'expected_sha256':expected_sha256},preview_only)


    @register(True)
    def sc2_script_triggers(project_id: str) -> dict:
        """只读检查图形 Triggers XML 的元素与引用结构。"""
        return script.inspect_triggers(service.record(project_id)[1])


    @register(True)
    def sc2_text_inspect(project_id: str, locale: str='zhCN') -> dict:
        """检查本地化键、重复、格式和卡名/描述配对；不会跨地区静默回退。"""
        return localization.inspect_localization(service.record(project_id)[1],locale)


    @register(False)
    def sc2_text_set(project_id: str, updates: dict[str,str], locale: str='zhCN', preview_only: bool=False) -> dict:
        """精确修改或追加本地化键值，保留原编码与换行。"""
        return service.edit(project_id,'localization_set',{'updates':updates,'locale':locale},preview_only)


    @register(False)
    def sc2_layout_replace(project_id: str, path: str, old: str, new: str, expected_sha256: str, preview_only: bool=False) -> dict:
        """精确修改 SC2Layout 上下文并核验 XML，不重排整个文档。"""
        return service.edit(project_id,'layout_replace',{'path':path,'old':old,'new':new,'expected_sha256':expected_sha256},preview_only)


    @register(True)
    def sc2_assets_search(project_id: str, query: str='') -> dict:
        """查询组件项目内的资源文件。"""
        return assets.inspect_assets(service.record(project_id)[1],query)


    @register(True)
    def sc2_assets_audit(project_id: str) -> dict:
        """按依赖路径检查 XML/Galaxy 字面资源引用；未解析的宏与模型二进制引用单列。"""
        roots,dep=service.roots(project_id)
        return {**assets.missing_asset_references(roots),'dependencies_complete':dep['complete']}


    @register(False)
    def sc2_assets_import(project_id: str, source: str, destination: str, overwrite: bool=False, preview_only: bool=False) -> dict:
        """把独立资源导入地图相对路径，自动备份并检查名称冲突。"""
        return service.edit(project_id,'asset_import',{'source':source,'destination':destination,'overwrite':overwrite},preview_only)


    @register(False)
    def sc2_assets_casc_extract(project_id: str, installation: str, paths: list[str], destination: str, product: str|None=None, branch: str|None=None) -> dict:
        """从指定本地 SC2 构建提取明确 CASC 虚拟路径到全新目录，不下载或修改安装。"""
        service.record(project_id)
        return service.jobs.submit('casc_extract',lambda cancel:casc.extract_casc(Path(installation),paths,Path(destination),product,branch,cancel=cancel))


    @register(False)
    def sc2_assets_migrate_mod(project_id: str, selections: list[dict[str,str]], template_project_id: str, destination: str|None=None, preview_only: bool=True) -> dict:
        """规划所选数据及本地引用闭包迁移至独立模组；缺失/未知依赖阻止成品写入。"""
        return service.migrate(project_id,selections,template_project_id,destination,preview_only)


    @register(True)
    def sc2_validate_static(project_id: str, background: bool=False) -> dict:
        """静态结构与依赖检查，分别记录编译/编辑器/运行/视觉未完成状态。"""
        if background: return service.jobs.submit('validate',lambda cancel:service.validate(project_id,cancel))
        return service.validate(project_id)


    @register(True)
    def sc2_validate_native_script_gate(project_id: str, manifest_path: str,
                                        native_root: str, installation: str,
                                        expected_editor_sha256: str,
                                        evidence_path: str|None=None) -> dict:
        """读取固定编辑器构建的独立 Galaxy 编译/重存证据，不启动程序。"""
        return service.native_script_gate(project_id,manifest_path,native_root,installation,
                                          expected_editor_sha256,evidence_path)


    @register(True)
    def sc2_validate_environment(installation: str) -> dict:
        """核对客户端、编辑器、地区构建、进程与日志，不启动程序。"""
        return editor.inspect_editor(Path(installation))


    @register(True)
    def sc2_validate_region_diagnose(installation: str, product: str|None=None, branch: str|None=None,
                                     locale: str='zhCN', map_path: str|None=None) -> dict:
        """只读诊断国服/亚服或国际服编辑器打不开的构建、注册表、地图语言和日志差异。"""
        return editor.diagnose_editor_region(Path(installation), product, branch, locale,
                                             Path(map_path) if map_path else None)


    @register(False)
    def sc2_validate_open_editor(project_id: str, installation: str, product: str='s2_cn', preflight: bool=True) -> dict:
        """先审计地图外壳再程序化打开；已知结构阻断时不启动。启动成功不等同载入验收。"""
        root=service.record(project_id)[1]
        shell=service.map_shell_audit(project_id,installation=installation,product=product)
        if preflight and shell['verdict']=='blocked':
            raise SC2Error('map_shell_blocked','地图外壳预检未通过，已阻止启动编辑器；先修复或提供同版本原生保存样本',audit=shell)
        result=editor.open_editor(root,Path(installation),product)
        result['map_shell']=shell
        return result


    @register(False)
    def sc2_validate_launch_test(project_id: str, installation: str, product: str='s2_cn') -> dict:
        """先生成独立已回读归档，再程序化启动游戏测试；不控制输入。"""
        destination=service.state/'test-runs'/uuid.uuid4().hex/'test.SC2Map'
        destination.parent.mkdir(parents=True)
        exported=service.export(project_id,str(destination))
        return {'export':exported,'launch':editor.launch_test(destination,Path(installation),product),'runtime':'not_verified'}


    @register(True)
    def sc2_validate_logs(path: str|None=None, limit: int=10, max_bytes: int=32768) -> dict:
        """列出或读取 SC2 专用日志，范围受限，敏感参数脱敏。"""
        return editor.read_log(Path(path),max_bytes) if path else {'logs':editor.log_files(limit)}


    @register(True)
    def sc2_validate_capture(pid: int, visible_frame: bool=False) -> dict:
        """只读捕获本服务启动的所属窗口；可能有 DirectX 黑/白帧，不自动算验收。"""
        output=service.state/'captures'/(uuid.uuid4().hex+'.png')
        output.parent.mkdir(parents=True,exist_ok=True)
        return editor.capture_visible_window(pid,output) if visible_frame else editor.capture_window(pid,output)


    @register(True)
    def sc2_validate_windows(pid: int) -> dict:
        """只读列出所属编辑器/游戏的主窗口与模态窗口，不发送窗口命令。"""
        return {'windows':editor.inspect_windows(pid)}


    @register(False)
    def sc2_validate_record(project_id: str, level: str, status: str, evidence_path: str, notes: str) -> dict:
        """登记调用方提供的编辑器/运行/视觉证据，绑定当前指纹并明确 caller_attested。"""
        return service.record_evidence(project_id,level,status,evidence_path,notes)


    @register(False)
    def sc2_changes_batch(project_id: str, edits: list[dict], preview_only: bool=False, experimental_write: bool=False, background: bool=True) -> dict:
        """单事务跨文件批处理。每项含 operation 和 parameters；类型见单项工具，可取消。"""
        fn=lambda cancel:service.edit(project_id,'batch',{'edits':edits},preview_only,experimental_write,cancel)
        return service.jobs.submit('batch',fn) if background else fn(None)


    @register(False)
    def sc2_dependencies_prepare(project_id: str, installation: str|None=None, locale: str|None=None, product: str|None=None, branch: str|None=None, background: bool=True) -> dict:
        """固定递归依赖、物化来源与构建指纹；缺失来源保持不完整，不改依赖声明。"""
        fn=lambda cancel:service.prepare_dependencies(project_id,installation,locale,product,branch)
        return service.jobs.submit('dependencies_prepare',fn) if background else fn(None)


    @register(True)
    def sc2_catalog_explain(project_id: str, catalog: str, object_id: str, fields: list[str]|None=None, source_context_id: str|None=None, observations: dict|None=None) -> dict:
        """分别解释静态值、逐层来源、未知规则和有证据绑定的实测对照。"""
        return service.explain_catalog(project_id,catalog,object_id,fields,source_context_id,observations)


    @register(True)
    def sc2_catalog_schema() -> dict:
        """返回当前已证实的 Catalog 类型、字段和数组规则；未知语义保持 unknown。"""
        from .catalog import _CATALOGS
        from .catalog_rules import rule_profile
        return {'schema':'sc2-catalog-schema/1','catalogs':list(_CATALOGS),
                'rules':rule_profile(),
                'unknown_semantics':['原生默认值','未索引数组追加顺序','动态表达式和宏','引擎最终合并值'],
                'write_policy':'未知字段、对象类型、数组索引或合并语义必须拒绝候选'}


    @register(False)
    def sc2_catalog_patch(project_id: str, operations: list[dict], source_context_id: str|None=None) -> dict:
        """按已支持字段与明确数组索引生成事务候选；未知合并规则拒绝。"""
        return service.prepare_catalog_patch(project_id,operations,source_context_id)


    @register(True)
    def sc2_official_assets_search(project_id: str, query: str='', catalog: str|None=None, component: str|None=None, offset: int=0, limit: int=30) -> dict:
        """搜索随包官方皮肤/模型/Actor/声音等知识快照，支持中文名；不是地图当前合并Catalog。"""
        context=service.prepare_dependencies(project_id)
        from .official_assets import search
        return search(query,catalog,component,offset,limit,context)


    @register(True)
    def sc2_official_assets_explain(project_id: str, catalog: str, object_id: str, component: str|None=None) -> dict:
        """解释官方对象声明、Skin模板参数、替换/EffectArray和模型路径；未知与实机层级单独报告。"""
        context=service.prepare_dependencies(project_id)
        from .official_assets import explain
        return explain(catalog,object_id,component,context)


    @register(True)
    def sc2_official_assets_audit(project_id: str, catalog: str, object_id: str,
                                  component: str|None=None, installation: str|None=None,
                                  locale: str|None=None, product: str|None=None,
                                  branch: str|None=None,
                                  source_context_id: str|None=None) -> dict:
        """分层核对官方对象知识、地图依赖和本机构建资源可读性。"""
        return service.official_asset_audit(project_id,catalog,object_id,component,
                                            installation,locale,product,branch,
                                            source_context_id)


    @register(True)
    def sc2_assets_model_inspect(project_id: str, reference: str|None=None, model_id: str|None=None, source_context_id: str|None=None, sources: list[str]|None=None, background: bool=True) -> dict:
        """只读检查M3/M3A动画、挂点、材质与外部引用；不修改模型。"""
        if (reference is None)==(model_id is None):raise SC2Error('invalid_model_request','请明确提供reference或model_id之一')
        fn=lambda cancel:service.resolve_model_assets(project_id,reference,model_id,source_context_id,sources,cancel)
        return service.jobs.submit('model_inspect',fn) if background else fn(None)


    @register(True)
    def sc2_assets_resolve(project_id: str, references: list[str], source_context_id: str|None=None, sources: list[str]|None=None, background: bool=True) -> dict:
        """按统一来源解析资源闭包，缺失和未支持结构保留unknown。"""
        fn=lambda cancel:service.resolve_model_assets(project_id,None,None,source_context_id,sources,cancel,references)
        return service.jobs.submit('assets_resolve',fn) if background else fn(None)


    @register(True)
    def sc2_unit_variant_audit(project_id: str, base_unit: str|None=None, new_id: str|None=None, visual_source: str='MarineWarfield', allowed_gameplay_differences: list[str]|None=None, source_context_id: str|None=None, named_workflow: str|None=None) -> dict:
        """审计单位变体；named_workflow=secret_hangar可单独审计秘密机库生产/挂件/弃牌链，无需base/new ID。"""
        if named_workflow is not None:
            return service.audit_named_unit_workflow(project_id,named_workflow,source_context_id)
        from .unit_variant import audit_unit_variant
        context=service.source_context(project_id,source_context_id) if source_context_id else service.prepare_dependencies(project_id)
        result=audit_unit_variant([Path(p) for p in context['roots']],base_unit,new_id,visual_source,allowed_gameplay_differences=allowed_gameplay_differences)
        result['source_context_id']=context['source_context_id'];result['dependencies_complete']=context['complete']
        return result


    @register(False)
    def sc2_unit_variant_plan(project_id: str, base_unit: str, new_id: str, visual_source: str='MarineWarfield', allowed_gameplay_differences: list[str]|None=None, source_context_id: str|None=None) -> dict:
        """受限Marauder/Warfield模板生成完整事务候选，公共伤害链不重复升级。"""
        from .unit_variant import plan_unit_variant
        return service.prepare_domain(project_id,'unit_variant',lambda root,roots,context:plan_unit_variant(root,roots,base_unit,new_id,visual_source,allowed_gameplay_differences),source_context_id)


    @register(True)
    def sc2_keystone_card_inspect(project_id: str, card_id: int|None=None, name: str|None=None) -> dict:
        """读取真实卡牌ID、费用、注册单位和静态效果调用链。"""
        return service.keystone_inspect(project_id,'card',{'card_id':card_id,'name':name})


    @register(False)
    def sc2_keystone_card_cost(project_id: str, card_id: int, mineral: int, gas: int, source_context_id: str|None=None) -> dict:
        """精确修改矿气与已识别的双悬停预览，生成事务候选。"""
        return service.prepare_keystone(project_id,'card_cost',{'card_id':card_id,'mineral':mineral,'gas':gas},source_context_id)


    @register(True)
    def sc2_keystone_descriptions(project_id: str, card_ids: list[int]|None=None, source_context_id: str|None=None) -> dict:
        """组合自动介绍与手写描述并提示重复；不自动改写语义不明卡效。"""
        return service.keystone_inspect(project_id,'descriptions',{'card_ids':card_ids},source_context_id)


    @register(True)
    def sc2_keystone_news_inspect(project_id: str, category: str='global') -> dict:
        """读取指定分类的真实页序、日期键和历史正文。"""
        return service.keystone_inspect(project_id,'news',{'category':category})


    @register(False)
    def sc2_keystone_news_update(project_id: str, category: str, date: str, body: str, source_context_id: str|None=None) -> dict:
        """按分类新增日期首页或补充同日正文，保留历史和其他分类，生成候选。"""
        return service.prepare_keystone(project_id,'news',{'category':category,'date':date,'body':body},source_context_id)


    @register(True)
    def sc2_keystone_portraits_inspect(project_id: str) -> dict:
        """读取稳定saveID、头像容量和分页；玩家可见页数保持未知。"""
        return service.keystone_inspect(project_id,'portraits')


    @register(False)
    def sc2_keystone_portrait_import(project_id: str, image_path: str, save_id: int|None=None, nemesis_unlock_id: int=-1, backer_exclusive: bool=False, support_months_required: int=0, standard_wins_required: int=0, source_context_id: str|None=None) -> dict:
        """解码源图片并裁切为152px DXT5头像；仅追加新稳定ID的事务候选。"""
        from .storage import guard_absolute_path
        path=guard_absolute_path(Path(image_path))
        if not path.is_file() or path.stat().st_size>64*1024*1024:raise SC2Error('keystone_image_invalid','源图片不存在或超过64MiB')
        raw=path.read_bytes()
        if len(raw)>64*1024*1024:raise SC2Error('keystone_image_invalid','源图片超过64MiB')
        return service.prepare_keystone(project_id,'portrait',{'image':raw,'save_id':save_id,'nemesis_unlock_id':nemesis_unlock_id,'backer_exclusive':backer_exclusive,'support_months_required':support_months_required,'standard_wins_required':standard_wins_required},source_context_id)


    @register(False)
    def sc2_changes_prepare(project_id: str, patches: list[dict], source_context_id: str|None=None) -> dict:
        """导入相对路径/基准及候选 SHA-256 明确的隔离补丁，仍由统一事务提交。"""
        return service.prepare_changes(project_id,patches,source_context_id)


    @register(False)
    def sc2_probe_prepare(project_id: str, template: str, parameters: dict, source_context_id: str|None=None, change_id: str|None=None, assertions: list[dict]|None=None) -> dict:
        """固定模板建立独立测试副本和唯一银行；不运行生产初始化，不接受任意Galaxy。"""
        return service.prepare_probe(project_id,template,parameters,source_context_id,change_id,assertions)


    @register(False)
    def sc2_probe_run(probe_id: str, installation: str, product: str='s2_cn', startup_timeout: int=120, probe_timeout: int=120) -> dict:
        """后台串行运行诊断；已有客户端阻塞，超时/中断保留partial，仅终止核实归属的测试进程。"""
        return service.jobs.submit('probe_run',lambda cancel:service.probes.run(probe_id,installation,product,startup_timeout,probe_timeout,cancel))


    @register(True)
    def sc2_probe_result(probe_id: str|None=None, historical_bank_path: str|None=None, assertions: list[dict]|None=None) -> dict:
        """重启后回收绑定原始Bank/阶段/断言；历史归档明确unbound，未采集数据不补零。"""
        return service.probe_result(probe_id,historical_bank_path,assertions)


    @register(True)
    def sc2_changes_inspect(project_id: str, change_id: str) -> dict:
        """读取项目对应修改记录、差异、备份、候选和验证结果。"""
        _,root=service.record(project_id)
        item=service.transactions.read(change_id)
        if Path(item['root']).resolve()!=root.resolve(): raise SC2Error('project_mismatch','记录不属于此项目')
        return service.transactions.describe(item)


    @register(False)
    def sc2_changes_apply(project_id: str, change_id: str, experimental_write: bool=False) -> dict:
        """重新校验并提交候选；地形仅独立测试图可显式experimental_write，正式图拒绝。"""
        return service.apply_candidate(project_id,change_id,experimental_write)


    @register(False)
    def sc2_changes_rollback(project_id: str, change_id: str) -> dict:
        """回滚到备份；检测后续人工修改并拒绝覆盖。"""
        _,root=service.record(project_id,True)
        if service.editor_conflict(): raise SC2Error('editor_unsaved_state_unknown','编辑器运行期间不能回滚')
        return service.transactions.rollback(change_id,root)


    @register(False)
    def sc2_changes_recover(project_id: str) -> dict:
        """从未完成事务日志恢复；检测冲突并保留人工新修改。"""
        _,root=service.record(project_id,True)
        if service.editor_conflict(): raise SC2Error('editor_unsaved_state_unknown','编辑器运行期间不能恢复')
        return {'recovered':service.transactions.recover(root)}


    @register(True)
    def sc2_job_status(job_id: str) -> dict:
        """查询长任务进度、结果、失败或中断状态。"""
        return service.jobs.status(job_id)


    @register(False)
    def sc2_job_cancel(job_id: str) -> dict:
        """请求取消长任务；事务在安全检查点恢复，不伪装即时取消。"""
        return service.jobs.cancel(job_id)


    @register(True)
    def sc2_report_read(name: str, offset: int=0, limit: int=24000) -> dict:
        """分段读取此服务生成的大型 JSON 报告。name 使用工具返回的 report_name。"""
        if not 0<=offset or not 1<=limit<=100000: raise SC2Error('invalid_range','报告范围无效')
        value=safe_path(service.state/'reports',name).read_text('utf-8')
        return {'text':value[offset:offset+limit],'next_offset':offset+limit if offset+limit<len(value) else None}


    @register(True)
    def sc2_artifact_image(path: str) -> dict:
        """将本服务生成的预览/截图作为原生 MCP 图片返回，供 AI 查看。"""
        requested=Path(path).resolve()
        if not requested.is_relative_to(service.state) or requested.suffix.lower()!='.png':
            raise SC2Error('artifact_path', 'Only generated PNG artifacts may be read')
        source=safe_path(service.state,requested.relative_to(service.state).as_posix())
        if not source.is_file() or source.stat().st_size>20_000_000:
            raise SC2Error('artifact_size', 'Image missing or larger than 20 MB')
        return {'path': str(source), 'format': 'png'}


    return operations
