# coding: utf-8

import re
import codecs
import os


from ..parser import DefinitionParser, DefinitionError
from ..types import ClassInfo
from .core import CoreParser
import lexical
from .lexical import LexicalParser, TypeName, Member, \
  FormalParameter, Statement, Attribute

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

  def swallow_one_of(self, words):
    for word in words:
      if self.core.skip_word_and_ws(word):
        return word
    raise DefinitionError("Could not read any of " + ", ".join(words))

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
        raise DefinitionError("no identity")
      args = self.opt(self._parse_type_argument_list)
      
      t = TypeName("namespace-or-type-name")
      t.parts.append(ident)
      t.parts.append(args)
      t.form = ident
      if args:
        t.form += "<{}>".format(", ".join(args))
      return t
    
    def _second():
      raise DefinitionError("Disabled")
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

  def _parse_nonarray_type(self):
    tname = self.first_of((self._parse_value_type, self._parse_class_type, 
      self._parse_interface_type, self._parse_delegate_type, 
      self._parse_type_parameter))
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
    kw = self.lex.parse_identifier_or_keyword()
    if kw in ("object", "dynamic", "string"):
      return kw
    raise DefinitionError("Not a class type")

  def _parse_delegate_type(self):
    return self._parse_type_name()

  def _parse_interface_type(self):
    return self._parse_type_name()

  def _parse_array_type(self):
    nat = self._parse_nonarray_type()
    if not nat:
      raise DefinitionError("Not an array type")
    self.swallow_with_ws('[')
    while self.core.skip_with_ws(','):
      pass
    self.swallow_with_ws(']')

  def _parse_type_argument_list(self):
    #type-argument-list: < type... >
    self.swallow_with_ws('<')
    args = self._parse_any(_self._parse_type, ",")
    if not args:
      raise DefinitionError("No type argument params")
    self.swallow_with_ws('>')


  ## B.2.4 Expressions ################################
  ## B.2.5 Statements #################################

  def _parse_statement(self):
    print "Trying to parse statement: " + self.cur_line()
    statement = self.first_of([
      self._parse_labeled_statement,
      self._parse_declaration_statement,
      self._parse_embedded_statement
      ])
    if statement:
      return statement
    raise DefinitionError("Could not read statement of any form")

  def _parse_embedded_statement(self):
    return self.first_of([
      self._parse_block,
      self._parse_empty_statement,
      self._parse_fudged_statement,
      ])

  def _parse_block(self):
    self.swallow_with_ws('{')
    statements = self._parse_any(self._parse_statement)
    self.swallow_with_ws('}')
    return statements
  
  def _parse_empty_statement(self):
    self.swallow_with_ws(';')
    return Statement('empty-statement', ';')

  def _parse_labeled_statement(self):
    ident = self.lex.parse_identifier()
    if not ident:
      raise DefinitionError("Not a labelled statement")
    self.swallow_with_ws(':')
    statement = self._parse_statement()
    form = "{} : {}".format(ident, statement)
    return Statement('labeled-statement', form)

  def _parse_declaration_statement(self):
    # local-variable-declaration ; local-constant-declaration ;
    const = self.core.skip_word_and_ws('const')
    st = self._parse_local_variable_declaration()
    if const:
      st.definitionname = "local-constant-declaration"
      st.form = "const " + st.form
    return st

  def _parse_local_variable_declaration(self):
    # Type: type, or var
    t = self._parse_type()
    if not t:
      self.swallow_word_and_ws('var')
      t = 'var'
    decl = self._parse_any(self._parse_local_variable_declarator, ',')
    if not decl:
      raise DefinitionError("Not a valid variable declaration")
    self.swallow_with_ws(';')
    form = "{} {}".format(t, decl)
    return Statement('local-variable-declaration', form)

  def _parse_local_variable_declarator(self):
    i = self.lex.parse_identifier()
    if not i:
      raise DefinitionError('not a local variable declarator')
    if self.core.skip_with_ws('='):
      exp = self._parse_expression()
      self.warn("Not properly parsing expressions")
    return i

  def _parse_fudged_statement(self):
    "Do a general 'statement-fudge'"
    # Try skipping to the next ;
    contents = self.core.skip_to_any_char(';}')
    self.swallow_with_ws(';')
    # print "SKipped: " + contents
    return contents

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

    print "Namespace member " + self.cur_line()
    return self.first_of((
      self._parse_namespace_declaration,
      self._parse_type_declaration
      ))

    raise DefinitionError("Could not parse namespace or type definition")

  def _parse_type_declaration(self):
    return self.first_of([
      self._parse_class_declaration
    ])
    # class-declaration
    # struct-declaration
    # interface-declaration
    # enum-declaration
    # delegate-declaration

  def _parse_qualified_alias_member(self):
    #     qualified-alias-member:
    # identifier :: identifier type-argument-listopt
    id1 = self.lex.parse_identifier()
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

    # self.swallow_with_ws('class')
    class_type = self.swallow_one_of(['class', 'struct'])
    print "Class type: " + class_type
    clike.name = self.lex.parse_identifier()

    type_params = self.opt(self._parse_type_parameter_list)

    if self.core.skip_with_ws(':'):
      clike.bases = self._parse_any(self._parse_type_name, ',')

    self.core.skip_ws()

    constraints = self._parse_any_type_parameter_constraints_clauses()
    
    return clike
    
  def _parse_class_declaration(self):

    clike = self._parse_class_declaration_header()
    self.core.skip_ws()


    # Class body
    print "Line: " + self.core.definition[self.core.pos:self.core.pos+30]
    self.swallow_with_ws('{')
    clike.members = self._parse_any_class_member_declarations()
    self.swallow_with_ws('}')
    self.core.skip_with_ws(";")
    return clike

  def _parse_type_parameter_list(self):
    self.swallow_with_ws('<')
    params = self._parse_any(self._parse_type_parameter, ",")
    if not params:
      raise DefinitionError("Incorrect type parameter list")
    self.swallow_with_ws('>')
    pl = lexical.TypeParameterList()
    pl.parts = params
    return pl

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
    return self.first_of([
      self.lex.parse_comment,
      self._parse_constant_declaration,
      self._parse_field_declaration,
      self._parse_method_declaration,
      self._parse_property_declaration,
      #event,
      #indexer,
      self._parse_constructor_declaration,
    ])

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

  def _parse_field_declaration(self):
    print "Trying to parse field: " + self.cur_line()
    m = Member("field-declaration")
    m.attributes = self._parse_any_attributes()
    valid_m = ("new", "public", "protected", "internal", "private", 
                "static", "readonly", "volatile")
    m.modifiers = self._parse_any_modifiers(valid_m)
    m.type = self._parse_type()
    decs = self._parse_variable_declarators()
    self.swallow_with_ws(';')
    m.name = decs
    return m

  def _parse_variable_declarators(self):
    decs = self._parse_any(self._parse_variable_declarator)
    if not decs:
      raise DefinitionError("Didn't get any variable declarators");
    return decs

  def _parse_variable_declarator(self):
    name = self.lex.parse_identifier()
    if not name:
      raise DefinitionError("no variable declarator")
    if self.core.skip_with_ws('='):
      # Expression, or array initialiser.
      value = self._parse_expression()
    return name

  def _parse_method_declaration(self):
    print "Trying to parse member: " + self.cur_line()
    m = self._parse_method_header()

    m.body = self.opt(self._parse_block)
    if not m.body:
      self.swallow_with_ws(';')

    return m

  def _parse_method_header(self):
    m = Member('method-declaration')
    m.attributes = self._parse_any_attributes()
    m.modifiers = self._parse_any_method_modifiers()
    m.partial = self.core.skip_with_ws('partial')
    m.type = self._parse_return_type()
    m.name = self._parse_type_name()
    type_params = self.opt(self._parse_type_parameter_list)
    self.swallow_with_ws('(')

    m.parameters = self.opt(self._parse_formal_parameter_list)
    print "Parameters: " + str(m.parameters)
    
    self.swallow_with_ws(')')
    constraints = self._parse_any_type_parameter_constraints_clauses()

    return m

  def _parse_return_type(self):
    rt = self._parse_type()
    if rt:
      return rt
    if self.core.skip_word_and_ws('void'):
      return void

  def _parse_formal_parameter_list(self):
    fixed = self._parse_any(self._parse_fixed_parameter, ',')
    return fixed

  def _parse_fixed_parameter(self):
    # attributesopt parameter-modifieropt type identifier default-argumentopt
    p = FormalParameter('fixed-parameter')
    p.attributes = self._parse_any_attributes()
    p.modifiers = self.opt(lambda: self.swallow_one_of(['ref', 'out', 'this']))
    p.type = self._parse_type()
    p.name = self.lex.parse_identifier()

    p.form = "{} {} {} {}".format(p.attributes, p.modifiers, p.type, p.name)
    if self.core.skip_with_ws('='):
      p.default = self._parse_expression()
      p.form += " = " + p.default
    p.form = p.form.strip()

    return p  

  def _parse_property_declaration(self):
    print "Trying to parse property: " + self.cur_line()
    m = Member('property-declaration')
    m.attributes = self._parse_any_attributes()
    m.modifiers = self._parse_any_property_modifiers()
    m.type = self._parse_type()
    m.name = self._parse_type_name()
    self.swallow_with_ws('{')
    # Accessor declarations
    acc = self._parse_accessor_declaration()
    acc2 = self.opt(self._parse_accessor_declaration)
    if acc2:
      m.accessors = [acc, acc2]
    else:
      m.accessors = [acc]
    self.swallow_with_ws('}')
    print "Parsed property"
    return m

  def _parse_accessor_declaration(self):
    #attributesopt accessor-modifieropt get accessor-body
    m = Member('accessor')
    m.attributes = self._parse_any_attributes()
    m.modifiers = self._parse_any_modifiers(['protected', 'internal', 'private'])
    m.accessor = self.swallow_one_of(['get', 'set'])
    m.body = self._parse_block()
    if not m.body:
      self.swallow_with_ws(';')
    m.definitionname = '{}-accessor-declaration'.format(m.accessor)
    return m

  def _parse_constructor_declaration(self):
    print "Trying to parse constructor: " + self.cur_line()
    # import pdb
    # pdb.set_trace()
    # constructor-declarator constructor-body

    m = Member('constructor-declaration')
    m.attributes = self._parse_any_attributes()
    m.modifiers = self._parse_any_modifiers(['public', 'protected', 'internal', 'private', 'extern'])
    m.name = self.lex.parse_identifier()
    self.swallow_with_ws('(')
    m.parameters = self.opt(self._parse_formal_parameter_list)
    self.swallow_with_ws(')')
    m.initialiser = self.opt(self._parse_constructor_initialiser)

    m.body = self.opt(self._parse_block)
    if not m.body:
      self.swallow_with_ws(';')
    return m

  def _parse_constructor_initialiser(self):
    #: base ( argument-listopt ) : this ( argument-listopt )
    self.swallow_with_ws(':')
    to = self.swallow_one_of(['base', 'this'])
    self.swallow_with_ws('(')
    self.core.skip_to_char(')')
    self.swallow_with_ws(')')
    return "[initialiser]"

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

  def _parse_expression(self):
    # Complicated... skip for now
    return self._parse_fudged_statement()
    # raise Exception("Not processing expressions")

  def _parse_any_attributes(self):
    return self._parse_any(self._parse_attribute_section)

  def _parse_attribute_section(self, targets = None):
    self.swallow_with_ws('[')

    # Do we have an attribute target specifier?
    if not targets:
      targets = ['field', 'event', 'method', 'param', 'property', 'return', 'type']
    target = self.opt(lambda: self.swallow_one_of(targets))
    target = None

    asi = Attribute('attribute-section')
    asi.target = target
    asi.attributes = self._parse_any(self._parse_attribute, ',')
    self.swallow_with_ws(']')
    return asi

  def _parse_attribute(self):
    name = self._parse_type_name()
    arguments = self._parse_attribute_arguments()
    attr = Attribute('attribute')
    attr.name = name
    attr.arguments = arguments
    return attr

  def _parse_attribute_arguments(self):
    if not self.core.skip_with_ws('('):
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

