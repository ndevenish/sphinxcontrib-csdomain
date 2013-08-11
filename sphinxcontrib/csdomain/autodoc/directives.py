from sphinx.util.compat import Directive
import os

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
  