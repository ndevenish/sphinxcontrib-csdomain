#coding: utf-8

import re

from docutils.parsers.rst import directives
from docutils import nodes

from sphinx.locale import l_, _
from sphinx.domains import Domain, ObjType
from sphinx.util.compat import Directive
from sphinx.directives import ObjectDescription
from sphinx.roles import XRefRole
from sphinx.util.docfields import Field, GroupedField
from sphinx.util.nodes import make_refnode

from sphinx import addnodes

from .parser import DefinitionParser, DefinitionError
from .types import TypeInfo, MethodInfo, PropertyInfo, ClassInfo

def valid_identifier(string):
  return _identifier_re.match(string) is not None

def full_type_name(type_name):
  """Returns a type name list to a full string"""
  return type_name
  # return ".".join(x['full'] for x in type_name)

def full_attribute_name(attribute_info):
  """Returns an attribute dictionary to a full string"""

  return " ".join(str(x) for x in attribute_info)

class CSObject(ObjectDescription):

  option_spec = {
      'namespace': directives.unchanged,
  }

  doc_field_types = [
    GroupedField('parameter', label=l_('Parameters'),
                 names=('param', 'parameter', 'arg', 'argument'),
                 can_collapse=True),
    GroupedField('exceptions', label=l_('Throws'), rolename='cpp:class',
                 names=('throws', 'throw', 'exception'),
                 can_collapse=True),
    Field('returnvalue', label=l_('Returns'), has_arg=False,
          names=('returns', 'return')),
    ]


  def resolve_current_namespace(self):
    namespace = self.env.temp_data.get('cs:namespace')
    parentname = self.env.temp_data.get('cs:parent')
    if parentname:
      namespace = parentname.fqn()
    if self.options.get('namespace', False):
      namespace = self.options.get('namespace')
    if namespace and parentname and not namespace.startswith(parentname.fqn()):
      self.state_machine.reporter.warning(
        "Child namespace {} does not appear to be child of parent {}"
        .format(namespace, parentname)
        , line=self.lineno)
    return namespace

  def resolve_previous_namespace(self):
    namespace = self.env.temp_data.get('cs:namespace')
    parentname = self.env.temp_data.get('cs:parent')
    if parentname:
      namespace = parentname.fqn()
    return namespace

  def add_target_and_index(self, name, sig, signode):
    idname = name._full_name.fqn()

    if idname not in self.state.document.ids:
      signode['names'].append(idname)
      signode['ids'].append(idname)
      signode['first'] = (not self.names)
      self.state.document.note_explicit_target(signode)

      self.env.domaindata['cs']['objects'].setdefault(idname, 
        (self.env.docname, self.objtype, name))

      indextext = self.get_index_text(name)
      if indextext:
          self.indexnode['entries'].append(('single', indextext, idname, ''))

  def get_index_text(self, name):
      return None

  def attach_name(self, signode, full_name):
    """Attaches a fully qualified TypeInfo name to the node tree"""
    # Get the previous namespace
    # import pdb
    # pdb.set_trace()
    prev_namespace = self.resolve_previous_namespace()
    if prev_namespace:
      curr = full_name.fqn()
      if full_name.fqn().startswith(prev_namespace) and not full_name.fqn() == prev_namespace:
        # print "Partially filled by parent: "
        # print "Previous namespace: '{}'".format(prev_namespace)
        # print "  Cutting from " + full_name.fqn()
        new_fqn = full_name.fqn()[len(prev_namespace):]
        if new_fqn[0] == ".":
          new_fqn = new_fqn[1:]
        # print "New fqn is: " + new_fqn
        full_name = DefinitionParser.ParseNamespace(new_fqn)
        # print "            to " + full_name.fqn()

    names = full_name.flatten_namespace()

    for space in names[:-1]:
      signode += addnodes.desc_addname(space, space)
      signode += nodes.Text('.')

    signode += addnodes.desc_name(names[-1], names[-1])


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
    # print "Vis: {}/{}".format(visibility,self.env.temp_data.get('cs:visibility'))
    if visibility and visibility != self.env.temp_data.get('cs:visibility'):
      signode += addnodes.desc_annotation(visibility, visibility)
      signode += nodes.Text(' ')

  def before_content(self):
    self.parentname_set = False
    lastname = self.names and self.names[-1]
    if lastname and not self.env.temp_data.get('cs:parent'):
        assert isinstance(lastname._full_name, TypeInfo)
        self.previous_parent = self.env.temp_data.get('cs:parent')
        self.env.temp_data['cs:parent'] = lastname._full_name
        self.parentname_set = True
    else:
        self.parentname_set = False

  def after_content(self):
    if self.parentname_set:
      self.env.temp_data['cs:parent'] = self.previous_parent


