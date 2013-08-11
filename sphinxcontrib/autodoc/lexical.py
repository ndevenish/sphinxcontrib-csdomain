
import re

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')

KEYWORDS = ("abstract", "byte", "class", "delegate", "event", 
  "fixed", "if", "internal", "new", "override", "readonly", 
  "short", "struct", "try", "unsafe", "volatile", "as", 
  "case", "const", "do", "explicit", "float", "implicit", 
  "is", "null", "params", "ref", "sizeof", "switch", "typeof", 
  "ushort", "while", "base", "bool", "catch", "char", "continue", 
  "decimal", "double", "else", "extern", "false", "for", "foreach",
  "in", "int", "lock", "long", "object", "operator", "private", 
  "protected", "return", "sbyte", "stackalloc", "static", 
  "this", "throw", "uint", "ulong", "using", "virtual", "break", 
  "checked", "default", "enum", "finally", "goto", "interface", 
  "namespace", "out", "public", "sealed", "string", "true", 
  "unchecked", "void")


class NamedDefinition(object):
  definitionname = None
  parts = []
  _strip = True
  form = ""

  def __init__(self, name, form = None):
    self.definitionname = name
    if form:
      self.form = form

  def __str__(self):
    return self.form

  def __repr__(self):
    return "<{}: {}>".format(self.definitionname, str(self))

class Comment(NamedDefinition):
  definitionname = "comment"
  def __init__(self, comment):
    self.parts.append(comment)
    self.form = "// " + comment

class SeparatedNameList(NamedDefinition):
  def __init__(self, name, separator = " "):
    super(SeparatedNameList, self).__init__(name)
    self.separator = separator

  def __str__(self):
    return self.separator.join(self.parts)

class CommaNameList(SeparatedNameList):
  def __init__(self, name):
    super(SeparatedNameList, self).__init__(name, ", ")

class TypeName(NamedDefinition):
  arguments = []

class Block(NamedDefinition):
  def __str__(self):
    return "{" + ";\n".join(self.parts) + "}"

class FormalParameter(NamedDefinition):
  pass

class TypeParameterList(SeparatedNameList):
  def __init__(self):
    super(TypeParameterList, self).__init__("type-parameter-list", ", ")

  def __str__(self):
    return "<" + self.separator.join(self.parts) + ">"

class Statement(NamedDefinition):
  pass

class Attribute(NamedDefinition):
  pass
class Member(NamedDefinition):
  name = None
  attributes = []
  modifiers = []

class LexicalParser(object):
  core = None

  def __init__(self, parser):
    self.core = parser

  def savepos(self):
    return self.core.savepos()

  def restorepos(self, state):
    self.core.restorepos(state)

  def parse_identifier_or_keyword(self):
    state = self.core.savepos()
    prefix = self.core.skip('@')
    if not self.core.match(_identifier_re):
      self.core.restorepos(state)
      return None
    ident = self.core.matched_text
    self.core.skip_ws()
    if prefix:
      return "@" + ident
    return ident

  def parse_identifier(self):
    state = self.core.savepos()
    
    ident = self.parse_identifier_or_keyword()
    if not ident:
      return None
    if not ident.startswith("@"):
      if ident[1:] in KEYWORDS:
        self.core.restorepos(state)
        return None
    return ident

  def parse_comment(self):
    if self.core.skip('//'):
      return Comment(self.core.skip_to_eol())
    return None