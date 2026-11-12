"""Source-bound Catalog field literals and the exact B98370 game-link string cast.

Literal cases originated in the reviewed DeepSeek candidate. Cast acceptance uses
an independent counted expression emitter and an official GUI-header snapshot;
full native binding is separately exercised by the isolated SaveBank archive.
"""
import json
import unittest
import copy
import pytest
import xml.etree.ElementTree as ET
from sc2_mcp import trigger_codegen as _MODULE
from sc2_mcp.errors import SC2Error
_SC2Error=SC2Error
E=ET
class _StubBindings(object):
    """Minimal binding stub: only `aliases` is consulted by the literal branch."""

    def __init__(self, aliases):
        self.aliases = dict(aliases)

    def type(self, e, d, key, tag):  # pragma: no cover - not reached by literals
        raise AssertionError('stub must not be asked for a type mapping')

    def bind(self, *args, **kwargs):  # pragma: no cover - not reached by literals
        raise AssertionError('stub must not be asked to bind')


class _Node(object):
    """Stand-in for the target node object Generator.expr only uses via d.path."""

    path = 'stub/Triggers/UnitLiteral.SC2Map'

    def __init__(self, root):
        self.root = root

    def __getattr__(self, name):
        raise AttributeError(name)


def _expr(xml_text, aliases=None):
    if aliases is None:
        aliases = {'userfield': 'string', 'userinstance': 'string',
                   'catalogfieldpath': 'string'}
    root = ET.fromstring(xml_text)
    gen = _MODULE.Generator(target=None, bindings=_StubBindings(aliases))
    return gen.expr(_Node(root), ('', 'Param', '5DD823DA'), root)


CONTRACT_PARAM = ('<Element Type="Param" Id="5DD823DA">'
                  '<ParameterDef Type="ParamDef" Library="Ntve" Id="00000749"/>'
                  '<Value>Name</Value><ValueType Type="catalogfieldpath"/>'
                  '<ValueContext Value="CUpgrade"/></Element>')


class CatalogFieldPathAccepted(unittest.TestCase):

    def test_contract_exact_gui_param(self):
        self.assertEqual(_expr(CONTRACT_PARAM), '"Name"')

    def test_indexed_array_field_path(self):
        xml = ('<Element Type="Param" Id="P1"><Value>AbilArray[3].Name</Value>'
               '<ValueType Type="catalogfieldpath"/>'
               '<ValueContext Value="CAbil"/></Element>')
        self.assertEqual(_expr(xml), '"AbilArray[3].Name"')

    def test_json_escaped_text(self):
        xml = ('<Element Type="Param" Id="P2"><Value>Name"\\\t</Value>'
               '<ValueType Type="catalogfieldpath"/>'
               '<ValueContext Value="CUpgrade"/></Element>')
        out = _expr(xml)
        import json as _json
        self.assertEqual(_json.loads(out), 'Name"\\\t')

    def test_existing_aliases_still_accepted(self):
        for alias in ('userfield', 'userinstance'):
            xml = ('<Element Type="Param" Id="P3"><Value>K</Value>'
                   '<ValueType Type="%s"/>'
                   '<ValueContext Value="X"/></Element>' % alias)
            self.assertEqual(_expr(xml), '"K"')

    def test_comment_and_paramdef_allowed_shape(self):
        xml = ('<Element Type="Param" Id="P4">'
               '<ParameterDef Type="ParamDef" Library="Ntve" Id="00000749"/>'
               '<Value>Name</Value><ValueType Type="catalogfieldpath"/>'
               '<ValueContext Value="CUpgrade"/><Comment>c</Comment></Element>')
        self.assertEqual(_expr(xml), '"Name"')


