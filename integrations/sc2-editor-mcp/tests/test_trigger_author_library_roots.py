"""Library-only Triggers documents can lack the outer Root container."""
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from sc2_mcp.errors import SC2Error
from sc2_mcp.trigger_author import Author


def library_author(*, keep_reference=False):
    library = 'A431EF10'
    call = (library, 'FunctionCall', '10000001')
    parameter = (library, 'Param', '10000002')
    trigger = (library, 'Trigger', '10000003')
    replacement = (library, 'FunctionCall', '10000004')
    instance = Author.__new__(Author)
    instance.doc = SimpleNamespace(path='LibraryOnly.SC2Mod/Triggers')
    instance.target = SimpleNamespace(documents=[instance.doc])
    instance.elements = {
        call: ET.fromstring('<Element Type="FunctionCall" Id="10000001">'
            '<FunctionDef Type="FunctionDef" Library="Ntve" Id="00000136"/>'
            '<Parameter Type="Param" Library="A431EF10" Id="10000002"/></Element>'),
        parameter: ET.fromstring('<Element Type="Param" Id="10000002">'
            '<ParameterDef Type="ParamDef" Library="Ntve" Id="00000220"/>'
            '<Value>old value</Value><ValueType Type="string"/></Element>'),
        trigger: ET.fromstring('<Element Type="Trigger" Id="10000003">'
            '<Action Type="FunctionCall" Library="A431EF10" Id="%s"/></Element>'
            % (call[2] if keep_reference else replacement[2])),
        replacement: ET.fromstring('<Element Type="FunctionCall" Id="10000004">'
            '<FunctionDef Type="FunctionDef" Library="Ntve" Id="7B4A4D9D"/></Element>'),
    }
    # This is the shape read from a mod whose content is entirely in Library.
    instance.roots = {('', 'Root', ''): None,
                      (library, 'Root', ''): ET.fromstring('<Root/>')}
    instance.deleted = set()
    return instance, call, parameter, trigger, replacement


def test_prune_library_only_document_removes_exclusive_old_instances():
    instance, call, parameter, trigger, replacement = library_author()

    instance.prune([call], 'edits[0]')

    assert set(instance.elements) == {trigger, replacement}
    assert instance.deleted == {call, parameter}
    assert instance.roots[('', 'Root', '')] is None
    assert instance.roots[(call[0], 'Root', '')].tag == 'Root'


def test_prune_library_only_document_still_blocks_external_reference():
    instance, call, parameter, trigger, replacement = library_author(keep_reference=True)
    before = {key: ET.tostring(value) for key, value in instance.elements.items()}

    with pytest.raises(SC2Error) as error:
        instance.prune([call], 'edits[0]')

    assert error.value.code == 'trigger_author_invalid'
    references = error.value.details['references']
    assert references == [{'source': instance.doc.path,
                           'reference': list(trigger), 'target': list(call)}]
    assert {key: ET.tostring(value) for key, value in instance.elements.items()} == before
    assert not instance.deleted


def test_edit_delete_library_only_document_accepts_allowed_delete_shape():
    # Author.edit checks the exact edit shape before op='delete' touches the None global root.
    instance, call, parameter, trigger, replacement = library_author()
    instance.library = call[0]
    instance.impacts = []
    instance.review_node = lambda key: {'reference': list(key)}

    instance.edit({'op': 'delete', 'target': list(call)}, 'edits[0]')

    assert set(instance.elements) == {trigger, replacement}
    assert instance.deleted == {call, parameter}
    assert instance.roots[('', 'Root', '')] is None
    assert instance.roots[(call[0], 'Root', '')].tag == 'Root'
    assert instance.impacts[0]['operation'] == 'delete'


def movable_library_author(*, shared_owner=False):
    instance, call, parameter, source, replacement = library_author(keep_reference=True)
    destination = (call[0], 'Trigger', '10000005')
    instance.elements[destination] = ET.fromstring(
        '<Element Type="Trigger" Id="10000005">'
        '<Action Type="FunctionCall" Library="A431EF10" Id="%s"/></Element>'
        % (call[2] if shared_owner else replacement[2]))
    instance.library = call[0]
    instance.impacts = []
    instance.review_node = lambda key: {'reference': list(key)}
    instance.resolve = lambda ref, kind, path: (
        instance.doc, tuple(ref), ET.fromstring('<Element><FlagAction/></Element>'))
    instance.queue_parameter_check = lambda key, path: None
    return instance, call, parameter, source, destination, replacement


