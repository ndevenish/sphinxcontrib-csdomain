# coding: utf-8

from sphinx.util.compat import Directive
import os

from .parser import FileParser, opensafe

class CSAutodocModule(Directive):
  """
  Specifies the source file for autodoc
  """

  has_content = False
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True
  option_spec = {}

  def run(self):
    env = self.state.document.settings.env

    path = self.arguments[0]
    if not os.path.isfile(path):
      raise IOError("Could not read autodoc file {}".format(path))

    print "Set Autodoc path: " + path
    env.temp_data['cs:auto:module'] = path
    return []

class CSAutodoc(Directive):
  """Requests autodoc parsing of the specified module"""

  has_content = False
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True
  option_spec = {}

  def run(self):
    env = self.state.document.settings.env
    path = env.temp_data["cs:auto:module"]

    contents = opensafe(path).read()
    parser = FileParser(contents)
    cu = parser.parse_file()
    print "Parsed from file: " + repr(cu)

    todoc = self.arguments[0]
    print "Asked to document: " + todoc
    # Look for a class with this name
    potentials = [x for x in cu.iter_classes() if x.name == todoc]
    if len(potentials) != 1:
      print "ERROR: could not find class " + todoc

    obj = potentials[0]
    documentation = obj.documentation.parse_documentation()
    print obj.signature()
    print documentation

    for member in (x for x in obj.members if x.documentation):
      print member.signature()
    return []
  