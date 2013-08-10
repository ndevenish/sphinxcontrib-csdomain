# coding: utf-8

import re
import codecs
import os


from ..parser import DefinitionParser, DefinitionError

_not_newline_re = re.compile(r'[^\n\r]*')
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

def opensafe(filename, mode = 'r'):
  bytes = min(32, os.path.getsize(filename))
  raw = open(filename, 'rb').read(bytes)

  if raw.startswith(codecs.BOM_UTF8):
    encoding = 'utf-8-sig'
  else:
    result = chardet.detect(raw)
    encoding = result['encoding']

  return codecs.open(filename, mode, encoding=encoding)


class BasicFormInfo(object):
  contents = None
  def __init__(self, content = None):
    self.contents = content

class WhitespaceInfo(BasicFormInfo):
  pass

class CommentInfo(BasicFormInfo):
  pass

class Token(BasicFormInfo):
  tokentype = 'token'

class StatementInfo(BasicFormInfo):
  statement_type = None
  def __init__(self, st, contents):
    self.contents = contents
    self.statement_type = st

class NamespaceInfo(object):
  name = None
  members = []
  using = []
  extern_alias = []
  attributes = []

  def __init__(self, name):
    self.name = name

class FileParser(DefinitionParser):

  def warn(self, message):
    print message

  def savepos(self):
    return (self.pos, self.last_match)

  def restorepos(self, state):
    (self.pos, self.last_match) = state

  def parse_file(self):
    return self._parse_compilation_unit()

  def _parse_many(self, parser):
    items = []
    state = self.savepos()
    try:
      while True:
        item = parser()
        if not item:
          break;
        items.append(item)
        state = self.savepos()
    except:
      self.restorepos(state)
    return items

  def cur_line(self):
    self.match(_not_newline_re)
    value = self.matched_text
    self.backout()
    return value

  def _parse_compilation_unit(self):
    # None-or more "extern alias identifier ;"
    extern_alias = self._parse_extern_alias_directives()
    if extern_alias:
      print "Parsed {} EADs".format(len(extern_alias))
    using_directives = self._parse_using_directives()
    print "Parsed {} using directives".format(len(using_directives))

    global_attr = self._parse_many(self._parse_global_attribute_section)
    if global_attr:
      print "Parsed {} global attributes".format(len(global_attr))

    names = self._parse_namespace_member_declarations()
    print names

