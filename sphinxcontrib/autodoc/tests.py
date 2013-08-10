# coding: utf-8

import unittest
from .parser import FileParser, CommentInfo, opensafe

SAMPLE = "/Users/xgkkp/dockets/app/Core/Utils/DBPreflight.cs"

class TestAutodoc(unittest.TestCase):
  def test_read(self):
    contents = opensafe(SAMPLE).read()
    parser = FileParser(contents)
    # parser.parse_file()
    parser.parse_file()

  def test_eol(self):
    parser = FileParser("Some text to the end\nof the line")
    self.assertEqual(parser.skip_to_eol(), "Some text to the end")
    self.assertEqual(parser.definition[parser.pos:], "of the line")

  def test_comment(self):
    parser = FileParser("// Some text to the end\nof the line")
    comment = parser._parse_comment()
    self.assertIs(type(comment), CommentInfo)
    self.assertEqual(parser.definition[parser.pos:], "of the line")

  def test_qual_ident(self):
    p = FileParser("a.b.something.c and then..")
    out = p._parse_qualified_identifier()
    self.assertEqual(out, "a.b.something.c")

