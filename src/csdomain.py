#coding: utf-8

import re
from sphinx.locale import l_, _
from sphinx.domains import Domain, ObjType
from sphinx.util.compat import Directive
from sphinx.directives import ObjectDescription

from docutils import nodes
from sphinx import addnodes

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')
# _visibility_re = re.compile(r'\b(public|private|protected)\b')
_whitespace_re = re.compile(r'\s+(?u)')

class MemberInfo(object):
  _attributes = []
  _modifiers = []
  _name = None
  _type = None

class MethodInfo(MemberInfo):
  _arguments = None

class PropertyInfo(MemberInfo):
  _setter = None
  _getter = None

class AttributeSectionInfo(object):
  _target = None
  _attributes = []

  def __str__(self):
    fs = "["
    if self._target:
      fs += "{} : ".format(self._target)
    attrlist = [str(x) for x in self._attributes]
    fs += ", ".join(attrlist)
    fs += "]"
    return fs

class AttributeInfo(object):
  _name = None
  _arguments = []

  def __str__(self):
    fs = str(self._name)
    if len(self._arguments):
      fs += "(" + ", ".join(self._arguments) + ")"
    return fs

class TypeInfo(object):
  _name = None
  _arguments = None
  _full = None
  _namespace = None

  def __init__(self, name, arguments=[]):
    self._name = name
    self._arguments = arguments
    # if arguments is None:
    #   self._arguments = []
    # else:
    #   self._arguments = arguments

    if len(self._arguments):
      self._full = "{}<{}>".format(_name, ', '.join(_arguments))
    else:
      self._full = name

  def fqn(self):
    alln = [self._full]
    if self._namespace:
      alln = self._namespace.fqn() + [self._full]
    return ".".join(alln)

  def __str__(self):
    return self.fqn()

  def __repr__(self):
    return "<Type: {}>".format(self._full)

def valid_identifier(string):
  return _identifier_re.match(string) is not None

def full_type_name(type_name):
  """Returns a type name list to a full string"""
  return type_name
  # return ".".join(x['full'] for x in type_name)

def full_attribute_name(attribute_info):
  """Returns an attribute dictionary to a full string"""

  return " ".join(str(x) for x in attribute_info)


class DefinitionError(Exception):
    def __init__(self, description):
        self.description = description

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __unicode__(self):
        return self.description

class DefinitionParser(object):
  def __init__(self, definition):
    self.definition = definition.strip()
    self.pos = 0
    self.end = len(self.definition)
    self.last_match = None
    self._previous_state = (0, None)

  def fail(self, msg):
      raise DefinitionError(
        'Invalid definition: {} [error at {}]\n  {}\n  {}^here'
          .format(msg, self.pos, self.definition, " "*(self.pos)))

  def skip_word(self, word):
    return self.match(re.compile(r'\b%s\b' % re.escape(word)))

  def skip_character(self, char):
    return self.match(re.compile(re.escape(char)))

  def skip_character_and_ws(self, char):
    if self.skip_character(char):
      self.skip_ws()
      return True
    return False

  def swallow_character_and_ws(self, char):
    """Skips a character and any trailing whitespace, but raises DefinitionError if not found"""
    if not self.skip_character_and_ws(char):
      raise DefinitionError("Unexpected token: '{}'; Expected '{}'".format(self.definition[self.pos], char))

  def skip_ws(self):
    return self.match(_whitespace_re)

  def skip_word_and_ws(self, word):
    if self.skip_word(word):
      self.skip_ws()
      return True
    return False

  def backout(self):
      self.pos, self.last_match = self._previous_state

  def match(self, regex):
    match = regex.match(self.definition, self.pos)
    if match is not None:
      self._previous_state = (self.pos, self.last_match)
      self.pos = match.end()
      self.last_match = match
      return True
    return False

  def peek_match(self, regex):
    """Attempt to match the next set of data, without advancing"""
    match = regex.match(self.definition, self.pos)
    if match is not None:
      return (True, match.group())
    return None

  @property
  def matched_text(self):
    if self.last_match is not None:
      return self.last_match.group()

  @property
  def eof(self):
      return self.pos >= self.end


  def _parse_type_parameter_list(self):
    """Parses a <T, Q, ...> type parameter list. Empty for none."""
    generic = self.skip_character_and_ws('<')
    generic_params = []
    if generic:
      generic_params = self.parse_comma_list(['>'])
      self.skip_character_and_ws('>')
    return generic_params

  def _parse_type_argument_list(self):
    """Parses a <Type, Type,...> argument list. Empty for None."""
    generic = self.skip_character_and_ws('<')
    generic_params = []
    if generic:
      generic_params = self.parse_comma_list(['>'], self._parse_type)
      self.skip_character_and_ws('>')
    return generic_params    



  def parse_comma_list(self, terminators, parser=None):
    """Parses a list of comma separated identifiers, terminated by some set"""
    if parser is None:
      parser = self._parse_identifier
    results = []
    # try:
    #   match = parser()
    # except DefinitionError:
    #   match = None
    # Try to grab an identifier first

    while self.match(_identifier_re):
      matched_text = self.matched_text
      self.backout()
      if matched_text in terminators:
        break
      # We know we can continue, now run the proper parsing method
      try:
        results.append(parser())
      except DefinitionError:
        break
      self.skip_character_and_ws(',')
    return results

  def parse_method(self):
    method = self._parse_method_header()
    
    print method
    print "Parsing Method:"
    print "  Modifiers: {}".format(", ".join(method._modifiers))
    print "  Return:    {}".format(method._type)
    print "  Name:      {}".format(method._name)
    print "  Arguments: {}".format(len(method._arguments))
    for arg in method._arguments:
      argspec = ""
      if arg['attributes']:
        argspec += full_attribute_name(arg['attributes']) + " "
      if arg['modifiers']:
        argspec += " ".join(arg['modifiers']) + " "
      # argspec += arg['type'] + ' ' + arg['name']
      print "    {}{} {}".format(argspec, arg['type'], arg['name'])

    return method

