#coding: utf-8

import re

from docutils.parsers.rst import directives
from docutils import nodes

from sphinx.locale import l_, _
from sphinx.domains import Domain, ObjType
from sphinx.util.compat import Directive
from sphinx.directives import ObjectDescription
from sphinx.roles import XRefRole

from sphinx import addnodes

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')
# _visibility_re = re.compile(r'\b(public|private|protected)\b')
_whitespace_re = re.compile(r'\s+(?u)')

class MemberInfo(object):
  _attributes = []
  _modifiers = []
  _name = None
  _type = None
  _full_name = None

  @property
  def visibility(self):
    vis_modifiers = ('public', 'protected', 'private', 'internal')
    visibility = set(self._modifiers).intersection(set(vis_modifiers))
    if not visibility:
      return None
    return visibility.pop()


class MethodInfo(MemberInfo):
  _arguments = None
  valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                   'static', 'virtual', 'sealed', 'override', 'abstract',
                   'extern')

class PropertyInfo(MemberInfo):
  _setter = None
  _getter = None
  valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                   'static', 'virtual', 'sealed', 'override', 'abstract',
                   'extern')

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

class ClassInfo(object):
  _name = None
  _type_parameters = []
  _type_parameter_constraints = []
  _bases = []
  _modifiers = []
  _classlike_category = 'class'
  _partial = False

  @property
  def visibility(self):
    vis_modifiers = ('public', 'protected', 'private', 'internal')
    visibility = set(self._modifiers).intersection(set(vis_modifiers))
    if not visibility:
      return None
    return visibility.pop()

  @property
  def static(self):
    return 'static' in self._modifiers

class TypeInfo(object):
  _name = None
  _arguments = None
  _full = None
  _namespace = None

  def __init__(self, name, arguments=[]):
    self._name = name
    self._arguments = arguments

    if len(self._arguments):
      self._full = "{}<{}>".format(name, ', '.join(x.fqn() for x in arguments))
    else:
      self._full = name

  def fqn(self):
    alln = [self._full]
    if self._namespace:
      alln = [self._namespace.fqn(), self._full]
    return ".".join(alln)

  def deepest_namespace(self):
    if self._namespace:
      return self._namespace.deepest_namespace()
    return self
  def namespace_fqn(self):
    if self._namespace:
      return self._namespace.fqn()
    return None

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
      if not self.eof:
        raise DefinitionError("Unexpected token: '{}'; Expected '{}'".format(self.definition[self.pos], char))
      else:
        raise DefinitionError("Unexpected end-of-string; Expected '{}'".format(char))

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

  def parse_classlike(self):
    state = (self.pos, self.last_match)
    try:
      return self._parse_class()
    except DefinitionError:
      self.pos, self.last_match = state
    try:
      return self._parse_interface()
    except DefinitionError:
      self.pos, self.last_match = state
    raise ValueError("Could not read classlike object")


  def parse_class(self):
    clike = self._parse_class()
    return {
      'visibility': clike.visibility,
      'static': clike.static,
      'name': clike._name,
      'generic': len(clike._type_parameters) > 0,
      'typeargs': clike._type_parameters,
      'bases': clike._bases,
      'typearg_constraints': clike._type_parameter_constraints
    }

  def _parse_class(self):
    clike = ClassInfo()

    clike._modifiers = self._parse_class_modifiers()
    clike._partial = self.skip_word_and_ws("partial")
    self.swallow_character_and_ws('class')
    clike._full_name = self._parse_type_name()
    clike._name = clike._full_name._name
    # Optional type-parameter list
    clike._type_parameters = [x._name for x in clike._full_name._arguments]

    # (Optional) Class-bases next, starting with :
    if self.skip_character_and_ws(':'):
      clike._bases = self.parse_comma_list(("where", "{"), self._parse_type_name)

    # Optional type-parameter-constraints
    self.skip_ws()
    clike._type_parameter_constraints = self._parse_type_parameter_constraints_clauses()

    # # Print a summary of all information
    # print "Parsing Class:"
    # print "  Visibility: " + visibility
    # print "  Static:     {}".format(static)
    # print "  Partial:    {}".format(partial)
    # print "  ClassName:  {}".format(name)
    # print "  Generic:    {}".format(generic)
    # if (generic):
    #   print "     Args:    {}".format(", ".join(generic_params))
    #   for arg in [x for x in generic_params if parameter_constraints.has_key(x)]:
    #     print "     Arg {}:   {}".format(arg, parameter_constraints[arg])
    # if len(class_bases) > 0:
    #   print "  Bases:      {}".format(", ".join([str(x) for x in class_bases]))

    return clike

  def parse_property(self):
    return self._parse_property_declaration()

  def parse_member(self):
    return self._parse_class_member_declaration()

  def _parse_interface(self):
    cinfo = ClassInfo()

    cinfo._attributes = self._parse_attributes()
    cinfo._modifiers = self._parse_modifiers(('new', 'public', 'protected',
      'internal', 'private'))
    cinfo._partial = self.skip_word_and_ws('partial')
    self.swallow_character_and_ws('interface')
    cinfo._classlike_category = 'interface'
    cinfo._full_name = self._parse_type_name()
    cinfo._name = cinfo._full_name._name
    cinfo._type_parameters = [x._name for x in cinfo._full_name._arguments]
    if self.skip_character_and_ws(':'):
      cinfo._bases = self.parse_comma_list(("where", "{"), self._parse_type_name)
    cinfo._type_parameter_constraints = self._parse_type_parameter_constraints_clauses()

    return cinfo


