

from .directives import CSAutodocModule, CSAutodoc

def setup(app):
  # Need to do this, as nose relies on this method existing
  if hasattr(app, "add_directive_to_domain"):
    app.add_directive_to_domain("cs", "autodoc", CSAutodoc)
    app.add_directive_to_domain("cs", "autodocmodule", CSAutodocModule)