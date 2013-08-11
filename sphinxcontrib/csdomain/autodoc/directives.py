# coding: utf-8

from sphinx.util.compat import Directive
import os
from docutils import nodes
from docutils.statemachine import ViewList

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


    rel_filename, filename = env.relfn2path(self.arguments[0])
    print rel_filename, filename
    
    path = filename
    if not os.path.isfile(path):
      raise IOError("Could not read autodoc file {}".format(path))

    # for fn in self.filename_set:
    self.state.document.settings.record_dependencies.add(path)

    print "Set Autodoc path: " + path
    env.temp_data['cs:auto:module'] = path
    return []

class CSAutodoc(Directive):
  """Requests autodoc parsing of the specified module"""

  has_content = True
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
    # print "Parsed from file: " + repr(cu)

    todoc = self.arguments[0]
    print "Asked to document: " + todoc
    # Look for a class with this name
    potentials = [x for x in cu.iter_classes() if x.name == todoc]
    if len(potentials) != 1:
      print "ERROR: could not find class " + todoc

    obj = potentials[0]
    # print obj.signature()
    # print documentation

    # print "Generating REST"

    # if obj.name == "DB":
    #   try:
    #     self.rest_for_class(obj)
    #   except:
    #     import pdb
    #     pdb.post_mortem()
    #     raise


    rest = self.rest_for_class(obj)

    # print "Parsing internally"
    node = nodes.paragraph()
    node.document = self.state.document
    self.state.nested_parse(rest, 0, node)

    # import pdb
    # pdb.set_trace()
    # for member in (x for x in obj.members if x.documentation):
    #   print member.signature()
    return node.children

  def rest_for_class(self, obj):
    decl = "..  cs:class:: " + obj.signature()
    lines = []
    if obj.namespace:
      lines.append(":namespace: " + str(obj.namespace))
    # Get the documentation for this class
    if obj.documentation:
      lines.append("")
      lines.extend(obj.documentation.parse_documentation().splitlines())
    lines.append("")
    
    # Now, iterate through all members with documentation
    for member in (x for x in obj.members if x.documentation):
      lines.extend(self.rest_for_member(member))
      lines.append("")

    full_definition = [decl] + ["    " + line for line in lines]

    # print "====="
    # print "\n".join(full_definition)
    # print "====="
    return ViewList(full_definition)


  def rest_for_member(self, member):
    decl = "..  cs:member:: " + member.signature()

    lines = []
    if member.namespace:
      lines.append(":namespace: " + str(member.namespace))

    if member.documentation:
      lines.append("")
      lines.extend(member.documentation.parse_documentation().splitlines())

    full_definition = [decl] + ["    " + line for line in lines]

    return ViewList(full_definition)