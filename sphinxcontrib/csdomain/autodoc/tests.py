# coding: utf-8

import unittest
from .parser import FileParser, opensafe
from .lexical import Comment, summarize_space
from .core import CoreParser
import glob
import os

SAMPLE = "/Users/xgkkp/dockets/app/Core/Utils/DBPreflight.cs"

class TestAutodoc(unittest.TestCase):
  def test_read(self):
    contents = opensafe(SAMPLE).read()
    parser = FileParser(contents)
    # parser._debug = True
    # parser.parse_file()
    cu = parser.parse_file()

    # print 
    # for cls in cu.iter_classes():
    #   print "Class: {}".format(cls.name)
    #   print "  Doc? {}".format(bool(cls.documentation))
    #   print str(cls.documentation)

  def test_eol(self):
    parser = FileParser("Some text to the end\nof the line")
    self.assertEqual(parser.core.skip_to_eol(), "Some text to the end")
    self.assertEqual(parser.core.definition[parser.core.pos:], "of the line")

  def test_comment(self):
    parser = FileParser("// Some text to the end\nof the line")
    comment = parser.lex.parse_comment()
    self.assertIs(type(comment), Comment)
    self.assertEqual(parser.core.definition[parser.core.pos:], "of the line")

  def test_qual_ident(self):
    p = FileParser("a.b.something.c and then..")
    out = p._parse_qualified_identifier()
    self.assertEqual(out, "a.b.something.c")

  def test_parse_class_decl(self):
    p = FileParser('protected class ViewModel<T, Q> : IViewModel, IEditableObject, INotifyDataErrorInfo where T : class, IModelClass, new() { }')
    p._parse_class_declaration_header()

  def test_parse_type(self):
    p = FileParser('string')
    p._parse_type()

  def test_skip_to(self):
    p = CoreParser("some text with a d) in the")
    self.assertEqual(p.skip_to_char(')'), "some text with a d")

  def test_new_expr(self):
    p = FileParser("var x = new []{}()something(withpar);")
    p._parse_balanced_expression()
    self.assertEqual(p.core.next_char, ';')

  def test_parsing_xmldoc(self):
    # doc = ["/ <summary>", "/ Contains methods to probe various details about a database, without attempting", "/ to connect proper, i.e. avoiding NHibernate.", "/ </summary>"]
    doc = ['/ <summary>', '/ Initialise with only a hostname and port', '/ </summary>', '/ <param name="hostname">The hostname to connect to</param>', '/ <param name="port">The port to connect to</param>', '/ <remarks>This method can be useful when checking for server existence</remarks><returns>Some value</returns>']
    c = Comment()
    c.parts = doc
    self.assertTrue(c.is_documentation)
    doc = c.parse_documentation()

  def test_another_read(self):
    filename = "/Users/xgkkp/dockets/app/Core/Utils/DB.cs"
    contents = opensafe(filename).read()
    parser = FileParser(contents)
    # parser._debug = True
    # parser.parse_file()
    cu = parser.parse_file()
    # summarize_space(cu)

    # Try and read the documentation for every class
    for cls in cu.iter_classes():
      if cls.documentation:
        cls.documentation.parse_documentation()

  def test_parse_array_type(self):
    tp = "string[]"
    p = FileParser(tp)
    p._parse_type()
    self.assertTrue(p.core.eof)

  def test_generic_new(self):
    p = FileParser("class Test<T> where T : new() { }")
    cls = p._parse_class_declaration()
    self.assertIsNotNone(cls)

  def test_parse_parameter_constraints(self):
    p = FileParser("where T : new()")
    p._parse_type_parameter_constraints_clause()
    self.assertTrue(p.core.eof)

  def test_static_constructor(self):
    p = FileParser("static ConstructorName(){}")
    cons = p._parse_constructor_declaration()
    self.assertIsNotNone(cons)
    self.assertIn('static-constructor-declaration', cons.definitions)

  def test_parse_double(self):
    p = FileParser('double')
    self.assertIsNotNone(p._parse_simple_type())
    p.core.pos = 0
    self.assertIsNotNone(p._parse_type())

  # def test_field(self):
  #   p = FileParser("private readonly double PointsPerCharacter;")
  #   import pdb
  #   pdb.set_trace()
  #   f = p._parse_field_declaration()
  #   self.assertIsNotNone(f)

  def test_whole_tree(self):
    return
    files = set()
    for (dirpath, _, filenames) in os.walk("/Users/xgkkp/dockets/app/"):
      for filename in filenames:
        if filename.endswith(".cs"):
          files.add(os.path.join(dirpath, filename))
    # print files
    # return
    # pattern = "/Users/xgkkp/dockets/app/Core/Utils/*.cs"
    for filename in files:#[x for x in files if "SiteConfiguration.cs" in x]:
      print "================="
      print "Parsing " + os.path.basename(filename)
      contents = opensafe(filename).read()
      parser = FileParser(contents)
      parser._debug = False
      cu = parser.parse_file()
      summarize_space(cu)

  def test_assemblyinfo(self):
    p = FileParser('[assembly: AssemblyTitle("StylePackCore")]')
    # import pdb
    # pdb.set_trace()
    self.assertIsNotNone(p.parse_file())

  def test_ops(self):
    p = FileParser("+")
    oop = p.lex.parse_operator_or_punctuator()
    self.assertIsNotNone(oop)
    self.assertEqual(str(oop), "+")
    p = FileParser("::+")
    oop = p.lex.parse_operator_or_punctuator()
    self.assertIsNotNone(oop)
    self.assertEqual(str(oop), "::")

  def test_qualified_identifier(self):
    p = FileParser("global::System.Runtime.CompilerServices.CompilerGeneratedAttribute")
    p._parse_type_name()
    self.assertTrue(p.core.eof)

  def test_property_generic(self):
    p = FileParser("SomeType<string> PropertyName { get; }")
    # import pdb
    # pdb.set_trace()
    # p._parse_namespace_or_type_name()
    p._parse_property_declaration()
    self.assertTrue(p.core.eof)

  # def test_generic_indexer(self):
  #   p = FileParser("TValue IDictionary<TKey, TValue>.this[TKey key] { get; }")
  #   # import pdb
  #   # pdb.set_trace()
  #   p._parse_indexer_declaration()
  #   self.assertTrue(p.core.eof)

  def test_indexer_interface_prefix(self):
    """Tests swallowing of trailing . does not occur"""
    p = FileParser("IDictionary<TKey, TValue>.this")
    # import pdb
    # pdb.set_trace()
    p._parse_interface_type()
    self.assertEquals(p.cur_line(), ".this")

  def test_parse_eof_comment(self):
    p = FileParser("// Some long comment")
    p.lex.parse_comment()
    self.assertTrue(p.core.eof)

  def testfailingdependencyprop(self):
    # p = FileParser('public static readonly DependencyProperty IconProperty = DependencyProperty.Register("Icon", typeof(Uri), typeof(EditorBase), new PropertyMetadata(new Uri("pack://application:,,,/StylePack;component/StylePack.ico")));')
    p = FileParser('IconProperty = DependencyProperty.Register("Icon", typeof(Uri), typeof(EditorBase), new PropertyMetadata(new Uri("pack://application:,,,/StylePack;component/StylePack.ico")));')
    p._parse_variable_declarator()
    self.assertEqual(p.core.pop_char(), ";")
    self.assertTrue(p.core.eof)

  def test_string_literal(self):
    p = FileParser('"this is a string"')
    self.assertEqual(str(p.lex.parse_string_literal()), "this is a string")
    p = FileParser(r'"this is an \" escaped string"')
    self.assertEqual(str(p.lex.parse_string_literal()), r"this is an \" escaped string")
    p = FileParser('""')
    self.assertEqual(str(p.lex.parse_string_literal()), r"")
