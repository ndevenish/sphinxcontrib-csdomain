# coding: utf-8

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
  _strip = True
  form = ""

  def __init__(self, name, form = None):
    self.parts = []
    self.definitionname = name
    if form:
      self.form = form

  def __str__(self):
    return self.form

  def __repr__(self):
    return "<{}: {}>".format(self.definitionname, str(self))

class Whitespace(NamedDefinition):
  def __repr__(self):
    return "<{}>".format(self.definitionname)

  @property
  def lines(self):
    return len(self.form.splitlines())

class Comment(NamedDefinition):
  definitionname = "comment"
  def __init__(self, comment):
    self.parts = [comment]
    self.form = "// " + comment
  def __repr__(self):
    return "<{}>".format(self.definitionname)
  
  @property
  def is_documentation(self):
    return self.parts[0].startswith("/")

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

class Space(NamedDefinition):
  members = None
  using = None
  extern_alias = None
  attributes = None
  name = None
  documentation = None

  def __init__(self, name, form=None):
    super(Space, self).__init__(name, form)
    self.members = []
    self.using = []
    self.extern_alias = []
    self.attributes = []
    self.namespace = ""

  def __str__(self):
    if self.name:
      return self.name
    return self.form

class Class(Space):
  bases = None

  def __init__(self, name, form=None):
    super(Class, self).__init__(name, form)
    bases = []
  
  def __str__(self):
    return self.name

class Statement(NamedDefinition):
  pass

class Attribute(NamedDefinition):
  pass

class Member(NamedDefinition):
  name = None
  attributes = []
  modifiers = []
  documentation = None

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
      comment_val = self.core.skip_to_eol()
      # This swallows the whitespace, which we do not want. Reset.
      self.core.backout()
      comment = Comment(comment_val)
      comment.whitespace = self.parse_whitespace()
      return comment

    return None

  def parse_whitespace(self):
    if self.core.skip_ws():
      return Whitespace('whitespace', self.core.matched_text)

def coalesce_comments(members):
  """Coalesces consecutive comments"""
  new_mems = []
  prev_comment = None
  for member in members:
    # print "  Processing " + str(member)
    if type(member) is Comment:
      if prev_comment:
        # print "    - Appending comment to previous"
        assert prev_comment.parts is not member.parts
        prev_comment.parts.extend(member.parts)
        prev_comment.whitespace = member.whitespace
      else:
        # print "    - Starting new comment run"
        prev_comment = member
    else:
      # print "    - not a comment"
      # Not a comment. Flush any prev, then append
      if prev_comment:
        # print "    - Flushing previous comment due to not comment"
        if prev_comment.is_documentation:
          # print "    - Attaching comment as documentation"
          member.documentation = prev_comment
        # new_mems.append(prev_comment)
          prev_comment = None
      new_mems.append(member)
    # Flush the prev_comment if needed
    if prev_comment and prev_comment.whitespace.lines > 2:
      # print "    - previous Comment has more than one newline; flushing"
      new_mems.append(prev_comment)
      prev_comment = None
  return new_mems

def summarize_space(space, level=0):
  prefix = "  " * level
  doc = bool(space.documentation)
  info = "{}{}{}".format(prefix, "", repr(space))
  print "{}{}".format(info.ljust(75), doc)
  if not hasattr(space, "members"):
    return
  for member in space.members:
    summarize_space(member, level+1)