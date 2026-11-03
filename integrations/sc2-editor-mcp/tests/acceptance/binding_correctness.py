"""Build a new GUI acceptance copy for source-bound signature generation."""
import argparse
import json
from pathlib import Path
import shutil
from gui_matrix import Matrix, node, ref, WORKSPACE
from sc2_mcp.trigger_pipeline import target_for
from sc2_mcp.trigger_writer import plan_write


def prepare(source, destination):
    source = source.resolve()
    destination = destination.resolve()
    if destination.exists() or not destination.is_relative_to(WORKSPACE):
        raise ValueError('destination must be a NEW workspace directory')
    target = target_for(source)
    if target.problems:
        raise ValueError(target.problems)
    matrix = Matrix(target)
    matrix.counter = 0x3000
    preset_type = lambda: [node('Type', {'Value':'preset'}), ref('TypeElement','Preset','1CAA7463','Ntve')]
    flag = matrix.add('Variable', [node('Identifier',text='PresetReady'),node('VariableType',children=preset_type()),
        matrix.reference('Value',matrix.literal_param(True))], name='Preset Ready')
    function = ('','FunctionDef',matrix.ident())
    argument = matrix.add('ParamDef',[node('Identifier',text='Input'),node('ParameterType',children=preset_type())],
        owner={'type':'FunctionDef','id':function[2]})
    local = matrix.add('Variable',[node('Identifier',text='LocalPreset'),node('VariableType',children=preset_type())],
        owner={'type':'FunctionDef','id':function[2]})
    body = [matrix.assign(local,matrix.read(argument)),matrix.call('Return',[matrix.read(local)])]
    matrix.add('FunctionDef',[node('Identifier',text='PresetIdentity'),node('FlagCall'),
        node('ReturnType',children=preset_type()),matrix.reference('Parameter',argument),matrix.reference('Variable',local)] +
        [matrix.reference('FunctionCall',c) for c in body],ident=function[2],name='Preset Identity')
    matrix.defs[function]=[argument]
    point_name = next(name for name,key in matrix.native.items()
                      if name=='Point' and len(matrix.defs[key])==2)
    def point():
        return matrix.expression(point_name,[matrix.value(0),matrix.value(0)])
    legacy=('Ntve','FunctionDef','00000250')
    modern=('Ntve','FunctionDef','2E7FB833')
    legacy_value=matrix.expression(legacy,[matrix.value(1),point()])
    modern_value=matrix.expression(modern,[matrix.value(1),point(),[node('Value',text='PowerSource'),node('ValueType',{'Type':'string'})]])
    ok=matrix.variable('BindingAllPassed','bool',initial=True)
    actions=[matrix.assign(flag,matrix.expression(function,[matrix.read(flag)])),
        matrix.verify(matrix.compare(matrix.read(flag),'==',matrix.value(True)),'PRESET',ok),
        matrix.verify(matrix.compare(legacy_value,'==',modern_value),'POWER_COMPAT',ok),
        matrix.branch(matrix.compare(matrix.read(ok),'==',matrix.value(True)),
            [matrix.message('GUI_BINDING_ALL_PASS')],[matrix.message('GUI_BINDING_ALL_FAIL')])]
    event=matrix.call('TriggerAddEventMapInit')
    condition=matrix.compare(matrix.read(flag),'==',matrix.value(True))
    matrix.add('Trigger',[node('Identifier',text='BindingCorrectness'),matrix.reference('Event',event),
        matrix.reference('Condition',condition)]+[matrix.reference('Action',c) for c in actions],name='Binding Correctness')
    operations=sorted(matrix.ops,key=lambda o:0 if o['type'] in {'FunctionDef','Trigger','Category'} else 1)
    changes=plan_write(source,operations,locale='zhCN')
    shutil.copytree(source,destination)
    for relative,raw in changes.items():
        path=destination/relative
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(raw)
    return {'source':str(source),'map':str(destination),'expected':['GUI_MATRIX_PRESET_PASS','GUI_MATRIX_POWER_COMPAT_PASS','GUI_BINDING_ALL_PASS']}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(prepare(args.source,args.destination),indent=2))
