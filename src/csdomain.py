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

  def parse_comma_list(self, terminators):
    """Parses a list of comma separated identifiers, terminated by some set"""
    results = []
    while self.match(_identifier_re):
      if self.matched_text in terminators:
        break
      results.append(self.matched_text)
      self.skip_character_and_ws(',')
    # Step backwards if we broke early
    if self.matched_text in terminators:
      self.backout()
    return results

  def parse_class(self):
    visibility, static = self._parse_visibility_static()
    # Skip the word partial, and class
    partial = self.skip_word_and_ws("partial")
    if not self.skip_word_and_ws("class"):
      self.fail("invalid class definition")
    # The Class Name
    self.match(_identifier_re)
    name = self.matched_text

    # Optional type-parameter list
    generic = self.skip_character_and_ws('<')
    generic_params = []
    if generic:
      generic_params = self.parse_comma_list(['>'])
      self.skip_character_and_ws('>')

    class_bases = []
    # (Optional) Class-bases next, starting with :
    if self.skip_character_and_ws(':'):
      class_bases = self.parse_comma_list(("where", "{"))

    # Optional type-parameter-constraints
    self.skip_ws()
    parameter_constraints = {}
    while self.skip_word_and_ws("where"):
      self.match(_identifier_re)
      parameter_name = self.matched_text
      # Check that this is in the argument list
      if not parameter_name in generic_params:
        fail("Class Type-Argument mismatch: Constraint on non-class parameter")
      self.skip_ws()
      self.skip_character_and_ws(":")
      print "State: " + self.definition[self.pos:]
      parameter_constraint_list = self.parse_comma_list(("where", "{"))
      # If we ended with new, swallow the ()
      if parameter_constraint_list[-1] == "new":
        self.skip_character('(')
        self.skip_character_and_ws(')')
        parameter_constraint_list[-1] = 'new()'

      parameter_constraints[parameter_name] = parameter_constraint_list



    # Print a summary of all information

    print "Remaining:  " + self.definition[self.pos:]

    print "Visibility: " + visibility
    print "Static:     {}".format(static)
    print "Partial:    {}".format(partial)
    print "ClassName:  {}".format(name)
    print "Generic:    {}".format(generic)
    if (generic):
      print "   Args:    {}".format(", ".join(generic_params))
      for arg in [x for x in generic_params if parameter_constraints.has_key(x)]:
        print "   Arg {}:   {}".format(arg, parameter_constraints[arg])
    if len(class_bases) > 0:
      print "Bases:      {}".format(", ".join(class_bases))

    return {
      'visibility': visibility,
      'static': static,
      'name': name,
      'generic': generic,
      'typeargs': generic_params,
      'bases': class_bases,
      'typearg_constraints': parameter_constraints
    }

  def _parse_class_modifiers(self):
    """Parse any valid class modifiers"""
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                 'abstract', 'sealed', 'static', 'type')
    modifiers = []
    self.skip_ws()
    while self.match(_identifier_re):
      modifier = self.matched_text
      print "Testing " + modifier + "({})".format(modifier in valid_modifiers)
      if modifier in valid_modifiers:
        modifiers.append(modifier)
        self.skip_ws()
      else:
        self.backout()
        break
    return modifiers

  def _parse_visibility_static(self):
    """Extract if the class is static, and it's visibility"""
    modifiers = self._parse_class_modifiers()
    print "{} modifiers: {}".format(len(modifiers), ",".join(modifiers))
    static = 'static' in modifiers

    # Extract any visibility modifiers from this
    vis_modifiers = ('public', 'protected', 'private', 'internal')
    visibility = set(modifiers).intersection(set(vis_modifiers))
    if len(visibility) == 0:
      visibility = "public"
    else:
      visibility = visibility.pop()

    return visibility, static

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
    print namespace

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