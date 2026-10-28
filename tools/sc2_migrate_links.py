# Adapted from SC2EditorTool, Copyright (c) 2026 RichardM (MIT).
# See vendor/sc2editortool/LICENSE.
"""Typed migration links, including the reverse presentation side of catalogs.

Only known link positions are interpreted. An arbitrary string equal to an ID is
not evidence of a link; actor aliases and runtime substitutions stay diagnostic.
"""
import re
from collections import Counter, defaultdict
from sc2_migrate_catalog import elements, LINKS, FAMILIES, semantic_index

FIELDS = {
    'UnitName': 'Unit', 'unitName': 'Unit', 'UnitLink': 'Unit',
    'Abil': 'Abil', 'AbilLink': 'Abil', 'Ability': 'Abil',
    'Weapon': 'Weapon', 'WeaponLink': 'Weapon',
    'BehaviorLink': 'Behavior', 'Buff': 'Behavior',
    'effectAttack': 'Effect', 'effectLaunch': 'Effect', 'effectImpact': 'Effect',
    'AttackEffect': 'Effect', 'DeathEffect': 'Effect', 'BirthEffect': 'Effect',
    'DamageEffect': 'Effect', 'FinishEffect': 'Effect', 'CancelEffect': 'Effect',
    'DeathModel': 'Model', 'ModelDeath': 'Model', 'ModelBuild': 'Model',
    'ModelPlacement': 'Model', 'ModelPortrait': 'Model', 'PortraitModel': 'Model',
    'LaunchModel': 'Model', 'ImpactModel': 'Model', 'ModelLink': 'Model',
    'BuildModel': 'Model', 'PlacementModel': 'Model',
    'LaunchActor': 'Actor', 'ImpactActor': 'Actor', 'Beam': 'Actor',
    'HostActor': 'Actor', 'HostSupporter': 'Actor', 'CopySource': 'Actor',
    'SoundArray': 'Sound', 'SoundLink': 'Sound', 'LaunchSound': 'Sound',
    'ImpactSound': 'Sound', 'DeathSound': 'Sound', 'BirthSound': 'Sound',
    'PlacementSound': 'Sound',
    'Sound': 'Sound', 'MoverLink': 'Mover', 'TurretLink': 'Turret',
    'FootprintLink': 'Footprint', 'ValidatorLink': 'Validator',
    'ValidatorRemoveArray': 'Validator', 'ValidatorDisableArray': 'Validator',
    'ValidatorRegenArray': 'Validator', 'ValidatorsArray': 'Validator',
    'CountUnit': 'Unit', 'CountUpgrade': 'Upgrade', 'UpgradeLink': 'Upgrade',
    'RequirementNode': 'RequirementNode', 'Use': 'RequirementNode',
    'Show': 'RequirementNode', 'OperandArray': 'RequirementNode',
    'Operands': 'RequirementNode', 'Operand': 'RequirementNode',
    'CombineArray': 'Validator', 'AttachQuery': 'AttachMethod',
    'LaunchAttachQuery': 'AttachMethod', 'ImpactAttachQuery': 'AttachMethod',
    'SiteOps': 'Actor', 'SiteOpsArray': 'Actor', 'Macros': 'Actor',
    'MacroArray': 'Actor', 'Texture': 'Texture', 'TextureArray': 'Texture',
    'TargetFind': 'TargetFind', 'TargetSort': 'TargetSort',
}
ASSET = re.compile(r'\.(?:m3|m3a|dds|tga|png|jpg|ogg|wav|mp3|anim)$', re.I)
TEXT_FIELD = re.compile(r'(?:Name|Description|Tooltip|Text|Label|Hotkey|EditorPrefix|EditorSuffix)$')
TEXT_REF = re.compile(r'<s\s+[^>]*?(?:text|ref|val)\s*=\s*["\']([^"\']+)["\']', re.I)
DATA_REF = re.compile(r'<d\s+[^>]*?ref\s*=\s*["\']([^"\']+)["\']', re.I)
ACTOR_PATTERNS = (
    (r'\bUnit(?:Birth|Revive|Death|Construction|TypeChange)?\.([^.;\s]+)', 'Unit'),
    (r'\bEffect\.([^.;\s]+)\.', 'Effect'),
    (r'\bWeapon(?:Start|Stop|Fired)?\.([^.;\s]+)', 'Weapon'),
    (r'\bBehavior\.([^.;\s]+)\.', 'Behavior'),
    (r'\bAbil(?:Morph)?\.([^.;\s]+)\.', 'Abil'),
    (r'\b(?:ValidateUnit|ValidatePlayer)\s+(\S+)', 'Validator'),
    (r'\b(?:MorphTo|MorphFrom)\s+(\S+)', 'Unit'),
)


