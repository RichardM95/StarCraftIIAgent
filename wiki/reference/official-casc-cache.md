# CASC 官方依赖缓存

入口为 [sc2-official-cache.py](../../tools/sc2-official-cache.py)。CASC 只在显式 `probe` / `sync` 中打开；依赖、GUI、Catalog 和预检只消费已发布缓存，不加载 DLL、不自动提取或联网。命令不改写项目配置、游戏或模组。

## 诊断与同步

安装目录默认取当前配置，DLL 必须显式传入。另一个安装使用 `--sc2-install-dir`，并为其目标指定实际 `--mods-dir`。

```text
python tools/sc2-official-cache.py probe --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py sync --target "<Components>" --casc-dll "<CascLib.dll>"
python tools/sc2-official-cache.py sync --target "<Components>" --casc-dll "<CascLib.dll>" --apply
```

`probe` 输出安装布局、唯一活动构建、DLL 位数/指纹、接口、字符集尝试及 XML 样本的诊断 JSON。`read_verified` 要求存储打开、元数据和定义文件完整读取并可解析，不表示依赖完整。原生调用在独立子进程中执行，单次请求默认超时 60 秒，可用 `--timeout` 调整；异常、超时和崩溃成为诊断，句柄由子进程关闭/回收。

`sync` 默认仅在内存中预览，不创建缓存。必要元数据、注册定义或引用文件缺失时返回 `partial`；`--apply` 仍拒绝发布。可选语言文件不可读时记入 `unavailable_files`，不补造文字。JSON 的 `applied` 才表示实际发布。

默认目录为套件旁 `StarCraftIIAgent-data/reference/casc/<安装标识>/<构建键>/`，`--official-cache` 可指定根目录。保留 Mods/Campaigns 逻辑结构，路径统一小写，文件保留原始字节，清单记录实际 CASC 名称、安装/构建、DLL 指纹、文件哈希、语言可用性和登记证据。内容限于组件/依赖元数据、GUI 登记及库、Galaxy 定义、GameData XML 与 zhCN/enUS 本地化；地图、模型、贴图、声音和过场不在范围内。

发布前核对路径边界、构建身份、文件哈希、XML、库登记和 GameData 引用闭包，复用暂存/目录切换机制。失败保留当前缓存；已有目录必须是同安装/构建的缓存。禁止把缓存设在套件、游戏或两者的祖先目录。不跨安装或构建混用缓存。

## 加载证据与边界

优先读取真实 ComponentList 定位的 info 文件；没有清单时只使用确实存在的 DocumentInfo。不修造官方组件清单。已有但损坏的本地组件继续报错；只有本地不存在且缓存中精确匹配的引用才使用官方来源。纯网络引用、缺失自定义依赖、名称相似的组件不自动映射。

部分官方组件的战役父关系位于引擎内置表。[sc2_engine_dependencies.py](../../tools/sc2_engine_dependencies.py) 只支持已经核对的本机 x64 引擎 SHA-256，读取固定边界并校验 PE 指针、父节点顺序和多人堆叠表，不执行引擎。未知指纹停止使用该来源。来源包括引擎路径、指纹、版本、表和行偏移，它不等同于官方 XML。结构来源为 [archive-system](https://github.com/sc2-arcade-watcher/sc2-file-format-docs/blob/main/archive-system.md#locale-dependency-chains)；实现参考为用户工具箱的 `utils/data/builtin_dependencies.py`，运行本工具无需依赖工具箱代码。

目前内置表不能证明 Core 的隐式加载。使用该来源的同步仍返回 `partial` 并阻止发布，不能由 Liberty 的空父列表推断完整根集合，也不能无条件注入 Core。需要同构建的 bootstrap 加载证据才能解除阻碍。Core 的 LibraryList 与 NativeLib 可以证明 Ntve 的归属，不能单独证明目标加载了 Core。

基础 DLL ABI 按 [CascLib 原始接口](https://github.com/ladislav-zezula/CascLib/blob/master/src/CascLib.h) 核对；只用本地存储、枚举、读取和严格数据检查，不用扩展参数结构、在线打开或加密内容零填充选项。错误码 2 只作为具体调用诊断，不能据此判定游戏损坏。

## 共用查询与新鲜度

`init-project.py`、`inspect-mod-dependencies.py`、`validate-agent-config.py`、`sc2-trigger-query.py`、`build-sc2-catalog-graph.py`、`sc2-catalog-query.py`、`test-suite.py` 均支持 `--official-cache`。未传时只读定位目标 Mods 所属安装的匹配构建；缓存缺失继续报告依赖缺口，显式缓存不合法则失败。

```text
python tools/inspect-mod-dependencies.py --official-cache "<缓存根>"
python tools/sc2-trigger-query.py --official-cache "<缓存根>" libraries
python tools/sc2-trigger-query.py --official-cache "<缓存根>" check
python tools/build-sc2-catalog-graph.py --official-cache "<缓存根>" --locale zhCN --sqlite-only
python tools/sc2-catalog-query.py --official-cache "<同一缓存根>" stats
python tools/test-suite.py --scope mod --official-cache "<缓存根>"
```

GUI 保留库归属、参数、冲突和加载链检查，输出 `origin` / `casc` 来源。缓存中存在不等于目标已加载。参考索引不成为活动依赖。

Catalog 保留 `local_mod`、`active_component_dependency`、`reference_export` 分类和本地覆盖，官方定义附加 CASC 清单、构建和路径。本地化由构建时 `--locale enUS|zhCN` 选择，默认 enUS，不跨语言补值，节点保留来源。官方 GameData 从真实入口递归处理 Includes/Catalog 引用；本地扫描范围不变，TXT 导出仍只是参考。

Catalog 输入清单现为版本 4，旧索引需重建；缓存清单、库存、活动构建信息、语言选择进入新鲜度检查。查询另传缓存须与索引选择相同。历史读取许可与部分依赖调查许可仍然独立。官方缓存核对哈希/XML/登记，不套用手写模组的编码和 Galaxy 风格限制。统一预检默认仍只检查主模组；显式扫描依赖也不会对官方缓存执行手写代码 linter。

## 本机证据范围

2026-10-21，SC2 `5.0.17.98370`、构建 `bb10ee62e9cf3678dfa74233d5657757`：原工具箱 x64 DLL 可用 ANSI 接口打开本地存储并读到 Core 库登记和 NativeLib，不需要替代 DLL。沙箱内首次打开曾返回 2，放开本次只读访问后成功，不能归因为客户端损坏。

Heros 只读预览从引擎表展开 Liberty/Swarm/Void Mod 与三层战役共六个组件，读取 812 份文件、52,589,275 字节；21 份语言文件登记存在但本地不可读。结果为 `partial`：Core/bootstrap 证据不足。没有发布完整官方缓存，因此真实目标的依赖、GUI 和 Catalog 完整性仍不能通过。回归使用独立且有 XML 证据的组件夹具验证发布和消费流程，不能替代本机完整性验收。
