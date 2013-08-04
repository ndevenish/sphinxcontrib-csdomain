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

class DefinitionParser(object):
  def __init__(self, definition):
    self.definition = definition.strip()
    self.pos = 0
    self.end = len(self.definition)
    self.last_match = None
    self._previous_state = (0, None)

  def skip_word(self, word):
    return self.match(re.compile(r'\b%s\b' % re.escape(word)))

  def skip_ws(self):
    return self.match(_whitespace_re)

  def skip_word_and_ws(self, word):
    if self.skip_word(word):
      self.skip_ws()
      return True
    return False

  def match(self, regex):
    match = regex.match(self.definition, self.pos)
    if match is not None:
      self._previous_state = (self.pos, self.last_match)
      self.pos = match.end()
      self.last_match = match
      return True
    return False

  def parse_class(self):
    visibility, static = self._parse_visibility_static()
    # Skip the word class
    self.skip_word_and_ws("class")
    # Now, the type name
    name = self._parse_type()    


  def _parse_visibility_static(self):
    static = self.skip_word_and_ws('static')
    visibility = 'public'
    if self.match(_visibility_re):
        visibility = self.matched_text
    # If we didn't get static already, look again
    if not static:
      static = self.skip_word_and_ws('static')
    return visibility, static

  def _parse_type(self, in_template=False):
    result = []
    # This is where modifiers might be checked for... none for now
    
    # Loop, eating all path qualifiers
    while 1:
      self.skip_ws()
      if  (in_template and self.current_char in ',>') or \
          (result and not self.skip_string('.')) or self.eof:
          break
      result.append(self._parse_type_expr(in_template))

  def _parse_type_expr(self, in_template=False):
      typename = self._parse_name_or_template_arg(in_template)
      self.skip_ws()
      if not self.skip_string('<'):
          return typename

      args = []
      while 1:
          self.skip_ws()
          if self.skip_string('>'):
              break
          if args:
              if not self.skip_string(','):
                  self.fail('"," or ">" in template expected')
              self.skip_ws()
          args.append(self._parse_type(True))
      return TemplateDefExpr(typename, args)

  def _parse_name_or_template_arg(self, in_template):
    if not self.match(_identifier_re):
      if not in_template:
        self.fail('expected name')
      if not self.match(_identifier_re):
        self.fail('expected name or constant template argument')
      return ConstantTemplateArgExpr(self.matched_text.strip())
    identifier = self.matched_text

    return NameDefExpr(identifier)


  @property
  def matched_text(self):
    if self.last_match is not None:
      return self.last_match.group()

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