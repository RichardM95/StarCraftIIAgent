from pathlib import Path
from copy import deepcopy
from xml.etree import ElementTree as E
import pytest
from sc2_mcp.errors import SC2Error
from test_trigger_codegen_stop_looping import Tree
IDS=['E65EFFD5','859ED2A6','28BFEC98']
class PresetTree(Tree):
    def __init__(self):
        super().__init__()
        for x in E.parse(Path(__file__).parent/'fixtures/implicit_preset.xml').getroot():self.nodes[('SwaC',x.get('Type'),x.get('Id'))]=deepcopy(x)
        self.group=self.nodes[('SwaC','Preset','15CE809C')]
    def value(self,i):
        k=self.put('Param');self.ref(self.nodes[k],'Preset',('SwaC','PresetValue',IDS[i]));return self.generator.expr(self.doc,k,self.nodes[k])

@pytest.mark.parametrize('i',[0,1,2])
def test_official_header_confirmed_integer_values(i):assert PresetTree().value(i)==str(i)

def test_order_comes_from_source_membership_not_hardcoded_ids():
    t=PresetTree();refs=t.group.findall('Item');t.group.remove(refs[-1]);t.group.insert(list(t.group).index(refs[0]),refs[-1]);assert t.value(2)=='0' and t.value(0)=='1'

@pytest.mark.parametrize('mutation',['duplicate_parent','duplicate_item','mixed_explicit','wrong_base','bits','custom','foreign_member','unexpected_field','missing_sibling','missing_integer_flag'])
def test_ambiguous_or_unproven_shapes_rejected(mutation):
    t=PresetTree()
    if mutation=='duplicate_parent':
        k=t.put('Preset','SwaC');t.nodes[k]=deepcopy(t.group);t.nodes[k].set('Id',k[2])
    elif mutation=='duplicate_item':t.group.append(deepcopy(t.group.findall('Item')[0]))
    elif mutation=='mixed_explicit':E.SubElement(t.nodes[('SwaC','PresetValue',IDS[0])],'Value').text='9'
    elif mutation=='wrong_base':t.group.find('BaseType').set('Value','fixed')
    elif mutation=='bits':E.SubElement(t.group,'PresetAsBits')
    elif mutation=='custom':E.SubElement(t.group,'PresetCustom')
    elif mutation=='foreign_member':t.group.findall('Item')[0].set('Library','Other')
    elif mutation=='unexpected_field':E.SubElement(t.group,'ScriptCode').text='bad'
    elif mutation=='missing_sibling':del t.nodes[('SwaC','PresetValue',IDS[0])]
    else:t.group.remove(t.group.find('PresetInteger'))
    with pytest.raises((SC2Error,KeyError)):t.value(2)

@pytest.mark.parametrize('value',['17','-2','c_someSymbol','"quoted"'])
def test_existing_explicit_value_behavior_preserved(value):
    t=PresetTree();E.SubElement(t.nodes[('SwaC','PresetValue',IDS[2])],'Value').text=value;assert t.value(2)==value

@pytest.mark.parametrize('mutation',['double_base','foreign_parent_type','foreign_parent_library','item_attribute','bad_default','two_defaults'])
def test_strict_parent_and_default_metadata(mutation):
    t=PresetTree()
    if mutation=='double_base':E.SubElement(t.group,'BaseType',Value='int')
    elif mutation=='foreign_parent_type':
        group=t.nodes.pop(('SwaC','Preset','15CE809C'));t.nodes[('SwaC','Category','15CE809C')]=group
    elif mutation=='foreign_parent_library':
        group=t.nodes.pop(('SwaC','Preset','15CE809C'));t.nodes[('Other','Preset','15CE809C')]=group
    elif mutation=='item_attribute':t.group.find('Item').set('Unknown','1')
    elif mutation=='bad_default':t.nodes[('SwaC','PresetValue',IDS[1])].find('DefinesDefault').set('Unknown','1')
    else:E.SubElement(t.nodes[('SwaC','PresetValue',IDS[0])],'DefinesDefault')
    with pytest.raises((SC2Error,KeyError)):t.value(2)
