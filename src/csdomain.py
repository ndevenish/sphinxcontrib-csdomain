#coding: utf-8

import re
from sphinx.locale import l_, _
from sphinx.domains import Domain, ObjType
from sphinx.util.compat import Directive
from sphinx.directives import ObjectDescription

from docutils import nodes
from sphinx import addnodes

_identifier_re = re.compile(r'(~?\b[a-zA-Z_][a-zA-Z0-9_]*)\b')
_visibility_re = re.compile(r'\b(public|private|protected)\b')
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

  @property
  def matched_text(self):
    if self.last_match is not None:
      return self.last_match.group()

  @property
  def eof(self):
      return self.pos >= self.end

  def parse_class(self):
    self._parse_class_modifiers()
    visibility, static = self._parse_visibility_static()
    # Skip the word partial, and class
    partial = self.skip_word_and_ws("partial")
    if not self.skip_word_and_ws("class"):
      self.fail("invalid class definition")
    # The Class Name
    self.match(_identifier_re)
    name = self.matched_text

    # Optional type-parameter list
    generic = self.skip_word_and_ws('<')
    generic_params = []
    if generic:
      # List of identifiers, ended with >
      while not self.match(re.compile(r'>')):
        match = self.match(_identifier_re)
        generic_params.append(self.matched_text)
        self.match(re.compile(r','))
        self.skip_ws()
      self.skip_ws()


    # Print a summary of all information
    print "Visibility: " + visibility
    print "Static:     {}".format(static)
    print "Partial:    {}".format(partial)
    print "ClassName:  {}".format(name)
    print "Generic:    {}".format(generic)
    if (generic):
      print "   Args:    {}".format(", ".join(generic_params))



  def _parse_class_modifiers(self):
    """Parse any valid class modifiers"""
    valid_modifiers = ('new', 'public', 'protected', 'internal', 'private',
                 'abstract', 'sealed', 'static', 'type')
    modifiers = []
    self.match(_identifier_re)
    modifier = self.matched_text
    while modifier in valid_modifiers:
      modifiers.append(modifier)
      self.skip_ws()
      self.match(_identifier_re)
      modifier = self.matched_text  
    self.backout()
    return modifiers

  def _parse_visibility_static(self):
    """Extract if the class is static, and it's visibility"""
    modifiers = self._parse_class_modifiers()
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
  
  def handle_signature(self, sig, signode):
    parser = DefinitionParser(sig)
    rv = self.parse_definition(parser)
  
  def parse_definition(self, parser):
    raise NotImplementedError()

class CSClassObject(CSObject):
  def parse_definition(self, parser):
    return parser.parse_class()

class CSMemberObject(CSObject):
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
      env.temp_data['cs:prefix'] = None
    else:
      # Only allow alphanumeric and ./_

      # Parse the namespace definition
      parts = self.arguments[0].strip().split(".")
      if any([not valid_identifier(x) for x in parts]):
        self.state_machine.reporter.warning("Not a valid namespace: " + ".".join(parts),
                                            line=self.lineno)
      env.temp_data["cs:prefix"] = ".".join(parts)
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