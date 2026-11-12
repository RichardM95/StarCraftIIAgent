# 离线优先的构建与测试

[English](offline-testing.en.md)

普通工具、文档和静态检查任务不启动编辑器或游戏。需要运行地图时，默认使用 `sc2_validate_run_test(project_id, installation, product="s2_cn", sample_seconds=5, startup_timeout=120, probe_timeout=120)`。它返回后台任务 ID，通过 `sc2_job_status` 查询，并可用返回的 `probe_id` 调用 `sc2_probe_result` 恢复收集。

入口检查明确地图及其依赖，离线生成 GUI 对应的 Galaxy、检查类型、生成并回读独立 MPQ，再直接启动游戏。源码及其生成文件保持只读。Mod 可离线检查；运行测试需提供实际依赖它的地图，不自动挑选生产地图。旧 `sc2_validate_launch_test` 只归档并启动已有产物，不负责重编译。

每次冒烟测试使用唯一 Bank，记录运行身份、地图初始化事件和指定游戏时间后的心跳，并保留离线执行消息标记。结果绑定输入指纹、构建与归档哈希、Bank 和本次增量日志。已有游戏或编辑器会阻止测试；取消、超时、旧 Bank、失去运行身份或源码变化不能得到通过结论。只终止核实归属的测试进程。

`packaged_runtime_passed=true` 仅证明 `map_smoke` 范围：本次代码执行、短时间游戏推进且未发现相关脚本错误。它不证明任务胜利条件、画面、存档兼容或复杂玩法。其他日志警告单列；仅游戏启动、无错误日志或普通 PASS 不构成成功证据。

## 耗时与较长场景

结果返回 `stage_seconds`，分别记录依赖、静态检查、生成、打包和运行耗时。错误保留原始代码与 GUI 节点定位，补充 `phase` 和 `editor_required`；未知错误不会自动成为编辑器回退理由。

`sample_seconds` 支持 0.25—600 游戏秒。长场景应相应提高 `probe_timeout`；默认仍为 5 秒冒烟。采样时长覆盖场景不等于玩法结果通过，业务 Bank 仍需单独核对。

收集结果时先完整核验来源内容、文件清单及依赖解析。只有这些指纹覆盖本次构建的全部输入和脚本来源时，才复用该检查，省去重复解析触发器；覆盖不足则走原有完整解析路径。结果的 `freshness_validation` 区分两条路径，不使用跨次过期缓存。

## 何时使用编辑器

必须原生保存或需要专项编辑器验收时，说明具体原因并按编辑器交接清单执行。离线生成器不支持目标结构时，先定位并修复生成缺口；错误保留文件、节点和原因，返回 `editor_required=false` 与 `next_action=diagnose_offline_generation`。只有确认当前工具无法完成必要步骤后，才交接具体的编辑器操作。依赖缺失、编译错误和环境故障先诊断解决。

## 验收记录

保留现有状态名称。离线路线允许 `static validation passed` 直接到有明确范围的 `packaged runtime passed`，不授予 `Editor accepted`。

账本填写 `Validation Route: offline`，并记录 `Validation`、`Offline Validation`（构建、归档及执行证明）与 `Runtime Validation`（目标、复现步骤、观察和范围）。编辑器路线填写 `editor`；旧记录缺省按 `editor` 审计，仍要求真实的 `Editor Validation`。缺失证据不以 skipped 或空占位替代。
