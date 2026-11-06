---
name: sc2-unit-portrait
description: 选择或改造 SC2 单位肖像的现有模型与静态回退图，检查身份、取景、灯光及 PortraitModel/PortraitActor 接线。
---

# 单位肖像

1. 从目标 Unit 找到单位 Actor，分别记录 PortraitModel、PortraitActor 及其有效来源。查询前者的 Model 数据；后者按实际 Actor 类型解析，继续查其引用。
2. 记录 M3、静态 Image、Lighting、父级、面部控制及依赖。镜头和动画名称从实际资源或预览读取。参考[静态样本](references/portraits.md)及[共享接线案例](../sc2-art/references/score-actor-cases.json)选材。
3. 保留识别特征并调整取景。人形关注眼位、面罩和肩甲；机械关注驾驶舱、传感器和前部轮廓；虫族关注口器、冠甲和甲壳；孵化体关注囊体和外壳。按实际主体选择裁切。[四组单位与肖像对照](../sc2-art/references/editor-preview-observations.md)展示如何在不同取景中保留身份结构，选材时说明借用的具体部件与明暗关系。
4. 分别检查动态肖像和静态回退图。核对灯光是否保留脸部或主结构暗面、发光点是否抢占身份特征、背景是否分离。动态预览还需检查待机、说话等实际使用动画。
5. 修改与导入沿 [Actor 系统](../sc2-actor-system/SKILL.md) 和 [共享素材入口](../sc2-shared-tools/SKILL.md)。提交前保留原资源哈希，回读实际 DDS，并核对同名覆盖。

静态图片能提供构图与材质依据。动态镜头、动画、灯光及回退生效需对应预览或运行证据。交付列出对象链、采用的参考、图像对照、未解析依赖与观察范围。
