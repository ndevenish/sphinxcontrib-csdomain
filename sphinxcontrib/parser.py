# coding: utf-8

import re
from .types import *

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')
# _visibility_re = re.compile(r'\b(public|private|protected)\b')
_whitespace_re = re.compile(r'\s+(?u)')

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

  @staticmethod
  def ParseNamespace(name):
    return DefinitionParser(name)._parse_namespace_name()


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
    method._member_category = "constructor"
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
