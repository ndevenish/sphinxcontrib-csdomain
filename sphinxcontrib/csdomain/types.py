# coding: utf-8

class MemberInfo(object):
  _attributes = []
  _modifiers = []
  _name = None
  _type = None
  _full_name = None
  _member_category = 'member'

  @property
  def visibility(self):
    vis_modifiers = ('public', 'protected', 'private', 'internal')
    visibility = set(self._modifiers).intersection(set(vis_modifiers))
    if not visibility:
      return None
    return visibility.pop()

  def print_summary(self):
    print "{}: {}".format(self._member_category, self._full_name.fqn())
    print "  Modifiers: {}".format(", ".join(self._modifiers))
    print "  Return:    {}".format(self._type)


class MethodInfo(MemberInfo):
  _member_category = "method"
  _arguments = None
  valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                   'static', 'virtual', 'sealed', 'override', 'abstract',
                   'extern')
  def print_summary(self):
    super(MethodInfo, self).print_summary()
    print "  Arguments: {}".format(len(self._arguments))
    for arg in self._arguments:
      argspec = ""
      if arg['attributes']:
        argspec += full_attribute_name(arg['attributes']) + " "
      if arg['modifiers']:
        argspec += " ".join(arg['modifiers']) + " "
      # argspec += arg['type'] + ' ' + arg['name']
      print "    {}{} {}".format(argspec, arg['type'], arg['name'])


class PropertyInfo(MemberInfo):
  _member_category = "property"
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
  
  def flatten_namespace(self):
    if self._namespace:
      return self._namespace.flatten_namespace() + [self._full]
    return [self._full]

  def merge_onto(self, namespace):
    """Merges the existing typeinfo onto another namespace."""
    if not namespace:
      return
    if not self.fqn().startswith(namespace.fqn()):
      self.deepest_namespace()._namespace = namespace

  def __str__(self):

    return self.fqn()

  def __repr__(self):
    return "<Type: {}>".format(self._full)
