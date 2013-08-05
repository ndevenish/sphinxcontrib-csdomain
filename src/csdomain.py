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

def valid_identifier(string):
  return _identifier_re.match(string) is not None

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
    match = None
    try:
      match = parser()
    except DefinitionError:
      match = None
    while match:
      if match in terminators:
        break
      results.append(self.matched_text)
      self.skip_character_and_ws(',')
      try:
        match = parser()
      except DefinitionError:
        match = None
    # Step backwards if we broke early
    if self.matched_text in terminators:
      self.backout()
    return results

  def parse_method(self):
    modifiers = self._parse_method_modifiers()
    self.skip_word_and_ws('partial')
    returntype = self._parse_returntype()
    
    # The member name
    name = self._parse_member_name()

    self.skip_character_and_ws('(')
    arguments = self._parse_formal_argument_list()
    self.skip_character_and_ws(')')
    # (
    # formal-parameter-listopt
    # )
    type_parameter_list = self._parse_type_parameter_list()

    #raise NotImplementedError("Need to read formal parameter list")

    constraints = self._parse_type_parameter_constraints_clauses()


    print "Parsing Method:"
    print "  Modifiers: {}".format(", ".join(modifiers))
    print "  Return:    {}".format(returntype)
    print "  Name:      {}".format(name)
    print "  Arguments: {}".format(len(arguments))
    for arg in arguments:
      argspec = ""
      if arg['attributes']:
        argspec += "["
        for attr in arg['attributes']:
          argspec += ", ".join(attr["attributes"])
        argspec += "] "
      if arg['modifiers']:
        argspec += " ".join(arg['modifiers']) + " "
      # argspec += arg['type'] + ' ' + arg['name']
      print "    {}{} {}".format(argspec, arg['type'], arg['name'])


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
      class_bases = self.parse_comma_list(("where", "{"))

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
      print "  Bases:      {}".format(", ".join(class_bases))

    return {
      'visibility': visibility,
      'static': static,
      'name': name,
      'generic': generic,
      'typeargs': generic_params,
      'bases': class_bases,
      'typearg_constraints': parameter_constraints
    }

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
    if (self.skip_word_and_ws('void')):
      return 'void'
    return self._parse_type()

  def _parse_attributes(self):
    attrs = []
    while self.skip_character('['):
      self.backout()
      attrs.append(self._parse_attribute_section())
      self.skip_ws()
    return attrs

  def _parse_attribute_section(self):
    self.skip_character_and_ws('[')
    
    # Do we have an attribute target specifier?
    specifiers = ['field', 'event', 'method', 'param', 'property', 'return', 'type']
    self.match(_identifier_re)
    target = None
    if self.matched_text in specifiers:
      target = self.matched_text
      self.skip_ws()
      self.skip_character_and_ws(':')
    else:
      self.backout()

    # Now, the main attribute list: One or more attributes, separated by commas
    attributes = self.parse_comma_list([r']'], self._parse_attribute)
    self.skip_character_and_ws(']')
    return {
      'target': target,
      'attributes': attributes
    }

  def _parse_attribute(self):
    name = self._parse_type_name()
    arguments = self._parse_attribute_arguments()
    return {
      'name': name,
      'args': arguments,
    }

  def _parse_attribute_arguments(self):
    if not self.skip_character_and_ws('('):
      return []
    # Skip anything until the end )
    self.match(re.compile(r"[^)]*"))
    value = self.matched_text
    self.skip_character_and_ws(')')
    return value

  def _parse_type_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_namespace_name(self):
    return self._parse_namespace_or_type_name()

  def _parse_namespace_or_type_name(self):
    # Effectively, list of .-separated identifier/type-argument-list pairs
    name = {}
    name['name'] = self._parse_identifier()
    name['args'] = self._parse_type_argument_list()
    if len(name['args']):
      name['full'] = "{}<{}>".format(name['name'], ', '.join(name['args']))
    else:
      name['full'] = name['name']

    names = [name]
    if self.skip_character_and_ws('.'):
      # Grab another namespace
      names.extend(self._parse_namespace_or_type_name)
    return names

  def _parse_type(self):
    """Parses a 'type'. Only simple, for now"""
    self.match(_identifier_re)
    match = self.matched_text
    self.skip_ws()
    return match

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
  pass  
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

    namespace = self.env.temp_data.get('cs:namespace')

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

    # Handle the namespace
    if namespace:
      for space in namespace.split('.'):
        signode += addnodes.desc_addname(space, space)
        signode += nodes.Text('.')
    signode += addnodes.desc_name(info['name'], info['name'])
    
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
        signode += nodes.emphasis(unicode(base), unicode(base))
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


        #     self.attach_modifiers(signode, cls)
        # signode += addnodes.desc_annotation('class ', 'class ')
        # self.attach_name(signode, cls.name)
        # if cls.bases:
        #     signode += nodes.Text(' : ')
        #     for base in cls.bases:
        #         self.attach_modifiers(signode, base, 'private')
        #         signode += nodes.emphasis(unicode(base.name),
        #                                   unicode(base.name))
        #         signode += nodes.Text(', ')
        #     signode.pop()  # remove the trailing comma


class CSMethodObject(CSObject):
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_method()


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
      'method':       CSMethodObject,
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