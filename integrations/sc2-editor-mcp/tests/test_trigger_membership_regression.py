"""Regression: updating an existing Trigger is not a new top-level object, so it
keeps its Category/declaration membership instead of being re-registered to Root.
Also covers the layout check rejecting duplicate Root/Category Item owners."""
from xml.etree import ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_writer import plan_write, validate_editor_library_layout

HEAD = '<?xml version="1.0" encoding="utf-8"?>\r\n<TriggerData>\r\n'
LIB = 'LibABC'
TRIG_A = 'AAAAAAAA'
TRIG_B = 'BBBBBBBB'
CAT_C = 'CCCCCCCC'
CAT_D = 'DDDDDDDD'


def _triggers(body):
    return HEAD + '<Library Id="%s">\r\n%s</Library>\r\n</TriggerData>' % (LIB, body)


def _root(items, library_id=LIB):
    body = ''.join('<Item Type="%s" Id="%s" Library="%s"/>' % (t, i, library_id) for t, i in items)
    return '<Root>\r\n%s</Root>\r\n' % body


def _category(category_id=CAT_C, triggers=()):
    # A Category lists only its members; it is not an Item of itself.
    body = ''.join('<Item Type="Trigger" Id="%s" Library="%s"/>' % (t, LIB) for t in triggers)
    return '<Element Type="Category" Id="%s">\r\n%s</Element>\r\n' % (category_id, body)


def _trigger_element(trigger_id=TRIG_A):
    return '<Element Type="Trigger" Id="%s">\r\n</Element>\r\n' % trigger_id


def _members(text, typ, ident):
    """Every (container kind, target Library) registration of Type/Id in the Library."""
    found = []
    for library in ET.fromstring(text).findall('Library'):
        for item in library.findall('Root/Item'):
            if (item.get('Type'), item.get('Id')) == (typ, ident):
                found.append(('Root', item.get('Library')))
        for element in library.findall('Element'):
            for item in element.findall('Item'):
                if (item.get('Type'), item.get('Id')) == (typ, ident):
                    found.append(('Category', item.get('Library')))
    return found


def _write(tmp_path, text):
    # safe_path expects a Path, not a str.
    (tmp_path / 'Triggers').write_bytes(text.encode('utf-8'))
    return tmp_path


def _plan(tmp_path, text, operation):
    root = _write(tmp_path, text)
    return plan_write(root, [operation])['Triggers'].decode('utf-8-sig')


def _renamed_children():
    # node() rejects tag 'Element' as a child tag; use a real child node.
    return [{'tag': 'Identifier', 'text': 'Updated'}]


# 1. Existing Category Trigger, no owner given: membership stays Category only.
def test_existing_category_trigger_default_upsert_keeps_membership(tmp_path):
    out = _plan(tmp_path, _triggers(_category(triggers=[TRIG_A]) + _trigger_element()),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB, 'children': _renamed_children()})
    assert _members(out, 'Trigger', TRIG_A) == [('Category', LIB)]
    assert ET.fromstring(out).find('Library').findall('Root/Item') == []
    assert [c.get('Identifier') is None and c.text for c in ET.fromstring(out).iter('Identifier')] == ['Updated']


# 2. Existing Root Trigger stays a single Root registration.
def test_existing_root_trigger_stays_single(tmp_path):
    out = _plan(tmp_path, _triggers(_root([('Trigger', TRIG_A)]) + _trigger_element()),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB, 'children': _renamed_children()})
    assert _members(out, 'Trigger', TRIG_A) == [('Root', LIB)]
    assert out.count('<Item Type="Trigger" Id="%s"' % TRIG_A) == 1


# 3. A new Trigger still defaults to exactly one Root registration.
def test_new_trigger_defaults_to_root_once(tmp_path):
    out = _plan(tmp_path, _triggers(_root([])),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB})
    assert _members(out, 'Trigger', TRIG_A) == [('Root', LIB)]
    assert out.count('<Item Type="Trigger" Id="%s"' % TRIG_A) == 1


# 4. owner False never changes membership: existing Category stays, new has none.
def test_owner_false_leaves_existing_category_membership(tmp_path):
    out = _plan(tmp_path, _triggers(_category(triggers=[TRIG_A]) + _trigger_element()),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB, 'owner': False})
    assert _members(out, 'Trigger', TRIG_A) == [('Category', LIB)]


def test_owner_false_new_trigger_registers_nothing(tmp_path):
    out = _plan(tmp_path, _triggers(_root([])),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB, 'owner': False})
    assert _members(out, 'Trigger', TRIG_A) == []


def test_explicit_category_owner_keeps_single_registration(tmp_path):
    out = _plan(tmp_path, _triggers(_category(triggers=[TRIG_A]) + _trigger_element()),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB,
                 'owner': {'type': 'Category', 'id': CAT_C}, 'children': _renamed_children()})
    assert _members(out, 'Trigger', TRIG_A) == [('Category', LIB)]


# 5. Real Root + Category duplicate of the same Type/Id in one Library is rejected.
def test_layout_rejects_root_and_category_duplicate():
    text = _triggers(_root([('Trigger', TRIG_A)]) + _category(triggers=[TRIG_A]) + _trigger_element())
    with pytest.raises(SC2Error) as excinfo:
        validate_editor_library_layout(ET.fromstring(text))
    assert 'duplicate Item owner' in str(excinfo.value)