class CatalogFieldPathRejected(unittest.TestCase):

    def assertRejected(self, xml_text, aliases=None):
        with self.assertRaises(_SC2Error) as cm:
            _expr(xml_text, aliases)
        self.assertEqual(cm.exception.code if hasattr(cm.exception, 'code')
                         else getattr(cm.exception, 'kind', None),
                         'trigger_generation_unsupported')

    def test_missing_context(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/></Element>')

    def test_multiple_contexts(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/>'
                            '<ValueContext Value="CUnit"/></Element>')

    def test_unknown_attribute_on_element(self):
        self.assertRejected('<Element Type="Param" Id="P1" Foo="bar"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')

    def test_unknown_attribute_on_context(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade" Extra="1"/></Element>')

    def test_unknown_attribute_on_valuetype(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath" X="1"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')

    def test_value_with_attribute(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value A="1">Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')

    def test_extra_child_element(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/>'
                            '<ValueId Id="7"/></Element>')

    def test_context_with_child_element(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"><X/></ValueContext></Element>')

    def test_empty_value(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>   </Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')

    def test_empty_context(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value=" "/></Element>')

    def test_unmapped_alias(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>',
                            aliases={'userfield': 'string', 'userinstance': 'string'})

    def test_alias_mismatch_not_string(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>',
                            aliases={'catalogfieldpath': 'int'})

    def test_unknown_type_still_rejected(self):
        self.assertRejected('<Element Type="Param" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpathx"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')

    def test_wrong_element_type(self):
        self.assertRejected('<Element Type="Variable" Id="P1"><Value>Name</Value>'
                            '<ValueType Type="catalogfieldpath"/>'
                            '<ValueContext Value="CUpgrade"/></Element>')



source=E.fromstring('<Evidence>\n  <Element Type="FunctionDef" Id="E4B86923">\n    <Identifier>StringToText2</Identifier>\n    <Label Type="Label" Library="Ntve" Id="00000014" />\n    <FlagCall />\n    <FlagOperator />\n    <ReturnType>\n      <Type Value="string" />\n    </ReturnType>\n    <Parameter Type="ParamDef" Library="Ntve" Id="711D5A26" />\n  </Element>\n  <Element Type="ParamDef" Id="711D5A26">\n    <Identifier>val</Identifier>\n    <ParameterType>\n      <Type Value="anygamelink" />\n    </ParameterType>\n  </Element>\n  <Element Type="Label" Id="00000014">\n    <Icon>Assets\\Textures\\ui-editoricon-triggercategories_conversion.dds</Icon>\n  </Element>\n</Evidence>')
F=('Ntve','FunctionDef','E4B86923');P=('Ntve','ParamDef','711D5A26');L=('Ntve','Label','00000014');C=('A431EF10','FunctionCall','TEST');A=('A431EF10','Param','ARG')
class Doc:
 path='official-slice/NativeLib.TriggerLib';sha256='source-bound-unit-test';standard='Ntve'
 def __init__(self,nodes):self.elements=nodes
 def name(self,k):return self.elements[k].findtext('Identifier') or k[2]
class Bind:
 def __init__(self,alias):self.aliases={'anygamelink':alias};self.used=[]
 def raw_type(self,n,d,k,tag):
  x=n.find(tag+'/Type');return x.get('Value') if x is not None else None
 def type(self,n,d,k,tag):
  raw=self.raw_type(n,d,k,tag);return self.aliases.get(raw,raw)
class Target:
 def __init__(self,d):self.d=d
 def resolve(self,k,d):return self.d,self.d.elements[k]
class Gen(_MODULE.Generator):
 def expr(self,d,k,n):self.evaluated+=1;assert k==A;return 'ExactlyOnce()'
def exercise(mutation=None,statement=False,alias='string',foreign=False):
 nodes={(n.get('Type'),n.get('Id')):copy.deepcopy(n) for n in source}
 fd=nodes[F[1:]];pd=nodes[P[1:]]
 if mutation:mutation(fd,pd)
 fk=('Ntve','FunctionDef','OTHER') if foreign else F
 data={fk:fd,P:pd,L:nodes[L[1:]]}
 arg=E.fromstring('<Element Type="Param" Id="ARG"><ParameterDef Type="ParamDef" Library="Ntve" Id="711D5A26"/></Element>');data[A]=arg
 call=E.fromstring('<Element Type="FunctionCall" Id="TEST"><FunctionDef Type="FunctionDef" Library="Ntve" Id="'+fk[2]+'"/><Parameter Type="Param" Library="A431EF10" Id="ARG"/></Element>');data[C]=call
 d=Doc(data);b=Bind(alias);g=Gen(Target(d),bindings=b);g.evaluated=0;out=g._call(d,C,call,statement)
 return out,g.evaluated,b.used

def test_exact_official_cast_evaluates_argument_once():
    out,count,used=exercise()
    assert out=='(ExactlyOnce())' and count==1 and len(used)==1

@pytest.mark.parametrize('mutation', [
    lambda f,p:setattr(f.find('Identifier'),'text','WrongCast'),
    lambda f,p:f.remove(f.find('FlagCall')),
    lambda f,p:f.remove(f.find('FlagOperator')),
    lambda f,p:f.find('FlagCall').set('Unknown','1'),
    lambda f,p:f.find('ReturnType/Type').set('Value','int'),
    lambda f,p:E.SubElement(f,'ScriptCode'),
    lambda f,p:f.find('Label').set('Id','OTHER'),
    lambda f,p:setattr(p.find('Identifier'),'text','wrong'),
    lambda f,p:p.find('ParameterType/Type').set('Value','int'),
    lambda f,p:E.SubElement(p,'Unknown'),
    lambda f,p:E.SubElement(f,'Unknown'),
])
def test_official_cast_signature_mutations_fail_closed(mutation):
    with pytest.raises(SC2Error) as error:
        exercise(mutation)
    assert error.value.code=='trigger_generation_unsupported'

@pytest.mark.parametrize('kwargs', [{'statement':True},{'alias':'int'},{'alias':None}])
def test_official_cast_invalid_context_rejected(kwargs):
    with pytest.raises(SC2Error) as error:
        exercise(**kwargs)
    assert error.value.code=='trigger_generation_unsupported'

def test_foreign_identity_never_uses_passthrough():
    out,count,used=exercise(foreign=True)
    assert out!='(ExactlyOnce())' and not used
