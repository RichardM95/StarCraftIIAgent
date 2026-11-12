"""Editor annotations inside action lists are not executable branch calls."""
import unittest
import xml.etree.ElementTree as ET
from sc2_triggers import validate_call


class CommentChildrenTests(unittest.TestCase):
    def check_child(self,kind,body):
        definition=ET.fromstring('<Element><SubFunctionType Type="SubFuncType" Library="Ntve" Id="THEN"/></Element>')
        call=ET.fromstring('<Element><FunctionDef Type="FunctionDef" Library="Ntve" Id="IF"/><FunctionCall Type="'+kind+'" Id="CHILD"/></Element>')
        child=ET.fromstring('<Element>'+body+'</Element>')
        nodes={('Ntve','FunctionDef','IF'):definition,(None,kind,'CHILD'):child}
        def resolve(key,document):return document,nodes[key]
        return validate_call(call,(None,'FunctionCall','PARENT'),object(),resolve)

    def test_comment_annotations_do_not_require_an_execution_branch(self):
        self.assertEqual(self.check_child('Comment','<Comment>HINT</Comment>'),[])
        self.assertEqual(self.check_child('Comment','<Comment>Note</Comment><SubFunctionType Type="SubFuncType" Library="Ntve" Id="LEGACY"/>'),[])

    def test_executable_children_still_require_the_exact_branch(self):
        self.assertIn('invalid SubFunctionType',' '.join(self.check_child('FunctionCall','')))
        self.assertIn('invalid SubFunctionType',' '.join(self.check_child('FunctionCall','<SubFunctionType Type="SubFuncType" Library="Ntve" Id="OTHER"/>')))


if __name__=='__main__':unittest.main()