#     partialopt return-type member-name type-parameter-listopt
# ( formal-parameter-listopt ) type-parameter-constraints-clausesopt

  def parse_class(self):

    modifiers = self._parse_class_modifiers()
    static = 'static' in modifiers
    visibility = self._find_visibility(modifiers)

    # Skip the word partial, and class
    partial = self.skip_word_and_ws("partial")
    if not self.skip_word_and_ws("class"):
      self.fail("invalid class definition")
    # The Class Name
    self.match(_identifier_re)
    name = self.matched_text

    # Optional type-parameter list
    generic_params = self._parse_type_parameter_list()
    generic = len(generic_params) > 0

    class_bases = []
    # (Optional) Class-bases next, starting with :
    if self.skip_character_and_ws(':'):
      class_bases = self.parse_comma_list(("where", "{"), self._parse_type_name)

    # Optional type-parameter-constraints
    self.skip_ws()
    parameter_constraints = self._parse_type_parameter_constraints_clauses()
    # parameter_constraints = {}
    # while self.skip_word_and_ws("where"):
    #   self.match(_identifier_re)
    #   parameter_name = self.matched_text
    #   # Check that this is in the argument list
    #   if not parameter_name in generic_params:
    #     fail("Class Type-Argument mismatch: Constraint on non-class parameter")
    #   self.skip_ws()
    #   self.skip_character_and_ws(":")
    #   parameter_constraint_list = self.parse_comma_list(("where", "{"))
    #   # If we ended with new, swallow the ()
    #   if parameter_constraint_list[-1] == "new":
    #     self.skip_character('(')
    #     self.skip_character_and_ws(')')
    #     parameter_constraint_list[-1] = 'new()'

    #   parameter_constraints[parameter_name] = parameter_constraint_list



    # Print a summary of all information

    print "Parsing Class:"
    print "  Visibility: " + visibility
    print "  Static:     {}".format(static)
    print "  Partial:    {}".format(partial)
    print "  ClassName:  {}".format(name)
    print "  Generic:    {}".format(generic)
    if (generic):
      print "     Args:    {}".format(", ".join(generic_params))
      for arg in [x for x in generic_params if parameter_constraints.has_key(x)]:
        print "     Arg {}:   {}".format(arg, parameter_constraints[arg])
    if len(class_bases) > 0:
      print "  Bases:      {}".format(", ".join([str(x) for x in class_bases]))

    return {
      'visibility': visibility,
      'static': static,
      'name': name,
      'generic': generic,
      'typeargs': generic_params,
      'bases': class_bases,
      'typearg_constraints': parameter_constraints
    }

  def parse_property(self):
    return self._parse_property_declaration()

  def parse_member(self):
    return self._parse_class_member_declaration()

  def _parse_method_header(self):
    method = MethodInfo()
    method._attributes = self._parse_attributes()
    method._modifiers = self._parse_method_modifiers()
    self.skip_word_and_ws('partial')
    method._type = self._parse_returntype()
    
    # The member name
    method._name = self._parse_member_name()

    # The argument list
    self.swallow_character_and_ws('(')
    method._arguments = self._parse_formal_argument_list()
    self.swallow_character_and_ws(')')

    type_parameter_list = self._parse_type_parameter_list()

    #raise NotImplementedError("Need to read formal parameter list")

    constraints = self._parse_type_parameter_constraints_clauses()

    return method

  def _parse_class_member_declaration(self):
    state = (self.pos, self.last_match)
    # Attempt to parse a methd
    try:
      return self._parse_method_header()
    except DefinitionError:
      self.pos, self.last_match = state
      print "Could not parse method from: " + self.definition[self.pos:]
    try:
      return self._parse_property_declaration()
    except DefinitionError:
      self.pos, self.last_match = state
      print "Could not parse property from: " + self.definition[self.pos:]
    raise ValueError()

  # class-member-declaration:
  #  constant-declaration
  #  field-declaration 
  #  method-declaration 
  #  property-declaration 
  #  event-declaration 
  #  indexer-declaration 
  #  operator-declaration 
  #  constructor-declaration 
  #  destructor-declaration
  #  static-constructor-declaration 
  #  type-declaration

  def _parse_property_declaration(self):
    prop = PropertyInfo()

    prop._attributes = self._parse_attributes()
    prop._modifiers = self._parse_property_modifiers()
    prop._type = self._parse_type()
    prop._name = self._parse_member_name()
    
    self.swallow_character_and_ws('{')
    try:
      ac = self._parse_accessor_declaration()
      if ac:
        if ac._name == "get":
          prop._getter = ac
        else:
          prop._setter = ac
    except DefinitionError:
      pass
    try:
      ac = self._parse_accessor_declaration()
      if ac:
        if ac._name == "get":
          prop._getter = ac
        else:
          prop._setter = ac
    except DefinitionError:
      pass

    print "setter: " + str(prop._setter)
    print "getter: " + str(prop._getter)


    self.swallow_character_and_ws('}')
    return prop

  def _parse_accessor_declaration(self):
    ai = MemberInfo()
    ai._attributes = self._parse_attributes()
    ai._modifiers = self._parse_modifiers(('protected', 'internal', 'private'))
    
    # Next word is either get or set
    if self.skip_word_and_ws('get'):
      ai._name = "get"
    elif self.skip_word_and_ws('set'):
      ai._name = "set"
    else:
      raise DefinitionError("Could not read get or set from property")
    # Now is accessor body. Die unless this is just an empty ;
    if not self.skip_character_and_ws(';'):
      raise DefinitionError("Can not read properties with block body!")
    return ai


  def _parse_identifier(self):
    match = self.match(_identifier_re)
    if not match:
      raise DefinitionError("Could not parse. Expected: Identifier. Got: " + self.definition[self.pos:])
    value = self.matched_text
    self.skip_ws()
    return value

  def _parse_member_name(self):
    return self._parse_identifier()

  def _parse_formal_argument_list(self):
    arguments = []
    while (not self.skip_character(')')) and (not self.eof):
      argument = self._parse_fixed_parameter()
      arguments.append(argument)
      self.skip_character_and_ws(',')
    self.backout()
    return arguments


  def _parse_fixed_parameter(self):
    # Attributes....
    attributes = self._parse_attributes()

    #attributesopt  type identifier default-argumentopt
    modifiers = self._parse_modifiers(("ref", "out", "this"))
    paramtype = self._parse_type()
    name = self._parse_identifier()
    expression = None
    if self.skip_character_and_ws('='):
      # For now, skip until the next , or )
      self.match(re.compile(r'[^,)]+'))
      expression = self.matched_text
    return {
      'attributes': attributes,
      'modifiers': modifiers,
      'type': paramtype,
      'name': name,
      'default': expression
    }

  def _parse_type_parameter_constraints_clauses(self):
    parameter_constraints = {}
    while self.skip_word_and_ws("where"):
      self.match(_identifier_re)
      parameter_name = self.matched_text
      self.skip_ws()
      self.skip_character_and_ws(":")
      parameter_constraint_list = self.parse_comma_list(("where", "{"))
      # If we ended with new, swallow the ()
      if parameter_constraint_list[-1] == "new":
        self.skip_character('(')
        self.skip_character_and_ws(')')
        parameter_constraint_list[-1] = 'new()'

      parameter_constraints[parameter_name] = parameter_constraint_list
    return parameter_constraints
    
  def _parse_class_modifiers(self):
    """Parse any valid class modifiers"""
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                       'abstract', 'sealed', 'static', 'type')
    return self._parse_modifiers(valid_modifiers)

  def _parse_method_modifiers(self):
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                       'static', 'virtual', 'sealed', 'override', 'abstract',
                       'extern')
    return self._parse_modifiers(valid_modifiers)

  def _parse_property_modifiers(self):
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                       'static', 'virtual', 'sealed', 'override', 'abstract',
                       'extern')
    return self._parse_modifiers(valid_modifiers)

  def _parse_modifiers(self, valid_modifiers):
    modifiers = []
    self.skip_ws()
    while self.match(_identifier_re):
      modifier = self.matched_text
      if modifier in valid_modifiers:
        modifiers.append(modifier)
        self.skip_ws()
      else:
        self.backout()
        break
    return modifiers

  def _parse_returntype(self):
    # if (self.skip_word_and_ws('void')):
    #   return 'void'
    return self._parse_type()

  def _parse_attributes(self):
    attrs = []
    while self.skip_character('['):
      self.backout()
      attrs.append(self._parse_attribute_section())
      self.skip_ws()
    return attrs

  def _parse_attribute_section(self):
    self.swallow_character_and_ws('[')

    # Do we have an attribute target specifier?
    specifiers = ['field', 'event', 'method', 'param', 'property', 'return', 'type']
    self.match(_identifier_re)
    target = None
    if self.matched_text in specifiers:
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

  def _parse_type_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_class_type(self):
    #type-name
    #     object
    #     dynamic
    #     string
    self.match(_identifier_re)
    if self.matched_text in ("object", "dynamic", "string"):
      return self.matched_text
    self.backout()
    return self._parse_type_name()

  def _parse_namespace_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_namespace_or_type_name(self):
    # Effectively, list of .-separated identifier/type-argument-list pairs
    name = self._parse_identifier()
    args = self._parse_type_argument_list()
    tname = TypeInfo(name, args)

    if self.skip_character_and_ws('.'):
      # Grab another namespace
      tname._namespace = self._parse_namespace_or_type_name()
    return tname

  def _parse_type(self):
    """Parses a 'type'. Only simple, for now"""
    return self._parse_type_name()
    # self.match(_identifier_re)
    # match = self.matched_text
    # self.skip_ws()
    # return match

