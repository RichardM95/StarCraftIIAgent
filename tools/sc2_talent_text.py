"""Render static SC2 catalog expressions and presentation tags for talent lists."""
import ast
import operator
import re
import xml.etree.ElementTree as ET
from decimal import Decimal, DecimalException

from sc2_migrate_catalog import elements, semantic_index


FIELD = r"[A-Za-z_]\w*(?:\[[\w@]+\])?"
REFERENCE = re.compile(rf"([A-Za-z_]\w*),([\w@-]+),({FIELD}(?:\.{FIELD})*)")
DATA_TAG = re.compile(r"<d\b[^>]*>", re.I)
OPERATIONS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def plain_text(text):
    text = re.sub(r"<n\s*/>", "\n", text, flags=re.I)
    return re.sub(r"</?(?:c|s)\b[^>]*>", "", text, flags=re.I)


def field_value(root, path):
    node = root
    parts = path.split(".")
    for position, part in enumerate(parts):
        name, _, index = part.partition("[")
        attrs = node["attributes"]
        if position == len(parts) - 1 and part in attrs:
            return attrs[part]
        candidates = [c for c in elements(node) if c["@tag"] == name]
        if index:
            candidates = [c for c in candidates if semantic_index(c) == index[:-1]]
        if len(candidates) != 1:
            raise ValueError("字段缺失或索引不唯一: " + part)
        node = candidates[0]
    if "value" not in node["attributes"]:
        raise ValueError("字段没有可静态读取的数值: " + path)
    return node["attributes"]["value"]


def calculate(expression, catalog):
    # Substitute catalog leaves only. Evaluate the remaining arithmetic by walking
    # its syntax tree, keeping the decimal spellings from the source.
    values = {}

    def leaf(match):
        family, ident, path = match.groups()
        node = catalog.effective(family, ident)
        if node is None:
            raise ValueError("找不到对象: " + ident)
        value = Decimal(field_value(node, path))
        if not value.is_finite():
            raise ValueError("字段值不是有限数字")
        name = f"v{match.start()}"
        values[name] = value
        return name

    # Reject arbitrary identifiers, calls, Python operators and comments before
    # substitution so an input cannot masquerade as a synthesized variable.
    if re.search(r"[^\d.()+*/\s-]", REFERENCE.sub("0", expression)):
        raise ValueError("公式含有无法静态计算的内容")
    source = REFERENCE.sub(leaf, expression).strip()
    def evaluate(node):
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(ast.get_source_segment(source, node))
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATIONS:
            return OPERATIONS[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = evaluate(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        raise ValueError("不支持的运算")
    return evaluate(ast.parse(source, mode="eval").body)


def render_description(text, catalog, locale, ident, counts, issue):
    def replace(match):
        try:
            tag = ET.fromstring(match.group())
            value = calculate(tag.attrib["ref"], catalog)
            if "precision" in tag.attrib:
                digits = int(tag.attrib["precision"])
                if not 0 <= digits <= 28:
                    raise ValueError("无效精度")
                result = format(value, f".{digits}f")
            else:
                result = format(value.normalize(), "f")
        except (SyntaxError, ValueError, DecimalException, KeyError, ET.ParseError, RecursionError) as exc:
            counts["unresolved"] += 1
            issue("unresolved_description", {"id": ident, "locale": locale, "reference": match.group(), "reason": str(exc)})
            return "数值待确认" if locale == "zhCN" else "value unconfirmed"
        counts["resolved"] += 1
        return result
    return plain_text(DATA_TAG.sub(replace, text))