def text_data_links(value):
    result = []
    for reference in DATA_REF.findall(value):
        parts = reference.split(',', 2)
        if len(parts) >= 2 and parts[0] in FAMILIES and parts[1]:
            result.append(parts[0] + ':' + parts[1])
    return result


def _known_links(node, family, oid):
    rows = []
    source = f'{family}:{oid}'
    issues = []

    def add(target_family, value, field, role='reference', lookup=''):
        value = value.rstrip(';')
        if not value or value in {'None', 'null', '*', 'Find', 'Create'}:
            return
        if target_family == 'RequirementNode' and re.fullmatch(r'-?\d+(?:\.\d+)?', value):
            return  # Inline requirement constants are operands, not catalog IDs.
        if value.startswith(('_', '::')) or value in {'Self', 'Creator', 'Host'}:
            return
        if '##' in value or '$' in value:
            issues.append(dict(code='dynamic_reference', source=source, field=field, value=value))
            return
        target = 'asset:' + value if ASSET.search(value) else f'{target_family}:{value}'
        rows.append(dict(source=source, target=target, field=field, role=role, lookup=lookup))

    parent = node.get('attributes', {}).get('parent')
    if parent:
        add(family, parent, '@parent', 'parent')

    def walk(n, prefix='', lookup='', root=False):
        attrs = n.get('attributes', {})
        tag = n['@tag']
        field = prefix + tag
        mappings = {**LINKS, **FIELDS}
        if family != 'Requirement':
            mappings.pop('Use', None)
            mappings.pop('Show', None)
        if family == 'Requirement':
            mappings['NodeArray'] = 'RequirementNode'
        if family == 'RequirementNode' and tag == 'Count':
            counted_family = node['@tag'].removeprefix('CRequirementCount')
            if counted_family in FAMILIES:
                mappings['Count'] = counted_family
        if tag in mappings and not (family == 'Upgrade' and tag == 'EffectArray'):
            value = attrs.get('Link', attrs.get('value', attrs.get('Value', '')))
            for part in value.split() if tag in {'SiteOps', 'SiteOpsArray', 'Macros'} else [value]:
                add(mappings[tag], part, field, lookup=lookup)
        if tag == 'AbilCommandArray' and ',' in attrs.get('value', ''):
            add('Abil', attrs['value'].split(',', 1)[0], field, lookup=lookup)
        for attr, value in attrs.items():
            attribute_lookup = lookup if attr in {'value', 'Value', 'Link'} else lookup + '|@' + attr
            if attr in mappings:
                add(mappings[attr], value, field + '/@' + attr, 'binding', attribute_lookup)
            if attr == 'AbilCmd' and ',' in value:
                add('Abil', value.split(',', 1)[0], field + '/@' + attr, lookup=attribute_lookup)
            if attr == 'Reference' and ',' in value:
                parts = value.split(',', 2)
                add(parts[0], parts[1], field + '/@Reference', 'modifies_field', attribute_lookup)
            if ASSET.search(value):
                add('asset', value, field + '/@' + attr, lookup=attribute_lookup)
            if TEXT_FIELD.search(tag) and attr in {'value', 'Link'} and '/' in value and not ASSET.search(value):
                add('text', value, field, lookup=attribute_lookup)
            if family == 'Actor' and attr in {'Terms', 'Send', 'Target', 'Subject'}:
                for pattern, target_family in ACTOR_PATTERNS:
                    for match in re.findall(pattern, value):
                        add(target_family, match, field + '/@' + attr, 'actor_event', attribute_lookup)
                        if rows and rows[-1].get('lookup') == attribute_lookup:
                            rows[-1]['event_creates'] = bool(re.match(r'^\s*(?:Create|CreateCopy|ActorCreate)(?:\s|$)', attrs.get('Send', '')))
                            if not rows[-1]['event_creates']:
                                rows[-1]['optional_condition'] = True
                if attr in {'Send', 'Target'}:
                    for match in re.findall(r'\b(?:Create|CreateCopy|ActorCreate)\s+([^;\s]+)', value):
                        add('Actor', match, field + '/@' + attr, 'actor_message', attribute_lookup)
                if attr == 'Send':
                    for verb, target_family in (('ModelSwap','Model'),('ModelSet','Model'),('SoundPlay','Sound')):
                        for match in re.findall(r'\b'+verb+r'\s+([^;\s]+)',value):
                            add(target_family,match,field+'/@'+attr,'actor_message',attribute_lookup)
        children = elements(n)
        counts, tags = defaultdict(int), Counter(c['@tag'] for c in children)
        for c in children:
            ctag = c['@tag']
            index = semantic_index(c)
            array = index is not None or ctag.endswith('Array') or tags[ctag] > 1
            if index is None and array:
                index = str(counts[ctag])
            counts[ctag] = max(counts[ctag] + 1, int(index) + 1) if index is not None and index.isdigit() else counts[ctag] + 1
            path = (lookup + '|' if lookup else '') + ctag + ('|' + index if array else '')
            walk(c, field + '/', path)
    walk(node, root=True)
    seen, result = set(), []
    for row in rows:
        target = row['target']
        value = target.split(':', 1)[1]
        if value.startswith(('_', '::')) or value in {'*', 'None', 'null'}:
            continue
        if target.startswith('Unit:Alias_'):
            row['conditional'] = True
        # Auto sound/footprint slots are optional runtime conventions. Keep the
        # evidence visible without turning absent conventional IDs into errors.
        if family == 'Actor' and ('/SoundArray' in row['field'] or '/EventDataFootprint' in row['field']):
            row['conditional'] = True
        if target.startswith('asset:asset:'):
            row['target'] = target[len('asset:'):]
        identity = row['target'], row['field'], row.get('role')
        if identity not in seen:
            result.append(row)
            seen.add(identity)
    return result, issues