# identifier type-argument-listopt
# namespace-or-type-name . identifier type-argument-listopt qualified-alias-member




  def _find_visibility(self, modifiers):
    # Extract any visibility modifiers from this
    vis_modifiers = ('public', 'protected', 'private', 'internal')
    visibility = set(modifiers).intersection(set(vis_modifiers))
    if len(visibility) == 0:
      visibility = "public"
    else:
      visibility = visibility.pop()
    return visibility

class CSObject(ObjectDescription):
  def attach_name(self, signode, name):
    namespace = self.env.temp_data.get('cs:namespace')
    if namespace:
      for space in namespace.split('.'):
        signode += addnodes.desc_addname(space, space)
        signode += nodes.Text('.')
    signode += addnodes.desc_name(name, name)


  def attach_type(self, signode, typename):
    typename = full_type_name(typename)
    signode += nodes.emphasis(unicode(typename), unicode(typename))
    
  def attach_attributes(self, signode, attributes):
    aname = full_attribute_name(attributes)
    signode += nodes.emphasis(aname, aname)

  def attach_modifiers(self, signode, modifiers):
    for modifier in modifiers:
      signode += addnodes.desc_annotation(modifier, modifier)
      signode += nodes.Text(' ')

  # def handle_signature(self, sig, signode):
  #   parser = DefinitionParser(sig)
  #   rv = self.parse_definition(parser)
  
  # def parse_definition(self, parser):
  #   raise NotImplementedError()

  # def attach_modifiers(self, node, obj, visibility='public'):
  #     if obj.visibility != visibility:
  #         node += addnodes.desc_annotation(obj.visibility,
  #                                          obj.visibility)
  #         node += nodes.Text(' ')
  #     if obj.static:
  #         node += addnodes.desc_annotation('static', 'static')
  #         node += nodes.Text(' ')
  #     if getattr(obj, 'constexpr', False):
  #         node += addnodes.desc_annotation('constexpr', 'constexpr')
  #         node += nodes.Text(' ')