def test_layout_rejects_duplicate_category_owner():
    text = _triggers(_category(triggers=[TRIG_A]) + _category(category_id=CAT_D, triggers=[TRIG_A])
                     + _trigger_element())
    with pytest.raises(SC2Error) as excinfo:
        validate_editor_library_layout(ET.fromstring(text))
    assert 'duplicate Item owner' in str(excinfo.value)


# 6. Same ID in another Library or of another Type is not a duplicate.
def test_layout_allows_same_id_in_other_library():
    text = (HEAD + '<Library Id="%s">\r\n%s</Library>\r\n'
            '<Library Id="LibOTHER">\r\n<Root>\r\n<Item Type="Trigger" Id="%s" Library="LibOTHER"/>\r\n</Root>\r\n'
            '</Library>\r\n</TriggerData>') % (LIB, _root([('Trigger', TRIG_A)]) + _trigger_element(), TRIG_A)
    tree = ET.fromstring(text)
    assert len(tree.findall(".//Item[@Id='%s']" % TRIG_A)) == 2
    validate_editor_library_layout(tree)


def test_layout_allows_same_id_with_different_type():
    # Two Items with the same Id but different Type, one on Root and one in a Category.
    text = (HEAD + '<Library Id="%s">\r\n'
            '<Root>\r\n<Item Type="Trigger" Id="%s" Library="%s"/>\r\n</Root>\r\n'
            '<Element Type="Category" Id="%s">\r\n<Item Type="Variable" Id="%s" Library="%s"/>\r\n</Element>\r\n'
            '</Library>\r\n</TriggerData>') % (LIB, TRIG_A, LIB, CAT_C, TRIG_A, LIB)
    tree = ET.fromstring(text)
    assert len(tree.findall(".//Item[@Id='%s']" % TRIG_A)) == 2
    validate_editor_library_layout(tree)


# 7. One Category holding the same Type/Id for different target Libraries is fine;
#    repeating the same target Library inside that Category is not.
def test_layout_uses_item_library_for_duplicate_key():
    one_category = _triggers('<Element Type="Category" Id="%s">\r\n'
                             '<Item Type="Trigger" Id="%s" Library="LibONE"/>\r\n'
                             '<Item Type="Trigger" Id="%s" Library="LibTWO"/>\r\n'
                             '</Element>\r\n' % (CAT_C, TRIG_A, TRIG_A))
    validate_editor_library_layout(ET.fromstring(one_category))


def test_layout_rejects_same_target_library_twice_in_category():
    repeated = _triggers('<Element Type="Category" Id="%s">\r\n'
                         '<Item Type="Trigger" Id="%s" Library="LibONE"/>\r\n'
                         '<Item Type="Trigger" Id="%s" Library="LibONE"/>\r\n'
                         '</Element>\r\n' % (CAT_C, TRIG_A, TRIG_A))
    with pytest.raises(SC2Error):
        validate_editor_library_layout(ET.fromstring(repeated))


# 8. Existing layout checks are preserved.
def test_layout_keeps_existing_checks():
    missing = _triggers('<Root>\r\n<Item Type="Trigger" Id="%s"/>\r\n</Root>\r\n' % TRIG_A)
    with pytest.raises(SC2Error) as excinfo:
        validate_editor_library_layout(ET.fromstring(missing))
    assert 'explicit Library required' in str(excinfo.value)
    late = HEAD + '<Root/>\r\n<Library Id="%s">\r\n%s</Library>\r\n</TriggerData>' % (LIB, _root([]))
    with pytest.raises(SC2Error) as excinfo:
        validate_editor_library_layout(ET.fromstring(late))
    assert 'Library must precede map Root' in str(excinfo.value)


# 9. An already Root-registered element whose Root Item lacks Library must still be
#    re-registered once, repairing the qualifier; it must not gain a second Item.
def _root_members(text, typ, ident):
    found = []
    for library in ET.fromstring(text).findall('Library'):
        for item in library.findall('Root/Item'):
            if (item.get('Type'), item.get('Id')) == (typ, ident):
                found.append(item.get('Library'))
    return found


def test_unqualified_root_trigger_library_is_repaired(tmp_path):
    unqualified = '<Root>\r\n<Item Type="Trigger" Id="%s"/>\r\n</Root>\r\n' % TRIG_A
    out = _plan(tmp_path, _triggers(unqualified + _trigger_element()),
                {'type': 'Trigger', 'id': TRIG_A, 'library': LIB, 'children': _renamed_children()})
    assert _root_members(out, 'Trigger', TRIG_A) == [LIB]
    assert out.count('<Item Type="Trigger" Id="%s"' % TRIG_A) == 1


def test_unqualified_root_variable_library_is_repaired(tmp_path):
    unqualified = '<Root>\r\n<Item Type="Variable" Id="%s"/>\r\n</Root>\r\n' % TRIG_A
    out = _plan(tmp_path, _triggers(unqualified + '<Element Type="Variable" Id="%s"/>\r\n' % TRIG_A),
                {'type': 'Variable', 'id': TRIG_A, 'library': LIB})
    assert _root_members(out, 'Variable', TRIG_A) == [LIB]
    assert out.count('<Item Type="Variable" Id="%s"' % TRIG_A) == 1
