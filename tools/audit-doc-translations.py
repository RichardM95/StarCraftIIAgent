#!/usr/bin/env python3
"""Check bilingual usage pages, source fingerprints and example coverage."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import string
import sys

from sc2_i18n import UIArgumentParser, tr, run_cli

ROOT = Path(__file__).resolve().parents[1]


def source_digest(path):
    """Normalized UTF-8/LF digest is stable across Git checkout line endings."""
    return hashlib.sha256(path.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()


def check(root):
    errors = []
    try:
        pages = json.loads((root/'tools/sc2_doc_translations.json').read_text(encoding='utf-8'))['pages']
        for item in pages:
            source, english = root/item['source'], root/item['english']
            if not source.is_file() or not english.is_file():
                errors.append('Missing translation pair: ' + item['source'])
                continue
            original = source.read_text(encoding='utf-8-sig')
            translated = english.read_text(encoding='utf-8-sig')
            stamp = f"<!-- translation-source: {item['source']}; sha256: {source_digest(source)} -->"
            if stamp not in translated:
                errors.append('Outdated translation/source fingerprint: ' + item['english'])
            if f'({english.name})' not in original or f'({source.name})' not in translated:
                errors.append('Missing language switch: ' + item['source'])
            if item.get('scenarios'):
                expected = [f'{n:02}' for n in range(1, item['scenarios'] + 1)]
                for path, text in ((source, original), (english, translated)):
                    if re.findall(r'^\| (\d{2}) ', text, re.M) != expected:
                        errors.append('Scenario numbering mismatch: ' + str(path.relative_to(root)))
                if translated.count('\n### ') != item['dialogues']:
                    errors.append('Complete dialogue count mismatch: ' + item['english'])
        required = {p.as_posix() for p in root.glob('*.en.md')}
        covered = {(root/item['english']).as_posix() for item in pages}
        for missing in sorted(required - covered):
            errors.append('Unregistered translation: ' + missing)
        messages = json.loads((root/'tools/sc2_ui_messages.json').read_text(encoding='utf-8'))
        formatter = string.Formatter()
        def fields(text):
            return sorted((key, spec, conversion) for _, key, spec, conversion in formatter.parse(text) if key is not None)
        for key, value in messages.items():
            if not value or fields(key) != fields(value):
                errors.append('Invalid message translation/placeholders: ' + key)
        paths = list((root/'tools').glob('*.py'))
        paths += list((root/'skills/sc2-attack-wave-scaling/scripts').glob('*.py'))
        for path in paths:
            raw = path.read_text(encoding='utf-8-sig')
            if 'UIArgumentParser(' not in raw or path.name == 'sc2_i18n.py':
                continue
            tree = ast.parse(raw)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                values = [k.value for k in node.keywords if k.arg in ('help', 'description')]
                if isinstance(node.func, ast.Name) and node.func.id == 'tr' and node.args:
                    values.append(node.args[0])
                for value in values:
                    key = value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else (
                        ast.get_docstring(tree) if isinstance(value, ast.Name) and value.id == '__doc__' else None)
                    if key and key not in messages:
                        errors.append(f'Missing UI message: {path.name}: {key}')
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as exc:
        errors.append('Invalid translation inventory: ' + str(exc))
    return errors


def main():
    parser = UIArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path, nargs='?', default=ROOT, help='repository root')
    args = parser.parse_args()
    errors = check(args.root.resolve())
    if errors:
        print(tr('Translation audit failed:'))
        for error in errors:
            print('  ' + error)
        return 1
    print(tr('Translation pairs, fingerprints, examples and UI messages verified.'))
    return 0


if __name__ == '__main__':
    sys.exit(run_cli(main))