class CSClassObject(CSObject):
  # def parse_definition(self, parser):
  #   return parser.parse_class()
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_class()

        # modname = self.options.get(
        #     'module', self.env.temp_data.get('py:module'))
        # classname = self.env.temp_data.get('py:class')


    if info['visibility'] != 'public':
      signode += addnodes.desc_annotation(info["visibility"], info["visibility"])
      signode += nodes.Text(' ')
    if info['static']:
      signode += addnodes.desc_annotation('static', 'static')
      signode += nodes.Text(' ')

    signode += addnodes.desc_annotation('class ', 'class ')

    # Handle the name
    self.attach_name(signode, info['name'])
    
    if info['generic']:
      signode += addnodes.desc_annotation('<', '<')
      for node in info['typeargs']:
        signode += addnodes.desc_annotation(node, node)
        signode += nodes.Text(', ')
      signode.pop()
      signode += addnodes.desc_annotation('>', '>')

    if len(info['bases']) > 0:
      signode += nodes.Text(' : ')
      for base in info['bases']:
        self.attach_type(signode, base)
        signode += nodes.Text(', ')
      signode.pop()

    for (name, constraints) in info['typearg_constraints'].iteritems():
      signode += addnodes.desc_annotation(' where ', ' where ')
      signode += addnodes.desc_annotation(name, name)
      signode += addnodes.desc_annotation(' : ', ' : ')
      for constraint in constraints:
        signode += addnodes.desc_annotation(constraint, constraint)
        signode += addnodes.desc_annotation(', ', ', ')
      signode.pop()