# compilation-unit:
# extern-alias-directivesopt
# using-directivesopt global-attributesopt
# namespace-member-declarationsopt

  def _parse_using_directives(self):
    return self._parse_many(self._parse_using_directive)

  def _parse_extern_alias_directives(self):
    return self._parse_many(self._parse_extern_alias_directive)

  def _parse_extern_alias_directive(self):
    self.swallow_character_and_ws('extern')
    self.swallow_character_and_ws('alias')
    ident = self._parse_identifier()
    self.swallow_character_and_ws(';')

  def _parse_using_directive(self):
    state = self.savepos()
    try:
      self.swallow_word_and_ws('using')
      # Alias directive
      ident = self._parse_identifier()
      self.swallow_character_and_ws('=')
      namespace = self._parse_namespace_or_type_name()
      self.swallow_character_and_ws(';')
      return (namespace, ident)
    except DefinitionError:
      self.restorepos(state)

    # Using directive
    try:
      self.swallow_word_and_ws('using')
      namespace = self._parse_namespace_name()
      self.swallow_character_and_ws(';')
      if namespace:
        return (namespace, None)
    except DefinitionError:
      self.restorepos(state)

    self.restorepos(state)
    return None

  def _parse_global_attribute_section(self):
    return self._parse_attribute_section(['assembly', 'module'])
  
  def _parse_namespace_member_declarations(self):
    return self._parse_many(self._parse_namespace_member_declaration)

  def _parse_namespace_member_declaration(self):
    # namespace-declaration, or type-declaration
    state = self.savepos()
    try:
      return self._parse_namespace_declaration()
    except DefinitionError:
      self.restorepos(state)
    try:
      return self._parse_type_declaration()
    except DefinitionError:
      self.restorepos(state)

    raise DefinitionError("Could not parse namespace or type definition")


  def _parse_namespace_declaration(self):
    self.swallow_word_and_ws('namespace')
    identifier = self._parse_qualified_identifier()

    space = NamespaceInfo(identifier)

    # Parse namespace body
    # { extern-alias-directivesopt using-directivesopt 
    # namespace-member-declarationsopt }
    self.swallow_character_and_ws("{")
    space.extern_alias = self._parse_extern_alias_directives()
    space.using = self._parse_using_directives()
    print "Parsing internals of namespace: " + space.name
    space.members = self._parse_namespace_member_declarations()
    print "   Parsed {} members".format(len(space.members))
    self.swallow_character_and_ws("}")

    self.skip_character_and_ws(";")

    return space

  def _parse_type_declaration(self):
    pass

  def _parse_identifier(self):
    state = self.savepos()
    prefix = self.skip_character('@')
    if not self.match(_identifier_re):
      self.restorepos(state)
      return None
    ident = self.matched_text
    if not prefix:
      if ident in KEYWORDS:
        self.restorepos(state)
        return None
      return ident
    else:
      ident = "@" + ident
    self.skip_ws()

  def _parse_qualified_identifier(self):
    items = []
    while True:
      ident = self._parse_identifier()
      if not ident:
        break
      items.append(ident)
      if not self.skip_character_and_ws('.'):
        break
    self.skip_ws()
    return ".".join(items)

  def _parse_keyword(self):
    if self.match(_identifier_re):
      if self.matched_text in KEYWORDS:
        self.skip_ws()
        return self.matched_text
    return None

  def skip_to_eol(self):
    self.match(_not_newline_re)
    value = self.matched_text
    self.skip_ws()
    return value

  def _parse_comment(self):
    if self.definition[self.pos:self.pos+1] == "//":
      self.pos += 2
      
      match = regex.match(self.definition, self.pos)
    if match is not None:
      self._previous_state = (self.pos, self.last_match)
      self.pos = match.end()
      self.last_match = match
      return True

      return CommentInfo(self.skip_to_eol())
    return None
  
  def _parser_input_element(self):
    if self.skip_ws():
      return WhitespaceInfo(self.matched_text)
    comment = self._parse_comment()
    if comment:
      return comment
    token = self._parse_token()
    if not token:
      self.fail("Could not parse")
  
  def _parse_token(self):
    ident = self._parse_identifier()
    if not ident:
      self.fail("Could not get token from input")

    token = Token(ident)
    token.tokentype = "identifier"
    if ident in KEYWORDS:
      token.tokentype = "keyword"

    return token

  def _parse_statement(self):
    state = self.savepos()
    try:
      statement = self._parse_labeled_statement()
    except DefinitionError:
      self.restorepos(state)
    try:
      statement = self._parse_declaration_statement()
      if not statement:
        raise DefinitionError("Invalid statement")
    except DefinitionError:
      self.restorepos(state)
    try:
      statement = self._parse_embedded_statement()
    except DefinitionError:
      self.restorepos(state)

    raise DefinitionError("Could not read statement of any form")


  def _parse_labeled_statement(self):
    ident = self._parse_identifier()
    if not ident:
      raise DefinitionError("Not a labelled statement")
    self.swallow_character_and_ws(':')
    statement = self._parse_statement()
    return StatementInfo('labelled', (ident, statement))

  def _parse_declaration_statement(self):
    # local-variable-declaration ; local-constant-declaration ;
    const = self.skip_word_and_ws('const')
    st = self._parse_local_variable_declaration()
    if const:
      st.statement_type = "constant-variable"
    return st

  def _parse_local_variable_declaration(self):
    t = self._parse_type(self)
    if not t:
      return None
    # Comma-separated list of identifier, identifier + something
    identifiers = self.parse_comma_list([';'], self._parse_local_variable_declarator)
    if not identifiers:
      raise DefinitionError("Not a valid variable declaration")
    self.swallow_character_and_ws(';')
    return StatementInfo('local-variable', (t, identifiers))

  def _parse_local_variable_declarator(self):
    i = self._parse_identifier()
    if self.skip_character_and_ws('='):
      exp = self._parse_expression()
      self.warn("Not properly parsing expressions")
    return i


  def _parse_expression(self):
    # Complicated... skip for now
    raise Exception("Not processing expressions")

  def _parse_embedded_statement(self):
    state = (self.pos, self.last_match)
    # Blocks
    if self.skip_character_and_ws('{'):
      statements = []
      # Block start
      while not self.skip_character_and_ws('}'):
        statements.append(self._parse_statement())
      return StatementInfo('block', statements)
    if self.skip_character_and_ws(';'):
      return StatementInfo('empty', None)
    # Try expression-statement
    try:
      expr = self._parse_statement_expression()
      self.swallow_character_and_ws(';')
    except DefinitionError:
      (self.pos, self.last_match) = state
# expression-statement 
# selection-statement 
# iteration-statement 
# jump-statement 
# try-statement 
# checked-statement 
# unchecked-statement 
# lock-statement 
# using-statement 
# yield-statement


  def _parse_statement_expression(self):
    pass
# statement-expression: invocation-expression object-creation-expression assignment post-increment-expression post-decrement-expression pre-increment-expression pre-decrement-expression