def test_move_library_only_document_preserves_call_and_parameter():
    instance, call, parameter, source, destination, replacement = movable_library_author()
    before = {key: ET.tostring(instance.elements[key]) for key in [call, parameter]}

    instance.edit({'op': 'move', 'target': list(call), 'parent': list(destination),
                   'role': 'actions', 'index': 0}, 'edits[0]')

    assert not instance.elements[source].findall('Action')
    assert [n.get('Id') for n in instance.elements[destination].findall('Action')] == [call[2], replacement[2]]
    assert {key: ET.tostring(instance.elements[key]) for key in [call, parameter]} == before
    assert instance.roots[('', 'Root', '')] is None
    assert instance.impacts[0]['id_policy'] == 'preserved'


def test_move_library_only_document_still_rejects_shared_owner():
    instance, call, parameter, source, destination, replacement = movable_library_author(shared_owner=True)
    before = {key: ET.tostring(value) for key, value in instance.elements.items()}

    with pytest.raises(SC2Error) as error:
        instance.edit({'op': 'move', 'target': list(call), 'parent': list(destination),
                       'role': 'actions', 'index': 0}, 'edits[0]')

    assert error.value.code == 'trigger_author_invalid'
    assert 'exactly one owning reference' in str(error.value)
    assert {key: ET.tostring(value) for key, value in instance.elements.items()} == before


def array_index_author():
    # Real Array edge: the index Param holds a Param reference, not a nested Value.
    # arr needs no definition because owner_scope/check_scope never read variable types.
    library = 'A431EF10'
    source = (library, 'FunctionDef', '3692C84C')
    destination = (library, 'FunctionDef', '3692C84D')
    param_def = (library, 'ParamDef', '0EB672F4')
    call = (library, 'FunctionCall', '2A31DD2D')
    outer = (library, 'Param', '10000011')
    index = (library, 'Param', '10000012')
    instance = Author.__new__(Author)
    instance.doc = SimpleNamespace(path='LibraryOnly.SC2Mod/Triggers')
    instance.target = SimpleNamespace(documents=[instance.doc])
    instance.elements = {
        source: ET.fromstring('<Element Type="FunctionDef" Id="3692C84C">'
            '<Parameter Type="ParamDef" Library="A431EF10" Id="0EB672F4"/>'
            '<FunctionCall Type="FunctionCall" Library="A431EF10" Id="2A31DD2D"/></Element>'),
        destination: ET.fromstring('<Element Type="FunctionDef" Id="3692C84D"/>'),
        call: ET.fromstring('<Element Type="FunctionCall" Id="2A31DD2D">'
            '<Parameter Type="Param" Library="A431EF10" Id="10000011"/></Element>'),
        outer: ET.fromstring('<Element Type="Param" Id="10000011">'
            '<Variable Type="Variable" Library="A431EF10" Id="10000010"/>'
            '<Array Type="Param" Library="A431EF10" Id="10000012"/></Element>'),
        index: ET.fromstring('<Element Type="Param" Id="10000012">'
            '<Parameter Type="ParamDef" Library="A431EF10" Id="0EB672F4"/></Element>'),
        param_def: ET.fromstring('<Element Type="ParamDef" Id="0EB672F4">'
            '<ParameterType><Type Value="int"/></ParameterType></Element>'),
    }
    instance.roots = {}
    instance.deleted = set()
    instance.scopes = {}
    instance._scope_lookup_cache = {}
    return instance, source, destination, call, index, param_def


def test_array_index_parameter_scope_follows_call_function():
    instance, source, destination, call, index, param_def = array_index_author()

    instance.current_scope = instance.owner_scope(index)
    instance.check_scope(param_def, 'edits[0].array')

    assert instance.current_scope == source


def test_array_index_parameter_scope_rejects_crossing_function():
    instance, source, destination, call, index, param_def = array_index_author()
    # Move the call reference to B; A still declares p.
    instance.elements[source].remove(instance.elements[source].find('FunctionCall'))
    instance.elements[destination].append(ET.fromstring(
        '<FunctionCall Type="FunctionCall" Library="A431EF10" Id="2A31DD2D"/>'))

    instance.current_scope = instance.owner_scope(index)
    assert instance.current_scope == destination
    with pytest.raises(SC2Error) as error:
        instance.check_scope(param_def, 'edits[0].array')

    assert error.value.code == 'trigger_author_invalid'
    assert 'local reference crosses function scope' in str(error.value)
