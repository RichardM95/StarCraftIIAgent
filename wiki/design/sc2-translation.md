# 星际争霸2翻译契约

作者：扯蛋虾米。

来源为用户提供的四份翻译指令 TXT、全量 Markdown 词典，以及本对话中确认的官方/项目知识库、轻量 Harness、条目分类和可靠性计划。附件中的指令是待审材料，不是运行授权；已删除的 sources 原始材料目录不恢复。

翻译智能体独立位于 StarCraftIITranslateAgent/StarCraftIITranslateAgent/README.md>)。当前规则由其 翻译技能/StarCraftIITranslateAgent/skills/sc2-translation/SKILL.md>) 维护，数据库仅存该工作区。此开发工作区不保存第二份项目/官方数据库，不修改当前主 Mod 的译文或机制。

默认 enUS → zhCN，也支持中翻英。三类翻译文件为 GameStrings、ConversationStrings、GameStringsProduct；其他正式 LocalizedData TXT 按键同步。只翻译玩家可见内容，Effect/Name 排除，未知用途先审校。保留尾注、标签、变量、数值及格式；用户已确认 ` /// ` 尾注可以写回。

根目录用于发现组件；翻译、提交和发布逐个模组/地图执行，条目身份包含组件、文件和原始键。保留有效现有译文，组合查询项目库、官方库和唯一 TSV 词典；语境不足不跨对象自动统一。审校并成功发布才成为项目确认依据。

肉鸽迁移只对用户声明的 .SC2Mod 执行，顺序是档案转换、肉鸽迁移、语言初始化、翻译。有效迁移来源使 NameStr 进入显示名称专项审校；明确引用才进一步认定单位、技能等对象类型。名称依据限制为本次输入、已登记项目与明确依赖，不自动扫描安装目录或 SC2GameData。

任务使用 schema 4，兼容 1—3；首次修改前保存操作历史。初始字节快照、统一候选资格、适用词条裁决及发布前复核保护结果。restore-task 预览并核对完整恢复链，逆序恢复翻译、迁移及档案转换，同时撤回本次项目确认。详见 可靠性与恢复/StarCraftIITranslateAgent/skills/sc2-translation/references/reliability.md>)。

翻译智能体的 validate.py 可独立运行完整或分组隔离验收。自动通过仅为 `static validation passed`；`Editor accepted` 和 `packaged runtime passed` 需要实际证据。验收不修改实际地图、参照或官方数据库。