#     attributesopt interface-modifiersopt partialopt interface
# identifier variant-type-parameter-listopt interface-baseopt
# 504
# Copyright © Microsoft Corporation 1999-2012. All Rights Reserved.
# type-parameter-constraints-clausesopt
# interface-modifiers:
# interface-modifier
# interface-modifiers interface-modifier
# interface-body ;opt
# interface-modifier:
#          new
#          public
#          protected
#          internal
#          private
  def _parse_method_header(self):
    method = MethodInfo()
    method._attributes = self._parse_attributes()
    method._modifiers = self._parse_method_modifiers()
    self.skip_word_and_ws('partial')
    method._type = self._parse_returntype()
    
    # The member name
    method._full_name = self._parse_type_name()
    # method._name = self._parse_member_name()
    method._name = method._full_name._name

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
    try:
      return self._parse_property_declaration()
    except DefinitionError:
      self.pos, self.last_match = state
    try:
      return self._parse_constructor_declaration()
    except DefinitionError:
      self.pos, self.last_match = state

    raise ValueError("Could not determine member type for " + self.definition[self.pos:])

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

  def _parse_constructor_declaration(self):
    method = MethodInfo()
    method._attributes = self._parse_attributes()
    method._modifiers = self._parse_constructor_modifiers()
    method._full_name = self._parse_type_name()
    method._name = method._full_name._name

    self.swallow_character_and_ws('(')
    method._arguments = self._parse_formal_argument_list()
    self.swallow_character_and_ws(')')
    return method

  def _parse_property_declaration(self):
    prop = PropertyInfo()

    prop._attributes = self._parse_attributes()
    prop._modifiers = self._parse_property_modifiers()
    prop._type = self._parse_type()
    prop._full_name = self._parse_type_name()
    prop._name = prop._full_name._name
    
    self.swallow_character_and_ws('{')
    ac = self._parse_accessor_declaration()
    if ac:
      if ac._name == "get":
        prop._getter = ac
      else:
        prop._setter = ac
    try:
      ac = self._parse_accessor_declaration()
      if ac:
        if ac._name == "get":
          prop._getter = ac
        else:
          prop._setter = ac
    except DefinitionError:
      pass

    self.swallow_character_and_ws('}')
    return prop

  def _parse_accessor_declaration(self):
    ai = MemberInfo()
    ai._attributes = self._parse_attributes()
    ai._modifiers = self._parse_modifiers(('protected', 'internal', 'private'))
    # Reduce the modifiers
    ai._visibility = None
    if len(ai._modifiers) > 1:
      ai._modifiers.remove("internal")
      ai._modifiers.remove("protected")
      ai._visibility = "internal protected"
    elif len(ai._modifiers) == 1:
      ai._visibility = ai._modifiers[0]

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

  def _parse_constructor_modifiers(self):
    valid_modifiers = ('public', 'protected', 'internal', 'private', 'extern')
    return self._parse_modifiers(valid_modifiers)

  def _parse_method_modifiers(self):
    return self._parse_modifiers(MethodInfo.valid_modifiers)

  def _parse_property_modifiers(self):
    return self._parse_modifiers(PropertyInfo.valid_modifiers)

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
    # print "Remaining after initial parse: "  +self.definition[self.pos:]
    if self.skip_character_and_ws('.'):
      # Grab another namespace
      newname = self._parse_namespace_or_type_name()
      newname.deepest_namespace()._namespace = tname

      tname = newname
    return tname

  def _parse_type(self):
    """Parses a 'type'. Only simple, for now"""
    return self._parse_type_name()

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

  option_spec = {
      'namespace': directives.unchanged,
  }


  def attach_name(self, signode, namespace, name):
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

  def attach_visibility(self, signode, visibility):
    if visibility and visibility != self.env.temp_data.get('cs:visibility'):
      signode += addnodes.desc_annotation(visibility, visibility)
      signode += nodes.Text(' ')

  def before_content(self):
    self.parentname_set = False
    lastname = self.names and self.names[-1]
    if lastname and not self.env.temp_data.get('cs:parent'):
        assert isinstance(lastname, TypeInfo)
        self.env.temp_data['cs:parent'] = lastname
        self.parentname_set = True
    else:
        self.parentname_set = False

  def after_content(self):
    if self.parentname_set:
      self.env.temp_data['cs:parent'] = None


