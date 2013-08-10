# coding: utf-8

import re
import codecs
import os


from ..parser import DefinitionParser, DefinitionError
from ..types import ClassInfo
from .core import CoreParser
from .lexical import LexicalParser, TypeName, Member

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

class ClassInfo(NamespaceInfo):
  bases = []

class FileParser(object):
  core = None
  lex = None

  def opt(self, parser):
    state = self.core.savepos()
    try:
      return parser()
    except DefinitionError:
      self.core.restorepos(state)
      return None

  def first_of(self, parsers, msg=None):
    for parser in parsers:
      val = self.opt(parser)
      if val:
        return val
    if msg:
      raise DefinitionError(msg)
    else:
      raise DefinitionError("Could not resolve any parser")

  def swallow_with_ws(self, char):
    """Skips a character and any trailing whitespace, but raises DefinitionError if not found"""
    if not self.core.skip_with_ws(char):
      if not self.core.eof:
        raise DefinitionError("Unexpected token: '{}'; Expected '{}'".format(self.cur_line(), char))
      else:
        raise DefinitionError("Unexpected end-of-string; Expected '{}'".format(char))

  def swallow_word_and_ws(self, word):
    if not self.core.skip_word_and_ws(word):
      if not self.core.eof:
        raise DefinitionError("Unexpected token: '{}'; Expected '{}'".format(self.cur_line(), word))
      else:
        raise DefinitionError("Unexpected end-of-string; Expected '{}'".format(word))

  def __init__(self, definition):
    self.core = CoreParser(definition)
    self.lex = LexicalParser(self.core)

  def warn(self, msg):
    self.core.warn(msg)
  def fail(self, msg):
    self.core.fail(msg)

  def savepos(self):
    return self.core.savepos()

  def restorepos(self, state):
    self.core.restorepos(state)

  def parse_file(self):
    return self._parse_compilation_unit()

  def _parse_any(self, parser, separator = None):
    """Attempts to parse any number of separated structures"""
    items = []
    state = self.savepos()
    try:
      while True:
        item = parser()
        if not item:
          break;
        items.append(item)
        state = self.savepos()
        if separator:
          self.swallow_with_ws(separator)

    except DefinitionError:
      self.restorepos(state)
    return items

  def cur_line(self):
    return self.core.cur_line()


  ## B.2.1 Basic Concepts #############################

  def _parse_namespace_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_type_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_namespace_or_type_name(self):
    def _first():
      # identifier type-argument-listopt
      names = self._parse_any(self.lex.parse_identifier, '.')
      ident = ".".join(names)

      # ident = self.lex.parse_identifier()
      if not ident:
        raise DefinitionError()
      args = self.opt(self._parse_type_argument_list)
      
      t = TypeName("namespace-or-type-name")
      t.parts.append(ident)
      t.parts.append(args)
      t.form = ident
      if args:
        t.form += "<{}>".format(", ".join(args))
      return t
    
    def _second():
      # namespace-or-type-name . identifier 
      nmsp = self._parse_namespace_or_type_name()
      self.swallow_with_ws('.')
      ident = self.lex._parse_identifier()
      if not nmsp or not ident:
        raise DefinitionError()
      
      t = TypeName("namespace-or-type-name")
      t.parts.append(nmsp)
      t.parts.append(ident)
      t.form = nmsp + "." + ident
      return t

    def _third():
      # type-argument-listopt qualified-alias-member
      args = self.opt(self._parse_type_argument_list)
      memb = self._parse_qualified_alias_member()
      t = TypeName("namespace-or-type-name")
      t.form = ""
      if args:
        t.form += "<{}>".format(", ".join(args))
      t.form += " " + memb
      return t

    return self.first_of((_first, _second, _third))

  ## B.2.2 Types ####################################

  def _parse_type(self):
    tname = self.first_of((self._parse_value_type, 
      self._parse_reference_type, self._parse_type_parameter))
    nullable = self.core.skip_with_ws("?")
    return (tname, nullable)

  def _parse_value_type(self):
    def _simple_type():
      simple_types = ("sbyte", "byte", "short", "ushort", "int", "uint", "long", "ulong", "char", "decimal", "bool")
      kw = self.lex.parse_identifier_or_keyword()
      if kw in simple_types:
        return kw
      raise DefinitionError("Not a simple type")

    def _struct_type():
      # Not handling nullable - could be anywhere?
      return self.first_of((self._parse_type_name, _simple_type ))

    def _enum_type():
      return self._parse_type_name()

    return self.first_of((_struct_type, _enum_type))

  def _parse_reference_type(self):
    return self.first_of(
      (self._parse_class_type, self._parse_interface_type,
        self._parse_array_type, self._parse_delegate_type))

  def _parse_class_type(self):
    cn = self.opt(self._parse_type_name)
    if cn:
      return cn
    kw = lex.parse_identifier_or_keyword()
    if kw in ("object", "dynamic", "string"):
      return kw
    raise DefinitionError("Not a class type")

  def _parse_delegate_type(self):
    return self._parse_type_name()

  def _parse_interface_type(self):
    return self._parse_type_name()

  def _parse_array_type(self):
    raise NotImplemented()

  def _parse_type_argument_list(self):
    #type-argument-list: < type... >
    self.swallow_with_ws('<')
    args = self._parse_any(_self._parse_type, ",")
    if not args:
      raise DefinitionError("No type argument params")
    self.swallow_with_ws('>')


  ## B.2.4 Expressions ################################
  ## B.2.5 Statements #################################

  ## B.2.6 Namespaces #################################

  def _parse_compilation_unit(self):
    # None-or more "extern alias identifier ;"
    extern_alias = self._parse_any_extern_alias_directives()
    if extern_alias:
      print "Parsed {} EADs".format(len(extern_alias))
    using_directives = self._parse_any_using_directives()
    print "Parsed {} using directives".format(len(using_directives))

    global_attr = self._parse_any(self._parse_global_attribute_section)
    if global_attr:
      print "Parsed {} global attributes".format(len(global_attr))

    names = self._parse_any_namespace_member_declarations()
    print names

  def _parse_namespace_declaration(self):
    self.swallow_word_and_ws('namespace')
    identifier = self._parse_qualified_identifier()

    space = NamespaceInfo(identifier)

    # Parse namespace body
    # { extern-alias-directivesopt using-directivesopt 
    # namespace-member-declarationsopt }
    self.swallow_with_ws("{")
    space.extern_alias = self._parse_any_extern_alias_directives()
    space.using = self._parse_any_using_directives()
    print "Parsing internals of namespace: " + space.name
    space.members = self._parse_any_namespace_member_declarations()
    print "   Parsed {} members".format(len(space.members))
    self.swallow_with_ws("}")

    self.core.skip_with_ws(";")

    return space

  def _parse_qualified_identifier(self):
    items = self._parse_any(self.lex.parse_identifier, ".")
    if not items:
      raise DefinitionError("Could not read qualified identifier")
    return ".".join(items)

  def _parse_any_extern_alias_directives(self):
    return self._parse_any(self._parse_extern_alias_directive)

  def _parse_extern_alias_directive(self):
    self.swallow_word_and_ws('extern')
    self.swallow_word_and_ws('alias')
    ident = self._parse_identifier()
    self.swallow_character_and_ws(';')

  def _parse_any_using_directives(self):
    return self._parse_any(self._parse_using_directive)

  def _parse_using_directive(self):
    """Attempt to parse both types of using directive"""
    # import pdb
    # pdb.set_trace()

    state = self.savepos()
    try:
      self.swallow_word_and_ws('using')
      # Alias directive
      ident = self.lex.parse_identifier()
      if not ident:
        raise DefinitionError()
      self.swallow_with_ws('=')
      namespace = self._parse_namespace_or_type_name()

      self.swallow_character_and_ws(';')
      return (namespace, ident)
    except DefinitionError:
      self.restorepos(state)

    # Using directive
    try:
      self.swallow_word_and_ws('using')
      namespace = self._parse_namespace_name()
      self.swallow_with_ws(';')
      if namespace:
        return (namespace, None)
    except DefinitionError:
      self.restorepos(state)

    self.restorepos(state)
    return None

  def _parse_any_namespace_member_declarations(self):
    return self._parse_any(self._parse_namespace_member_declaration)

  def _parse_namespace_member_declaration(self):
    # print "Parsing NS-dec: " + self.cur_line()
    # namespace-declaration, or type-declaration
    comment = self.lex.parse_comment()
    if comment:
      # print "Parsed comment: " + comment.contents
      return comment

    return self.first_of((
      self._parse_namespace_declaration,
      self._parse_type_declaration
      ))

    raise DefinitionError("Could not parse namespace or type definition")

  def _parse_type_declaration(self):
    # class-declaration
    # struct-declaration
    # interface-declaration
    # enum-declaration
    # delegate-declaration
    pass

  def _parse_qualified_alias_member(self):
    #     qualified-alias-member:
    # identifier :: identifier type-argument-listopt
    id1 = self._parse_identifier()
    self.swallow_word_and_ws('::')
    id2 = self._parse_identifier()
    args = self._parse_type_argument_list()
    if not id1 or not id2:
      raise DefinitionError("Invalid qualified-alias-member")
    qal = NamedDefinition('qualified-alias-member')
    qal.parts = (id1, id2, args)
    qal.form = "{} :: {} {}"
    return qal


  ## B.2.7 Classes ####################################

  def _parse_class_declaration_header(self):
    # Partly handled by prior, but be strict here
    clike = ClassInfo(None)
    
    clike.attributes = self._parse_any_attributes()
    clike.modifiers = self._parse_any_class_modifiers()
    self.core.skip_with_ws('partial')
    self.swallow_with_ws('class')
    clike.name = self.lex.parse_identifier()

    type_params = self.opt(self._parse_type_parameter_list)

    if self.core.skip_with_ws(':'):
      bases = self._parse_any(self._parse_type_name, ',')
      clike.bases = [x for x in bases]

    self.core.skip_ws()
    
    constraints = self._parse_any_type_parameter_constraints_clauses()
    
    return clike
    
  def _parse_class_declaration(self):

    clike = self._parse_class_declaration_header()

    self.core.skip_ws()
    import pdb
    pdb.set_trace()

    # Class body
    print "Line: " + self.core.definition[self.core.pos:self.core.pos+30]
    self.swallow_with_ws('{')
    members = self._parse_any_class_member_declarations()
    self.swallow_with_ws('}')
    self.core.skip_with_ws(";")

  def _parse_type_parameter_list(self):
    self.swallow_with_ws('<')
    params = self._parse_any(self._parse_type_parameter, ",")
    if not params:
      raise DefinitionError("Incorrect type parameter list")
    self.swallow_with_ws('>')

  def _parse_type_parameter(self):
    attr = self._parse_any_attributes()
    ident = self.lex.parse_identifier()
    return ident


  def _parse_any_type_parameter_constraints_clauses(self):
    return self._parse_any(self._parse_type_parameter_constraints_clause)

  def _parse_type_parameter_constraints_clause(self):
    self.swallow_word_and_ws('where')
    name = self._parse_type_parameter()
    self.swallow_with_ws(':')

    # Attempt any primary constraints
    constraints = [self._parse_primary_constraint()]
    if self.core.skip_with_ws(','):
      constraints.extend(self._parse_any(self._parse_type_name, ','))

    if constraints and str(constraints[-1]) == "new":
      self.swallow_with_ws('(')
      self.swallow_with_ws(')')
      t = constraints[-1]
    
    return constraints

  def _parse_primary_constraint(self):
    typ = self._parse_class_type()
    if typ:
      return typ
    if self.skip_word_and_ws("class"):
      return "class"
    if self.skip_word_and_ws("struct"):
      return "struct"

  def _parse_any_class_member_declarations(self):
    return self._parse_any(self._parse_class_member_declaration)

  def _parse_class_member_declaration(self):
    # constant-declaration field-declaration method-declaration property-declaration event-declaration indexer-declaration operator-declaration constructor-declaration destructor-declaration static-constructor-declaration type-declaration
    return self.first_of((
      self._parse_constant_declaration
    ))

  def _parse_constant_declaration(self):
    m = Member("constant-declaration")
    m.attributes = self._parse_any_attributes()
    m.modifiers = self._parse_any_modifiers(['new', 'public', 'protected', 'internal', 'private'])
    self.swallow_word_and_ws('const')
    m.type = self._parse_type()
    m.name = self.lex.parse_identifier()
    self.swallow_with_ws('=')
    m.expression = self._parse_expression()
    self.swallow_with_ws(';')
    if not m.type or not m.name or not m.expression:
      raise DefinitionError()
    return m



  ## Uncategorised ####################################

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

  def _parse_any_attributes(self):
    return self._parse_any(self._parse_attribute_section)

  def _parse_attribute_section(self, targets = None):
    self.swallow_with_ws('[')

    # Do we have an attribute target specifier?
    if not targets:
      targets = ['field', 'event', 'method', 'param', 'property', 'return', 'type']
    self.match(_identifier_re)
    target = None
    if self.matched_text in targets:
      target = self.matched_text
      self.skip_ws()
      self.swallow_character_and_ws(":")
    else:
      self.backout()

    asi = AttributeSectionInfo()
    asi._target = target
    asi._attributes = self.parse_comma_list([r']'], self._parse_attribute)
    self.swallow_character_and_ws(']')
    return asi

  def _parse_attribute(self):
    name = self._parse_type_name()
    arguments = self._parse_attribute_arguments()
    attr = AttributeInfo()
    attr._name = name
    attr._arguments = arguments
    return attr

  def _parse_attribute_arguments(self):
    if not self.skip_character_and_ws('('):
      return []
    # Skip anything until the end )
    self.match(re.compile(r"[^)]*"))
    value = self.matched_text
    self.swallow_character_and_ws(')')
    return [value]

  def _parse_any_class_modifiers(self):
    """Parse any valid class modifiers"""
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                       'abstract', 'sealed', 'static', 'type')
    return self._parse_any_modifiers(valid_modifiers)

  def _parse_any_constructor_modifiers(self):
    valid_modifiers = ('public', 'protected', 'internal', 'private', 'extern')
    return self._parse_any_modifiers(valid_modifiers)

  def _parse_any_method_modifiers(self):
    valid = ('new', 'public', 'protected', 'internal', 'private',
                   'static', 'virtual', 'sealed', 'override', 'abstract',
                   'extern')
    return self._parse_any_modifiers(valid)

  def _parse_any_property_modifiers(self):
    valid = ('new', 'public', 'protected', 'internal', 'private',
                   'static', 'virtual', 'sealed', 'override', 'abstract',
                   'extern')
    return self._parse_any_modifiers(valid)

  def _parse_any_modifiers(self, valid_modifiers):
    fun = lambda: self._parse_modifier(valid_modifiers)
    return self._parse_any(fun)

  def _parse_modifier(self, valids):
    kw = self.lex.parse_identifier_or_keyword()
    if kw in valids:
      return kw
    raise DefinitionError("Not a valid keyword: " + str(kw))


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


  def _parse_global_attribute_section(self):
    return self._parse_attribute_section(['assembly', 'module'])  

  def _parse_statement_expression(self):
    pass
# statement-expression: invocation-expression object-creation-expression assignment post-increment-expression post-decrement-expression pre-increment-expression pre-decrement-expression

