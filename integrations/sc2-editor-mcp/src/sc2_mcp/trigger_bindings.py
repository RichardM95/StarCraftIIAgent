"""Source-bound Galaxy signatures and GUI type aliases."""
from functools import lru_cache
import hashlib
import re
from .errors import SC2Error
from .script import _strip_comments_strings


@lru_cache(maxsize=4)
def signature_index(inputs):
    signatures = {}
    pattern = re.compile(r'(?m)^\s*(?:native\s+)?(?!(?:return|else|if|while|for|switch)\b)(\w+)\s+(\w+)\s*\(([^;{}]*)\)\s*(?:;|\{)')
    for path, source in inputs:
        masked, _ = _strip_comments_strings(source)
        for match in pattern.finditer(masked):
            result, name, arguments = match.groups()
            params = [' '.join(p.split()[:-1]) for p in arguments.split(',')] if arguments.strip() else []
            record = {'return': result, 'parameters': params, 'file': path,
                      'line': masked.count('\n', 0, match.start()) + 1,
                      'sha256': hashlib.sha256(source.encode('utf-8')).hexdigest()}
            signatures.setdefault(name, []).append(record)
    return signatures


class Bindings:
    def __init__(self, target, files, roots):
        self.target = target
        self.files = files
        self.used = []
        self.unresolved = []
        self.aliases = {'gamelink': 'string', 'anygamelink': 'string'}
        self.index = signature_index(tuple(sorted(files.items())))
        self.active = set()
        def visit(path):
            path = path.lower()
            if path in self.active:
                return
            if path not in files:
                raise SC2Error('trigger_include_missing', 'required include is missing', path=path)
            self.active.add(path)
            masked, _ = _strip_comments_strings(files[path])
            for match in re.finditer(r'(?m)^\s*include\s+"([^"]+)"', files[path]):
                if masked[match.start():match.end()].lstrip().startswith('include'):
                    include = match.group(1).replace('\\', '/').lower()
                    visit(include.removesuffix('.galaxy') + '.galaxy')
        for path in roots:
            visit(path)
        observations = {}
        for document in target.documents:
            for key, element in document.elements.items():
                if key[1] != 'FunctionDef' or element.find('FlagNative') is None:
                    continue
                candidates = self.candidates(element.findtext('Identifier'))
                if not candidates and element.find('FunctionCall') is None:
                    self.unresolved.append({'definition':list(key),'name':element.findtext('Identifier'),
                                            'path':str(document.path),'sha256':document.sha256})
                variants = {(r['return'], tuple(r['parameters'])) for r in candidates}
                if len(variants) != 1:
                    continue
                result, params = next(iter(variants))
                gui = [self.raw_type(element, document, key, 'ReturnType')]
                if element.find('FlagEvent') is not None:
                    gui.append('trigger')
                for ref in element.findall('Parameter'):
                    if ref.get('Type') != 'ParamDef':
                        continue
                    pd, pe = target.resolve((ref.get('Library', key[0]), 'ParamDef', ref.get('Id')), document)
                    gui.append(self.raw_type(pe, pd, key, 'ParameterType'))
                if len(gui) != len(params) + 1:
                    continue
                for left, right in zip(gui, [result, *params]):
                    observations.setdefault(left, set()).add(right)
        for left, right in observations.items():
            if left and len(right) == 1:
                self.aliases[left] = next(iter(right))

    def candidates(self, name):
        return [r for r in self.index.get(name, []) if r['file'] in self.active]

    def raw_type(self, element, document, key, tag):
        container = element.find(tag)
        if container is None:
            return 'void' if tag == 'ReturnType' else None
        node = container.find('Type')
        value = node.get('Value') if node is not None else None
        if value == 'preset':
            ref = container.find('TypeElement')
            if ref is None:
                raise SC2Error('trigger_preset_type_missing', 'preset TypeElement is required', path=str(document.path), node=list(key))
            _, preset = self.target.resolve((ref.get('Library', key[0]), 'Preset', ref.get('Id')), document)
            base = preset.find('BaseType')
            value = base.get('Value') if base is not None else None
        if element.find('ParamFlagReference') is not None and value == 'unit':
            return 'unitref'
        return value

    def type(self, element, document, key, tag):
        value = self.raw_type(element, document, key, tag)
        return self.aliases.get(value, value)

    def bind(self, name, gui_return, gui_params, values, statement, document, key, definition, definition_document=None):
        candidates = self.candidates(name)
        variants = {(r['return'], tuple(r['parameters'])) for r in candidates}
        details = {'path': str(document.path), 'node': list(key), 'function': name,
                   'definition': list(definition), 'expected': candidates, 'actual_parameters': gui_params,
                   'actual_arguments': values, 'gui_return': gui_return}
        source = definition_document or document
        details['definition_source'] = {'path':str(source.path),'sha256':source.sha256}
        if len(variants) != 1:
            details['available_declarations'] = self.index.get(name, [])
            raise SC2Error('trigger_binding_missing', 'missing or ambiguous declaration in active include closure', **details)
        result, params = next(iter(variants))
        mapped = [self.aliases.get(t, t) for t in gui_params]
        expected_result = self.aliases.get(gui_return, gui_return)
        if list(params) != mapped or (expected_result != result and not (statement and gui_return == 'void')):
            raise SC2Error('trigger_binding_mismatch', 'GUI signature does not match active Galaxy declaration', **details)
        self.used.append({**details, 'signature': candidates[0], 'return_discarded': statement and result != 'void',
                          'gui_call_sha256': document.sha256})
        return name + '(' + ', '.join(values) + ')'
