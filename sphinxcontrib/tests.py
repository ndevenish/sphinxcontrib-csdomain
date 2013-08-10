# coding: utf-8

import unittest
from csdomain import DefinitionParser, PropertyInfo

class TestDefinitionParser(unittest.TestCase):
  def testInit(self):
    a = DefinitionParser("")

  def testLongClass(self):
    data = "protected class ViewModel<T, Q> : IViewModel, IEditableObject, INotifyDataErrorInfo where T : class, IModelClass, new()"
    parser = DefinitionParser(data)
    cl = parser.parse_classlike()
    self.assertEqual(cl._name, "ViewModel")
    self.assertEqual([x.fqn() for x in cl._bases], ['IViewModel', 'IEditableObject', 'INotifyDataErrorInfo'])
    self.assertEqual(cl.visibility, "protected")
    self.assertEqual(cl.static, False)
    self.assertEqual(cl._classlike_category, "class")
    self.assertEqual(cl._type_parameters, ['T', 'Q'])
    self.assertTrue(cl._type_parameter_constraints)

  def testStaticClass(self):
    cl = DefinitionParser('static class TC').parse_classlike()
    self.assertTrue(cl.static)

  def testInterfaceBasics(self):
    cl = DefinitionParser('public interface ITC').parse_classlike()
    self.assertEqual(cl._classlike_category, "interface")

  def testInterfaceWithBase(self):
    cl = DefinitionParser('public interface ITC : IViewModel').parse_classlike()
    assert ["IViewModel"] == [x.fqn() for x in cl._bases]


  def testMethodMember(self):
    data = "public void SetError(bool hasError, string description = null, [CallerMemberName] string property = null)"
    m = DefinitionParser(data).parse_member()
    self.assertEqual("SetError", m._name)
    self.assertEqual("void", str(m._type))
    self.assertTrue("public" in m._modifiers)
    self.assertEqual(3, len(m._arguments))

  def testPropertyMember(self):
    p = DefinitionParser("public bool HasErrors { get; private set; }").parse_member()
    self.assertEqual("HasErrors", p._name)
    self.assertTrue(type(p) is PropertyInfo)
    self.assertIsNotNone(p._getter)
    self.assertIsNotNone(p._setter)
    self.assertIsNone(p._getter._visibility)
    self.assertEqual(p._setter._visibility, "private")

    p = DefinitionParser("public bool HasErrors { get; }").parse_member()
    self.assertIsNone(p._setter)

  def testClassNamespacing(self):
    cl = DefinitionParser("public class test.namespace.ViewModel").parse_classlike()
    assert cl._name == "ViewModel"
    self.assertEqual(cl._full_name.fqn(), "test.namespace.ViewModel")

  def testQualifiedMember(self):
    mi = DefinitionParser("public bool ViewModel.HasErrors()").parse_member()
    self.assertEqual(mi._name, "HasErrors")
    self.assertEqual(mi._full_name.fqn(), "ViewModel.HasErrors")

  def testBadconstructor(self):
    mi = DefinitionParser("public DBPreflight(LoginDetails details)").parse_member()
    self.assertEqual(mi._member_category, 'constructor')
    self.assertEqual(mi._name, "DBPreflight")
    self.assertEqual(len(mi._arguments), 1)
    arg = mi._arguments[0]
    self.assertEqual(arg['type']._name, 'LoginDetails')
    self.assertEqual(arg['name'], 'details')

class TestParts(unittest.TestCase):
  def testNamespace(self):
    dp = DefinitionParser("test.namespace.ViewModel")
    tn = dp._parse_type_name()
    self.assertEqual(tn._name, "ViewModel")
    self.assertEqual(tn.fqn(), "test.namespace.ViewModel")