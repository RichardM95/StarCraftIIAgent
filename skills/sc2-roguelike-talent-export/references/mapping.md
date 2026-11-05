# 项目映射格式

`inspect` 给出项目绝对路径和结构指纹，填入下面的 `project` 和 `structure_fingerprint`。显式 `--mapping` 路径不存在时应先创建，映射为 JSON。

```json
{
  "version": 1,
  "project": "E:/SC2/Mods/Example.SC2Mod",
  "structure_fingerprint": "由 inspect 取得",
  "tables": [
    {
      "id": "Talents",
      "roles": {
        "name": "Name",
        "name_key": "NameStr",
        "description": "Description",
        "rarity": "Rarity",
        "category": "Type",
        "class": "Class",
        "max": "Max",
        "upgrade": "Upgrade",
        "icon": "Image",
        "banned": "Banned",
        "requirement": "Requirement"
      },
      "default_ids": ["[Default]"]
    }
  ],
  "relations": [
    {"role": "class", "table": "Classes", "field": "$id"}
  ],
  "rarity_labels": {
    "1": {"label": "普通", "evidence": "Triggers 的具体库、条件和文本参数 ID"}
  },
  "triggers": [],
  "merge_on": "upgrade"
}
```

`roles` 左侧是导出角色，右侧是本项目字段 ID。原始字段供适配器在导出时查询。文本来源按语言分别取活动组件，重复表合并由共享 Catalog 解析器处理。类别和前置复杂表达式继续保留原值。品质映射需要证据字段；单纯重复该数字并不能确定其含义。

## 触发器适配

`triggers` 每项绑定一个函数，可以覆盖同数组的多个字段写入。逐条注册的示例为：

```json
{
  "library": "ABCD1234",
  "function": "12345678",
  "namespace": "MyTalents",
  "roles": {"id": "PARAM_ID", "name_key": "PARAM_NAME", "rarity": "PARAM_RARITY"}
}
```

`roles` 的值为 GUI ParamDef ID。取到字面值时导出，嵌套计算与变量值列入动态缺口。多个库中相同的显示名继续由精确 ID 区分。静态调用位置包括库 ID 和 FunctionCall ID。

数组写入可以映射赋值 action 的目标参数和右值参数。例如：

```json
{
  "library": "Ntve",
  "function": "已核实的赋值函数ID",
  "namespace": "MyTalents",
  "array_id": "Talent",
  "roles": {
    "array_index": {"parameter": "目标参数定义ID", "array_index": true},
    "name": "右值参数定义ID"
  }
}
```

通过目标参数的 `Array` 引用读取常量索引，以 `Talent[3]` 为稳定行 ID。实际项目要先核对目标变量，再按 `variable` 填写目标变量 ID，避免同一个赋值函数消费其他数组。

当启用 `merge_on` 时，只按非空 `id` 或 `upgrade` 唯一合并。多候选、冲突或动态信息记录诊断。相同名称不参与合并。注册调用的执行条件与正常可达性需要独立取证。


## 品质 GUI 映射

`rarity_gui.rarity` 填入已核实的选择界面 Switch 的 `library` 和 `switch` ID。若界面对某些品质改按条目类型显示，`rarity_gui.category` 填写对应的字符串 Switch，并在 `display_category_for`（同属 `rarity_gui`）列出这些品质原值字符串。工具每次从活动 GUI 的常量 case 和本地化文本重新读取标签，将 case、动作和文本参数的位置保存在项目映射里。复杂分支需另行核实；手工核实的项目可继续使用带 evidence 的 rarity_labels。
