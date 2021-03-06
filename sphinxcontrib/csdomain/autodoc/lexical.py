# coding: utf-8

import re
import codecs
from .xmldoc import XmldocParser

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')
_doc_comment_skip_re = re.compile(r'^[\s/]*')
_decimal_digits_re = re.compile(r'[0-9]+')
_hex_digits_re = re.compile(r'[0-9a-fA-F]+')

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

OPERATOR_OR_PUNCTUATOR = [
  '{', '}', '[', ']', '(', ')', '.', ',', ':', ';', '+', '-', '*', '/', '%',
  '&', '|', '^', '!', '~', '=', '<', '>', '?',
  '??', '::', '++', '--', '&&', '||', '->', '==', '!=', '<=', '>=', '+=',
  '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<', '=>', '<<=']

class NamedDefinition(object):
  definitionname = None
  _strip = True
  form = ""
  definitions = None
  def __init__(self, name, form = None):
    self.parts = []
    self.comps = {}
    self.definitionname = name
    self.definitions = [name]
    self.documentation = None
    if form:
      self.form = form

  def adddef(self, name):
    self.definitions.append(name)

  def __str__(self):
    return self.form

  def __repr__(self):
    return codecs.utf_8_encode(
      u"<{}: {}>".format(self.definitionname, unicode(self)))[0]

class Directive(NamedDefinition):
  pass

class Whitespace(NamedDefinition):
  def __repr__(self):
    return "<{}>".format(self.definitionname)

  @property
  def lines(self):
    return len(self.form.splitlines())

class Comment(NamedDefinition):
  definitionname = "comment"
  documentation = None
  def __init__(self, comment = None):
    self.parts = []
    if comment:
      self.parts = [comment]
      self.form = "// " + comment
  def __repr__(self):
    return "<{}>".format(self.definitionname)
  def __str__(self):
    return "\n".join("//{}".format(x) for x in self.parts)
  
  @property
  def is_documentation(self):
    return self.parts[0].startswith("/")

  def parse_documentation(self):
    # Grab the leading indentation from the first line
    index = len(_doc_comment_skip_re.match(self.parts[0]).group())
    # Strip this from the others
    stripped = [x[index:] for x in self.parts]
    # Rejoin these
    fulltext = "\n".join(stripped)
    return XmldocParser(fulltext).parse()


class SeparatedNameList(NamedDefinition):
  def __init__(self, name, separator = " "):
    super(SeparatedNameList, self).__init__(name)
    self.separator = separator

  def __str__(self):
    return self.separator.join(str(x) for x in self.parts)

class CommaNameList(SeparatedNameList):
  def __init__(self, name):
    super(SeparatedNameList, self).__init__(name, ", ")

class TypeName(NamedDefinition):
  arguments = []

class Block(NamedDefinition):
  def __str__(self):
    return "{" + ";\n".join(self.parts) + "}"

class FormalParameter(NamedDefinition):
  def __init__(self, name):
    super(FormalParameter, self).__init__(name)
    self.modifier = None
    self.attributes = []
    self.default = None

  def __str__(self):
    parts = []
    if self.attributes:
      parts.append(str(self.attributes))
    if self.modifier:
      parts.append(self.modifier)
    parts.append(self.type)
    parts.append(self.name)
    if self.default:
      parts.append("=")
      parts.append(self.default)
    return (" ".join(str(x) for x in parts))

class ParameterArray(NamedDefinition):
  pass

class TypeParameterList(SeparatedNameList):
  def __init__(self):
    super(TypeParameterList, self).__init__("type-parameter-list", ", ")

  def __str__(self):
    return "<" + self.separator.join(self.parts) + ">"

class TypeArgumentList(SeparatedNameList):
  def __init__(self):
    super(TypeArgumentList, self).__init__("type-argument-list", ", ")

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

  def iter_classes(self):
    for member in self.members:
      # print "Checking " + repr(member)
      if type(member) is Class:
        yield member
      if hasattr(member, "iter_classes"):
        for x in member.iter_classes():
          yield x

class Class(Space):
  bases = None

  def __init__(self, name, form=None):
    super(Class, self).__init__(name, form)
    bases = []
  
  def __str__(self):
    return self.name

  def signature(self):
    sig = []
    if self.attributes:
      print "Don't know how to sign attributes: " + str(self.attributes)
      sig.append("[attributes]")
    sig.extend(self.modifiers)
    sig.append(self.class_type)
    sig.append(self.name)
    if self.bases:
      sig.append(":")
      sig.append(", ".join(str(x) for x in self.bases))
    return " ".join(sig)

class Statement(NamedDefinition):
  pass

class Attribute(NamedDefinition):
  pass

class Member(NamedDefinition):
  name = None
  attributes = None
  modifiers = None
  documentation = None
  def __init__(self, name):
    super(Member, self).__init__(name)
    attributes = []
    modifiers = []
  
  def signature(self):
    return repr(self)

