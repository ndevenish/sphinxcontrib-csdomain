# coding: utf-8

import unittest
from .parser import FileParser, opensafe
from .lexical import Comment
from .core import CoreParser

SAMPLE = "/Users/xgkkp/dockets/app/Core/Utils/DBPreflight.cs"

class TestAutodoc(unittest.TestCase):
  def test_read(self):
    contents = opensafe(SAMPLE).read()
    parser = FileParser(contents)
    # parser.parse_file()
    parser.parse_file()

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