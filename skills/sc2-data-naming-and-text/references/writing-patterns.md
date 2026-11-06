# 文本用途与来源案例

这些案例读取 zhCN 的本地声明及字符串，需在目标项目查询实际消费字段与继承值。原始标签和动态引用保存在[案例记录](score-cases.json)。

| 用途 | 来源对象 | 观察与写法 |
|---|---|---|
| 招募 | SCORE-Purifier.SC2Mod / Button/AdeptP | 招募名使用动作词和兵种名，说明定位、主要能力与攻击目标。 |
| 主动技能 | SCORE-Golden.SC2Mod / Button/ActivateStasisWardG | 技能说明包含作用、持续时间和限制，保留原动态引用。 |
| 被动 | SCORE-Umojan.SC2Mod / Button/AD20U | 被动名强调机制，说明触发或资源消耗关系。 |
| 升级 | SCORE-Moebius.SC2Mod / Button/AblativeScalesM | 升级名指向获得的改进，说明受影响单位与变化。 |
| 正面状态 | SCORE-Purifier.SC2Mod / Behavior/ChargingBarrierP | 状态写当前得到的保护，目标数值以有效行为为准。 |
| 负面状态 | SCORE-Primal.SC2Mod / Behavior/CoopMurvarPukePuddleDisablePZ | 负面状态同时交代速度和主动能力限制。 |
| 叠层状态 | SCORE-Webby.SC2Mod / Behavior/DefilerPlagueW | 该行为有本地叠层字段，原 Tooltip 只说持续伤害；先核对叠层规则和 UI 可见性再补草案。 |
| 内部辅助对象 | SCORE-Ihanrii.SC2Mod / Behavior/AdeptDeathCheckI | 该本地辅助行为缺少玩家 Name/Tooltip，先检查可见标志和消费面。 |

## 草案写法

按目标数据填写方括号，再保留项目需要的标记。

- 招募按钮名“训练[兵种]”，说明“[战术定位]。可使用[主要能力]。[攻击目标]。”
- 主动技能“对[目标]施加[作用]，持续[已核对的时间]。[限制]。”
- 被动“[触发条件]时，[主体]获得[作用]。”
- 升级“使[单位]的[属性]提高[已核对的变化量]。”
- 正面状态“该单位获得[保护或属性变化]。”
- 负面状态“该单位[受到的限制]，持续[已核对的时间]。”
- 叠层状态“每层[作用]，[按有效规则叠加或刷新]。”本案例未核实有效上限，保留待填项。
- 内部辅助对象用“[系统] - [用途]”作为编辑器草案，依目标项目补齐前后缀。

## 问题案例

LoadNearbyO 的“将单位装载进。”缺少目的对象，需从技能和运输容器数据核对。NetEaseShieldO 的 163 点描述可能易被误读，需对照伤害响应规则再决定文字。案例中混合语言、缺失键、编辑器包标记和玩家名称分别记录。

## 格式回查

ActivateStasisWardG 的持续时间包含动态 Behavior 引用，核对目标对象与 Duration 字段后保留。AdeptP 的名称带颜色标签，修改时保留标记配对和原换行。AdeptDeathCheckI 的缺失玩家文本先查显示用途，不能仅据缺失键补一段玩家说明。
