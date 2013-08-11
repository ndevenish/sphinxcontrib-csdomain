
from directives import CSAutodoc, CSAutodocModule

def setup(app):
  app.add_directive_to_domain("cs", "autodoc", CSAutodoc)
  app.add_directive_to_domain("cs", "autodocmodule", CSAutodocModule)