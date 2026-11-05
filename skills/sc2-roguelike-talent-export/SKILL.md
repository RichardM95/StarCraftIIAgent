---
name: sc2-roguelike-talent-export
description: 分析并导出当前或指定 SC2 肉鸽模组的天赋列表为双语 Excel，适配 UserData 表、GUI 常量数组和逐条注册，根据选择界面显示品质，并计算说明中的基础数值。
---

# 肉鸽天赋清单导出

用户要求整理、导出或比较天赋列表时使用。先运行探测，再确认项目字段角色。需要核对实际效果或平衡时加载 [SC2肉鸽机制专用技能](../sc2-roguelike-mechanics/SKILL.md)。

从工作区运行以下命令。省略 `--mod` 使用已选项目，显式路径只影响本次读取。命令支持 Components 与工作区内置 MPQ 读取器。

```powershell
python tools/sc2_talent_export.py inspect --ui-language zh-CN
python tools/sc2_talent_export.py export --ui-language zh-CN
```

探测列出候选表、字段类型、实例样本、GUI 定义入口和语言。单个明确 UserData 候选可自动生成初始映射，其他结构依 [适配格式](references/mapping.md) 写项目映射，再用 `--mapping` 指定。探测本身只读。

## 适配与导出

1. 核对名称原始字符串与本地化名称键、说明键、品质原值、类型、职业、上限、升级和图标各对应哪个字段。用项目 GUI 或文本确认品质标签，映射中记录证据。多个候选表时用样本差异决定，歧义无法消除再询问用户。
2. 从天赋选择界面的品质控件追到 GUI Switch。将品质分支和按类型显示的例外写入项目映射的 `rarity_gui`。导出时沿实际 case 读取返回值或设置对话框文本动作的中文参数，更新标签和来源。
3. 核对字段默认值及职业、兵种和前置条件。触发器型项目按函数与参数 ID 绑定静态数组或注册入口。遇到动态索引、计算值或无法证实的获取路径时保留取证缺口。
4. 玩家描述中的 `<d ref>` 从当前加载的有效 Catalog 取基础值，支持嵌套字段、数组索引、括号和四则运算；按 precision 显示，单位沿用原文。读取失败时仅替换当前数值，摘要中记录天赋、语言、原始标签和原因。清除颜色和样式标记，将游戏换行转换为 Excel 换行。
5. 工作簿只含「天赋清单」，以中文名称、品质和效果开头，双语说明及 ID 可用于对照。默认项与确认禁用项从清单过滤。文件位于项目 `.agent/runtime/reports/rogue-talents.xlsx`，可用 `--output` 指定位置。摘要在同目录的 `rogue-talents.summary.json`，项目映射在 `docs/implementation/talent-export-mapping.json`。

回读工作簿并核对表名、玩家行数、品质例外、中英文引用成功数与未解析数。额外升级、在场单位和玩家存档可能改变实际数值，游戏效果验证转入机制技能。
