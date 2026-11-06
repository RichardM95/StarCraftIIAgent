# SCORE 外观回查与预览交接

案例声明与来源见[清单](score-actor-cases.json)。用户已提供四组单位与肖像的八张预览截图，[观察页](editor-preview-observations.md)记录可见结构、制作参考与证据范围。对象对应关系采用用户给出的顺序；截图未显示资源 ID、构建、镜头与灯光参数。

| 需求 | 应查询的链与回查结果 | 下一步证据 |
|---|---|---|
| 单位配色变体 | 原模型的贴图槽、Actor 材质替换事件和目标队伍色需一起查，分包名只用于选参考。 | 同视角近景与单位群截图。 |
| 模型替换 | 四组原始单位的静帧可用于选材。省略 Model 的条目仍需查父级与类默认。 | 替换候选的同视角对照、实际动画及纹理；原始预览不能证明替换成功。 |
| 动态肖像 | 逐项区分 PortraitModel 和 PortraitActor。四组肖像静帧已观察。 | 动画、镜头变化和灯光参数尚未观察，需在对应资源中核实。 |
| 静态回退 | 15 张可读静态图已解码并保存无损 PNG，核对 Image 的来源和依赖。 | 目标设置下实际回退显示。 |
| 形态切换 | 核对形态对应 Unit/Actor、模型和继承事件，来源中的 Morph 名称不能单独证明生效。 | 两种形态、切换过程与旧模型销毁。 |

## 四组编辑器预览

下表保留数据中的本地声明，用于与用户提供的单位及肖像预览配对。截图、哈希、尺寸及观察说明见[预览记录](editor-preview-observations.json)。声明与画面分别保留依据，未从裁切截图反推实际加载的完整资源链。

| 来源包 | 单位／Actor ID | 本地 PortraitModel | 本地 PortraitActor |
|---|---|---|---|
| SCORE-CovertOps.SC2Mod | FirebatC | FirebatPortraitC | 需查继承 |
| SCORE-Ihanrii.SC2Mod | DragoonI | DragoonPortraitI | 需查继承 |
| SCORE-Webby.SC2Mod | HydraliskW | HydraliskPortraitW | 需查继承 |
| SCORE-Primal.SC2Mod | HydraliskPZ | Hydralisk_Primal_Collection_Portrait | 需查继承 |

后续实际改造时记录模型 ID、资源、可见状态、镜头和照明。缺纹理与未解析依赖分别记录具体症状。当前八张图是用户操作的预览证据，仅支持所见静帧的美术观察；不据此记录项目保存验收或游戏运行通过。