class CSClassObject(CSObject):
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    clike = parser.parse_classlike()

    # Work out our namespace by combining sources
    namespace = self.options.get('namespace', 
      self.env.temp_data.get('cs:namespace'))
    if namespace:
      # Merge the classlike type namespace with this namespace to give a fqn
      given_namespace = DefinitionParser(namespace)._parse_namespace_name()
      given_fqn = given_namespace.fqn()
      clike_fqn = clike._full_name.fqn()
      if not clike_fqn.startswith(given_fqn):
        clike._full_name.deepest_namespace()._namespace = given_namespace
      # Re-assign the resolved namespace
      namespace = clike._full_name.namespace_fqn()

    # parentname = self.env.temp_data.get('cs:parent')

    visibility = clike.visibility
    modifiers = clike._modifiers
    if visibility in modifiers:
      modifiers.remove(visibility)
    self.attach_visibility(signode, visibility)

    if clike.static:
      modifiers.remove('static')
      signode += addnodes.desc_annotation('static', 'static')
      signode += nodes.Text(' ')
    for modifier in modifiers:
      signode += addnodes.desc_annotation(modifier, modifier)
      signode += nodes.Text(' ')

    clike_category = clike._classlike_category + " "
    signode += addnodes.desc_annotation(clike_category, clike_category)

    # Handle the name
    self.attach_name(signode, namespace, clike._name)
    
    if clike._type_parameters:
      signode += addnodes.desc_annotation('<', '<')
      for node in clike._type_parameters:
        signode += addnodes.desc_annotation(node, node)
        signode += nodes.Text(', ')
      signode.pop()
      signode += addnodes.desc_annotation('>', '>')

    if clike._bases:
      signode += nodes.Text(' : ')
      for base in clike._bases:
        self.attach_type(signode, base)
        signode += nodes.Text(', ')
      signode.pop()

    for (name, constraints) in clike._type_parameter_constraints.iteritems():
      signode += addnodes.desc_annotation(' where ', ' where ')
      signode += addnodes.desc_annotation(name, name)
      signode += addnodes.desc_annotation(' : ', ' : ')
      for constraint in constraints:
        signode += addnodes.desc_annotation(constraint, constraint)
        signode += addnodes.desc_annotation(', ', ', ')
      signode.pop()

    return clike._full_name

class CSMemberObject(CSObject):


  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_member()

    namespace = self.options.get('namespace', 
      self.env.temp_data.get('cs:namespace'))
    parentname = self.env.temp_data.get('cs:parent')
    if namespace:
      namespace_type = DefinitionParser(namespace)._parse_namespace_name()
      # Validate these are compatible
      if parentname:
        if not parentname.fqn().startswith(namespace_type.fqn()):
          raise ValueError("Namespace Mismatch")
        namespace_type = parentname

      # Now, re-resolve with the parsed namespace
      if not info._full_name.fqn().startswith(namespace_type.fqn()):
        info._full_name.deepest_namespace()._namespace = namespace_type
        namespace = info._full_name.namespace_fqn()

    print "Member {} within namespace: {}".format(info._name, namespace)
    print "   In Class: {}".format(parentname)

    if type(info) is MethodInfo:
      self.attach_method(signode, info)
    elif type(info) is PropertyInfo:
      self.attach_property(signode, info)
    else:
      raise ValueError()
    return info._full_name

  def attach_method(self, signode, info):

    visibility = info.visibility
    if visibility in info._modifiers:
      info._modifiers.remove(visibility)
    self.attach_visibility(signode, visibility)
    self.attach_modifiers(signode, info._modifiers)
    if info._type:
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
    # accessor-declarations }
    self.attach_attributes(signode, info._attributes)
    self.attach_modifiers(signode, info._modifiers)
    self.attach_type(signode, info._type)
    signode += nodes.Text(u' ')
    signode += addnodes.desc_name(str(info._name), str(info._name))
    
    signode += nodes.Text(u'{ ')
    if info._getter:
      if info._getter._visibility:
        self.attach_modifiers(signode, [info._getter._visibility])
      signode += nodes.Text(' get; ')
    if info._setter:
      if info._setter._visibility:
        self.attach_modifiers(signode, [info._setter._visibility])
      signode += nodes.Text(' set; ')
    signode += nodes.Text(u'}')


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
      parser = DefinitionParser(self.arguments[0])
      name = parser._parse_namespace_name()
      env.temp_data["cs:namespace"] = name.fqn()
    return []

class CSDefaultVisibility(Directive):
  """This tells sphinx what the default visibility is"""
  has_content = False
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True
  option_spec = {}

  def run(self):
    env = self.state.document.settings.env
    vis = self.arguments[0].strip().lower()
    if vis in ('public', 'protected', 'internal', 'private'):
      env.temp_data["cs:visibility"] = vis
    else:
      env.temp_data['cs:visibility'] = None
    return []

class CSXRefRole(XRefRole):
  pass

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
      'interface':    CSClassObject,
      'method':       CSMemberObject,
      'property':     CSMemberObject,
      'member':       CSMemberObject,
      
      'namespace':    CSCurrentNamespace,
      'visibility':   CSDefaultVisibility,
  }

  roles = {
    'class':      CSXRefRole(),
    'member':     CSXRefRole(),
    'interface':  CSXRefRole(),
    'method':     CSXRefRole(),
    'property':   CSXRefRole(),
    
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