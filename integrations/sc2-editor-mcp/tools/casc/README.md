# 本地 CASC 后端

在工程根目录运行 `dotnet build tools/casc/Sc2Casc.csproj -c Release`，需要 .NET SDK 6；执行需要 .NET Runtime 6。没有 NuGet 包和其他工程运行时依赖。Python 接口是 `sc2_mcp.casc.extract_casc`，helper 只接受独立 JSON 请求文件。

CASCLib 1.0.23 的本地选择器按 Product 字段匹配，当前多地区 SC2 的 `.build.info` Product 可以为空，直接传 `s2` 会失败或选错版本。此适配器验证 Python 选定的活动 BuildKey，以该行的本地构建/CDN配置建立内存 CASCConfig，保留安装文件原样。CN 启动产品 `s2_cn` 与构建 UID `s2c` 分别记录，二者不是同一字段。访问其私有配置字段与固定版本绑定，升级 vendor 必须重测。

所有数据来自本地。CASCLib 在本地数据缺失时会尝试 HTTP 回退，此适配器把**内存配置**中的 CDN 主机改成无效 IPv6 主机并自检 URI 解析拒绝，保证该回退在网络请求构造前失败。源配置文件不变。缺失数据返回失败，不自动下载。

vendor/provenance.json 记录二进制本地来源、版本、SHA-256 和上游链接。复制来源不是上游构建可复现证据；正式对外分发前需按上游许可证保留相应声明。当前仅用于本机独立开发。