def links(node, family, oid):
    """Supplement known actor/message rules with exact XSD link positions."""
    from sc2_migrate_catalog import SCHEMA_SHAPES
    rows, issues = _known_links(node, family, oid)
    def shape(ctype, seen=()):
        if ctype in seen or ctype not in SCHEMA_SHAPES:
            return {}, {}
        children,attrs,base = SCHEMA_SHAPES[ctype]
        inherited_children,inherited_attrs = shape(base,seen+(ctype,))
        return {**inherited_children,**children},{**inherited_attrs,**attrs}
    def walk(current, ctype, path=''):
        children,attrs = shape(ctype)
        for attr,value in current.get('attributes',{}).items():
            kind = attrs.get(attr,'')
            match = re.fullmatch(r'(?:simple_)?C(\w+)Link',kind)
            if match and value and not ('##' in value or '$' in value):
                target_family = match[1]
                if target_family == 'String':
                    target_family = 'text'
                elif target_family not in FAMILIES:
                    continue  # aliases and non-catalog link classes are not IDs
                if target_family!='text' and value in {'0','None','null','*','Self','Creator','Host','Find','Create'}:
                    continue
                lookup = path if attr in {'value','Value','Link'} else path+'|@'+attr
                target = target_family+':'+value
                if not any(r['target']==target and r.get('lookup')==lookup for r in rows):
                    role='runtime_alias' if target_family=='Actor' and value.startswith(('_','::')) else 'schema_reference'
                    rows.append({'source':family+':'+oid,'target':target,'field':path+'/@'+attr,
                                 'lookup':lookup,'role':role,'schema_type':kind})
        counts=defaultdict(int)
        items=elements(current);tags=Counter(c['@tag'] for c in items)
        for child in items:
            tag=child['@tag'];idx=semantic_index(child)
            array=idx is not None or tag.endswith('Array') or tags[tag]>1
            if idx is None and array:
                idx=str(counts[tag])
            counts[tag]=max(counts[tag]+1,int(idx)+1) if idx is not None and idx.isdigit() else counts[tag]+1
            lookup=(path+'|' if path else '')+tag+('|' + idx if array else '')
            walk(child,children.get(tag,''),lookup)
    walk(node,node['@tag'])
    return rows,issues