class Method(Member):
  partial = False
  type = False
  def signature(self):
    sig = []
    sig.extend(self.attributes)
    sig.extend(self.modifiers)
    if self.partial:
      sig.append("partial")
    if self.type:
      sig.append(self.type)
    main_sig = str(self.name) + "(" + ", ".join(str(x) for x in self.parameters) + ")"
    sig.append(main_sig)
    return " ".join(str(x) for x in sig)


class Property(Member):
  setter = None
  getter = None
  def signature(self):
    sig = []
    sig.extend(self.attributes)
    sig.extend(self.modifiers)
    sig.append(self.type)
    sig.append(self.name)
    sig.append("{")

    # if "Username" in str(self.name):
    #   import pdb
    #   pdb.set_trace()
    # getter = next(x for x in self.accessors if x.accessor == "get")
    if self.getter:
      sig.extend(self.getter.modifiers)
      sig.append("get;")
    if self.setter:
      sig.extend(self.setter.modifiers)
      sig.append("set;")
    sig.append("}")
    return " ".join(str(x) for x in sig)

class LexicalParser(object):
  core = None

  def __init__(self, parser):
    self.core = parser

  def savepos(self):
    return self.core.savepos()

  def restorepos(self, state):
    self.core.restorepos(state)

  def parse_keyword(self):
    state = self.core.savepos()
    ide = self.parse_identifier_or_keyword()
    if ide in KEYWORDS:
      return ide
    self.core.restorepos(state)
    return None

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
      if ident in KEYWORDS:
        self.core.restorepos(state)
        return None
    return ident

  def parse_comment(self):

    if self.core.skip('//'):
      comment_val = self.core.skip_to_eol()
      # This swallows the whitespace, which we do not want. Reset.
      # self.core.backout()
      if not self.core.eof:
        self.core.pos = self.core.pos - 1
      comment = Comment(comment_val)
      comment.whitespace = self.parse_whitespace()
      return comment
    if self.core.skip("/*"):
      # Eat everything until the next */
      endcomment = self.core.definition[self.core.pos:].find("*/")
      full = self.core.definition[self.core.pos:self.core.pos+endcomment+2]
      self.core.pos = self.core.pos + endcomment + 2
      comment = Comment()
      comment.parts = full.splitlines()
      comment.whitespace = self.parse_whitespace()
      return comment

    return None

  def parse_pp_directive(self):
    # make sure we are at the beginning of the line
    state = self.core.savepos()
    if not self.core.skip_with_ws("#"):
      return None
    self.core.backout()

    # Verified the #, now verify position
    start_pos = self.core.current_line_start_pos()
    if not self.core.definition[start_pos:self.core.pos].strip() == "":
      return None
    self.core.skip_with_ws("#")
    directive = "#" + self.core.skip_to_eol() 
    self.core.skip_ws()
    return Directive("directive-declaration", directive)

  def parse_whitespace(self):
    if self.core.skip_ws():
      return Whitespace('whitespace', self.core.matched_text)

  def parse_input_element(self):
    whitespace = self.parse_whitespace()
    if whitespace:
      return whitespace
    comment = self.parse_comment()
    if comment:
      return comment
    pp = self.parse_pp_directive()
    if pp:
      return pp
    token = self.parse_token()
    if not token:
      self.fail("Could not parse")
    return token
  
  def parse_next_token(self):
    """Parses input elements until the next token is returned"""
    elem = self.parse_input_element()
    while type(elem) in (Whitespace, Comment, Directive):
      elem = self.parse_input_element()
    return elem

  def parse_token(self):
    ident = self.core.first_of([
      self.parse_identifier,
      self.parse_keyword,
      #self.parse_numeric_literal,
      # etc etc
      # integer-literal
      # real-literal
      self.parse_character_literal,
      self.parse_string_literal,
      self.parse_operator_or_punctuator,
      ])
    # ident = self._parse_identifier()
    if not ident:
      self.fail("Could not get token from input")

    return ident

  def parse_integer_literal(self):
    state = self.core.savepos()
    literal = NamedDefinition("integer-literal")
    literal.adddef("decimal-integer-literal")
    # Integer or hex
    ishex = self.core.skip("0x")
    if ishex:
      self.core.backout()
      return self.parse_hexadecimal_integer_literal()
    
    # Read the digits
    if not self.core.match(_decimal_digits_re):
      # Evidently not a decimal
      self.core.restorepos(state)
      return None
    literal.comp['decimal-digits'] = self.core.matched_text
    literal.comp['integer-type-suffix'] = self.parse_integer_type_suffix()
    return literal

  def parse_hexadecimal_integer_literal(self):
    state = self.core.savepos()
    literal = NamedDefinition("integer-literal")
    literal.adddef("hexadecimal-integer-literal")
    if not self.core.match( _hex_digits_re):
      self.core.restorepos(state)
      return None
    literal.comp['hex-digits'] = self.core.matched_text
    literal.comp['integer-type-suffix'] = self.parse_integer_type_suffix()
    return literal

  def parse_integer_type_suffix(self):
    # integer-type-suffix
    suffix = None
    integer_suffix = ["U", "u", "L", "l", "UL", "Ul", "uL", "ul", "LU", "Lu", "lU", "lu"]
    next_two = self.core.definition[self.core.pos:self.core.pos+1]
    if next_two in integer_suffix:
      suffix = next_two
    elif next_two[0] in integer_suffix:
      suffix = next_two[0]
    if suffix:
      self.core.skip("suffix")
      return NamedDefinition("integer-type-suffix", suffix)
    return None

    
      # We must have a hexadecimal on our hands


  def parse_operator_or_punctuator(self):
    # ops_1 = 
    # OPERATOR_OR_PUNCTUATOR
    ops_1 = [x for x in OPERATOR_OR_PUNCTUATOR if len(x) == 1]
    ops_2 = [x for x in OPERATOR_OR_PUNCTUATOR if len(x) == 2]
    ops_3 = [x for x in OPERATOR_OR_PUNCTUATOR if len(x) == 3]
    # ops_1 = list("{}[]().,:;+-*/%&|^!~=<>?")
    # ops_2 = ['??', '::', '++', '--', '&&', '||', '->', '==', '!=', '<=', '>=', '+=', '-=', '*=', '/=', '%=', '&=', '|=', '^=', '<<', '=>']
    # ops_3 = ['<<=']
    parsed = None
    threechars = self.core.definition[self.core.pos:self.core.pos+3]
    if len(threechars) == 3 and threechars in ops_3:
      parsed = threechars
    elif len(threechars) >= 2 and threechars[:2] in ops_2:
      parsed = threechars[:2]
    elif len(threechars) >= 1 and threechars[0] in ops_1:
      parsed = threechars[0]
    if not parsed:
      return None
    self.core.pos += len(parsed)
    return NamedDefinition("operator-or-punctuator", parsed)

  def parse_character_literal(self):
    state = self.core.savepos()
    if not self.core.next_char == "'":
      return None
    self.core.pop_char()
    char = self.core.pop_char()
    #Any character except ' (U+0027), \ (U+005C), and new-line-character
    if char in "'\n":
      raise DefinitionError("ERROR: Badly terminated char literal")
    if char == "\\":
      escapes = "'\"\\0abfnrtvxuU"
      char += self.core.pop_char()
      if not char[-1] in escapes:
        raise DefinitionError("Char not in escapes!")
      # Just read until the next ''
      char += self.core.skip_to_any_char("'")
    if not self.core.pop_char() == "'":
      raise DefinitionError("Badly terminated char")
    return NamedDefinition("character-literal", char)



  def parse_string_literal(self):
    def _parse_regular_string_literal():
      escapers = "'\"\0abfnrtvxuU"
      parsed = u""
      while True:
        parsed += self.core.skip_to_any_char('"\\\n')
        # Why did we stop?
        if self.core.next_char == '"':
          break
        halter = self.core.pop_char()
        if halter == "\\":
          # Could be an escape (probably)
          if not self.core.next_char in escapers:
            print "ERROR: Non-properly escaped char?"
            raise DefinitionError("Not properly escaped string char")
          # Eat the next character
          parsed += halter + self.core.pop_char()
        elif halter == "\n":
          print "ERROR: Newline in regular string"
          raise DefinitionError("Newline in regular string")
      return NamedDefinition("regular-string-literal", parsed)

    def _parse_verbatim_string_literal():
      parsed = u""
      while True:
        parsed += self.core.skip_to_any_char('"')
        # Stopped on ", if the next is one too just add

        if not self.core.pos+1 == self.core.end and self.core.definition[self.core.pos+1] == '"':
          parsed += '""'
          self.core.pop_char()
          self.core.pop_char()
        else:
          break
      return NamedDefinition("verbatim-string-literal", parsed)

    # regular-string-literal-character: 
    # single-regular-string-literal-character 
    # simple-escape-sequence
    # hexadecimal-escape-sequence 
    # unicode-escape-sequence

    state = self.core.savepos()
    next_token = self.core.pop_char()
    parsed = None
    if next_token == "@":
      if not self.core.pop_char() == '"':
        self.core.restorepos(state)
        return None
      parsed = _parse_verbatim_string_literal()
    elif next_token == '"':
      
      parsed = _parse_regular_string_literal()
    else:
      self.core.restorepos(state)
      return None

    # Eat the next token, a "
    if not self.core.pop_char() == '"':
      print "ERROR: Badly terminated stirng"
      raise DefinitionError("Badly terminated string")

    parsed.adddef("string-literal")
    return parsed




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
  info = u"{}{}{}".format(prefix, "", codecs.utf_8_decode(repr(space)))
  print "{}{}".format(info.ljust(75), doc)
  if not hasattr(space, "members"):
    return
  for member in space.members:
    summarize_space(member, level+1)