class CSMethodObject(CSObject):
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_method()


class CSPropertyObject(CSObject):
    def handle_signature(self, sig, signode):
      parser = DefinitionParser(sig)
      info = parser.parse_property()
      raise ValueError()

class CSMemberObject(CSObject):
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_member()

    if type(info) is MethodInfo:
      return self.attach_method(signode, info)
    elif type(info) is PropertyInfo:
      return self.attach_property(signode, info)
    else:
      raise ValueError()

  def attach_method(self, signode, info):
    self.attach_modifiers(signode, info._modifiers)
    self.attach_type(signode, info._type)
    signode += nodes.Text(u' ')
    signode += addnodes.desc_name(str(info._name), str(info._name))

    paramlist = addnodes.desc_parameterlist()
    for arg in info._arguments:
      param = addnodes.desc_parameter('', '', noemph=True)
      if arg['attributes']:
        self.attach_attributes(param, arg['attributes'])
      self.attach_modifiers(param, arg['modifiers'])
      self.attach_type(param, arg['type'])
      param += nodes.Text(u' ')
      param += nodes.emphasis(unicode(arg['name']), unicode(arg['name']))

      if arg['default']:
        param += nodes.Text(u' = ')
        param += nodes.emphasis(arg['default'], arg['default'])

      paramlist += param
    signode += paramlist

  def attach_property(self, signode, info):
    pass


class CSCurrentNamespace(Directive):
  """
  This directive is just to tell Sphinx that we're documenting stuff in
  namespace foo.
  """

  has_content = False
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True
  option_spec = {}

  def run(self):
    env = self.state.document.settings.env
    if self.arguments[0].strip() in ('NULL', '0', 'nullptr', 'null'):
      env.temp_data['cs:namespace'] = None
    else:
      # Only allow alphanumeric and ./_

      # Parse the namespace definition
      parts = self.arguments[0].strip().split(".")
      if any([not valid_identifier(x) for x in parts]):
        self.state_machine.reporter.warning("Not a valid namespace: " + ".".join(parts),
                                            line=self.lineno)
      env.temp_data["cs:namespace"] = ".".join(parts)
    return []


class CSharpDomain(Domain):
  """C# language domain."""
  name = 'cs'
  label = 'C#'
  object_types = {
    'class': ObjType(l_('class'), 'class'),
      # 'function': ObjType(l_('function'), 'func'),
      # 'member':   ObjType(l_('member'),   'member'),
      # 'macro':    ObjType(l_('macro'),    'macro'),
      # 'type':     ObjType(l_('type'),     'type'),
      # 'var':      ObjType(l_('variable'), 'data'),
  }

  directives = {
      'class':        CSClassObject,
      'method':       CSMemberObject,
      'property':     CSPropertyObject,
      'member':       CSMemberObject,
      # 'property':     CSPropertyObject
      'namespace':    CSCurrentNamespace
  }

  roles = {
      # 'func' :  CXRefRole(fix_parens=True),
      # 'member': CXRefRole(),
      # 'macro':  CXRefRole(),
      # 'data':   CXRefRole(),
      # 'type':   CXRefRole(),
  }
  initial_data = {
      'objects': {},  # fullname -> docname, objtype
  }



def setup(app):
  app.add_domain(CSharpDomain)