class CSClassObject(CSObject):

  def get_index_text(self, name):
    return _('{} (C# {})'.format(name._name, name._classlike_category))

  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    clike = parser.parse_classlike()

    # Use the current namespace to build a fully qualified name
    curr_namespace = self.resolve_current_namespace()
    clike._full_name.merge_onto(curr_namespace)
    # print "Fully Qualified Class name: " + clike._full_name.fqn()

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
    self.attach_name(signode, clike._full_name)
    
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

    return clike

class CSMemberObject(CSObject):

  def get_index_text(self, name):
    membertype = name._member_category
    return _('{} (C# {})'.format(name._name, membertype))

  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    info = parser.parse_member()

    namespace = self.resolve_current_namespace()
    if namespace:
      namespace_type = DefinitionParser(namespace)._parse_namespace_name()

      # Now, re-resolve with the parsed namespace
      if not info._full_name.fqn().startswith(namespace_type.fqn()):
        info._full_name.deepest_namespace()._namespace = namespace_type
        namespace = info._full_name.namespace_fqn()

    # print "Member {} within namespace: {}".format(info._name, namespace)
    # print "   In Class: {}".format(parentname)

    if type(info) is MethodInfo:
      self.attach_method(signode, info)
    elif type(info) is PropertyInfo:
      self.attach_property(signode, info)
    else:
      raise ValueError()
    return info

  def attach_method(self, signode, info):

    visibility = info.visibility
    if visibility in info._modifiers:
      info._modifiers.remove(visibility)
    self.attach_visibility(signode, visibility)
    self.attach_modifiers(signode, info._modifiers)
    if info._type:
      self.attach_type(signode, info._type)
      signode += nodes.Text(u' ')
    # signode += addnodes.desc_name(str(info._name), str(info._name))

    # self.attach_name(signode, namespace, info._name)
    namespace = self.resolve_current_namespace()

    # nstype = TypeInfo.FromNamespace(namespace)
    # print namespace
    # print nstype.flatten_namespace()
    self.attach_name(signode, info._full_name)

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
    visibility = info.visibility
    if visibility in info._modifiers:
      info._modifiers.remove(visibility)
    self.attach_visibility(signode, visibility)

    self.attach_attributes(signode, info._attributes)
    self.attach_modifiers(signode, info._modifiers)
    self.attach_type(signode, info._type)
    signode += nodes.Text(u' ')
    # signode += addnodes.desc_name(str(info._name), str(info._name))
    
    namespace = self.resolve_current_namespace()

    # nstype = TypeInfo.FromNamespace(namespace)
    # print namespace
    # print nstype.flatten_namespace()
    self.attach_name(signode, info._full_name)


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

  def find_obj(self, env, namespace, typ, target, node):
    objects = self.data['objects']
    # Find anything with the target
    matches = [x for x in objects.iterkeys() if x.lower().endswith(target.lower())]
    # print "Found: " + str(matches)
    if len(matches) > 1:
      env.warn_node('more than one target found for cross-reference ', node)
    if len(matches) == 1:
      return objects[matches[0]]

    # Try direct names (ignoring, e.g. arguments)
    matches = [x for x in objects.itervalues() if target.lower() == x[2]._name.lower()]
    if len(matches) == 1:
      return matches[0]

    # Try a different approach. Look for all keys with this in
    matches = [x for x in objects.iterkeys() if target.lower() in x.lower()]
    if matches:
      # print "Anywhere matches: " + str(matches)
      def _sort_match(x, y):
        tgt = target.lower()
        return cmp(len(x) - x.lower().index(tgt), len(y) - y.lower().index(tgt))
      matches.sort(cmp=_sort_match)
      # print "Best Match: " + str(matches[0])
      env.warn_node('Could not find explicit node for {}, using fallback of nearest-end: {}'
        .format(target, matches[0]), node)



  def resolve_xref(self, env, fromdocname, builder,
                   typ, target, node, contnode):
    # print "Resolving XRef"
    # print "  fromdocname: {}".format(fromdocname)
    # print "  builder:     {}".format(builder)
    # print "  typ:         {}".format(typ)
    # print "  target:      {}".format(target)
    # print "  node:        {}".format(node)
    # print "  contnode:    {}".format(contnode)

    # Firstly, parse this node into C# form
    target_t = DefinitionParser.ParseNamespace(target)
    target = target_t.fqn()

    match = self.find_obj(env, None, typ, target, node)
    if not match:
      return None

    # print "Found match: " + str(match)
    return make_refnode(builder, fromdocname, 
      match[0],match[2]._full_name.fqn(), contnode, target)

  def get_objects(self):
    for refname, (docname, typen, fullname) in self.data['objects'].items():
      yield (refname, refname, typen, docname, refname, 1)

  def clear_doc(self, docname):
    for fullname, (fn, _, _) in self.data['objects'].items():
      if fn == docname:
        del self.data['objects'][fullname]
