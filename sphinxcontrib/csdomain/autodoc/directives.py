# coding: utf-8

from docutils.parsers.rst import directives
from sphinx.util.compat import Directive
import os
from docutils import nodes
from docutils.statemachine import ViewList
from xml.etree.ElementTree import ParseError
from .parser import FileParser, opensafe
import glob

def _remove_source_file(filename, domaindata):
  """Remove all references to a source file"""
  namespaces = domaindata['namespaces']
  classes = domaindata['classes']
  modules = domaindata['modules']
  if modules.has_key(filename):
    del modules[filename]
  to_remove = []
  for entry in (x for x in classes.itervalues() if x.compilation_unit == filename):
    to_remove.append(entry)
    namespaces[str(entry.namespace)].remove(entry)
  for entry in to_remove:
    full_name = ".".join([str(entry.namespace), str(entry.name)])
    del classes[full_name]
  if to_remove:
    print "Removed classes " + str([x.name for x in to_remove])

def _parse_source_file(filename, domaindata):
  """Parse, or re-parse, a source file. Returns a bool indicating changes"""
  namespaces = domaindata['namespaces']
  classes = domaindata['classes']
  modules = domaindata['modules']
  
  # import pdb
  # pdb.set_trace()

  if not os.path.isfile(filename):
    # Just remove
    _remove_source_file(filename)
    return True

  stat = os.stat(filename)
  mtime = max(stat.st_mtime, stat.st_ctime)

  # If we have already parsed, check if we need to again
  if filename in modules:
    # Skip unchanged files
    if mtime <= modules[filename]:
      return False

  # Strip out all dictionary contents for this file
  _remove_source_file(filename, domaindata)

  print "C# Autodoc Parsing {}".format(filename)

  contents = opensafe(filename).read()
  parser = FileParser(contents)
  cu = parser.parse_file()
  modules[filename] = mtime
  # Append every class to the namespaces dictionary
  for cls in cu.iter_classes():
    cls.compilation_unit = filename
    namespaces[str(cls.namespace)].append(cls)
    classes[".".join([str(cls.namespace), str(cls.name)])] = cls

  return True

class CSAutodocModule(Directive):
  """
  Specifies the source file for autodoc
  """

  has_content = False
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True

  option_spec = {
      'tree': directives.flag,
  }

  def run(self):
    env = self.state.document.settings.env
    domaindata = env.domaindata['cs']

    # print "Classes in domain data: {}".format(len(domaindata['classes']))

    rel_filename, filename = env.relfn2path(self.arguments[0])

    tree_opt = 'tree' in self.options

    paths = []
    if not tree_opt:
      paths = glob.glob(filename)
    else:

      files = set()
      for filepath in glob.glob(filename):
        for (dirpath, _, filenames) in os.walk(filepath):
          for filename in filenames:
            if filename.endswith(".cs"):
              files.add(os.path.join(dirpath, filename))
      # print "Tree-walked: {}".format(files)
      paths = files

    if not paths:
      raise IOError("Could not read any autodoc modules {}".format(paths))

    # Read these files now
    for filename in paths:
      _parse_source_file(filename, domaindata)
      self.state.document.settings.record_dependencies.add(filename)

    return []

class CSAutodoc(Directive):
  """Requests autodoc parsing of the specified module"""

  has_content = True
  required_arguments = 1
  optional_arguments = 0
  final_argument_whitespace = True
  option_spec = {
    'all_members': directives.flag,
  }

  def run(self):
    env = self.state.document.settings.env
    # path = env.temp_data["cs:auto:module"]

    namespaces = env.domaindata['cs']['namespaces']
    classes = env.domaindata['cs']['classes']
    modules = env.domaindata['cs']['modules']

    todoc = self.arguments[0]
    print "Asked to document: " + todoc

    def _find_class_by_name(name):
      # print classes.keys()
      # Search the namespace dictionary for a class with this name
      # print "All Classes: " + str(", ".join(classes.keys()))
      # Look for a class with this name
      potential_names = [x for x in classes.iterkeys() if x.endswith(todoc)]
      potentials = [classes[x] for x in potential_names if classes[x].name == todoc]
      # print "Potentials: " + str(potentials)
      if len(potentials) == 0:
        print "ERROR: could not find class " + todoc
      elif len(potentials) > 1:
        print "ERROR: could not find unique class " + todoc
      return potentials[0]

    obj = _find_class_by_name(todoc)

    # Check the timestamp of the file this came from
    source = obj.compilation_unit
    self.state.document.settings.record_dependencies.add(source)
    # rescan this file (will not, if timestamps corrent)
    if _parse_source_file(source, env.domaindata['cs']):
      obj = _find_class_by_name(todoc)
    # if not os.path.isfile(source) or os.stat(source).st_mtime > modules[source]:
    #   # Re-parse, and re-find the class
    #   print "Re-scanning source file for {}".format(obj.name)
    #   _parse_source_file(source, env.domaindata['cs'])
    #   obj = _find_class_by_name(todoc)      
    #   # We need to reparse this file.

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
      try:
        parsed = obj.documentation.parse_documentation()
        lines.extend(parsed.splitlines())
      except ParseError as ex:
        self.state_machine.reporter.warning(
          "Error parsing documentation comments for {}.{}: {}. Skipping intelligent parse.".format(
            obj.namespace, obj.name, ex.message)
          )
        lines.extend(obj.documentation.parts)
      
    lines.append("")
    
    # Now, iterate through all members with documentation
    members = (x for x in obj.members if x.documentation)
    if "all_members" in self.options:
      members = obj.members

    for member in members:
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
      try:
        parsed = member.documentation.parse_documentation()
        lines.extend(parsed.splitlines())
      except ParseError as ex:
        self.state_machine.reporter.warning(
          "Error parsing documentation comments for {}.{}: {}. Skipping intelligent parse.".format(
            obj.namespace, obj.name, ex.message)
          )
      
    full_definition = [decl] + ["    " + line for line in lines]

    return ViewList(full_definition)