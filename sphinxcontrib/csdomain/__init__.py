
from .csdomain import CSharpDomain


def setup(app):
  # Need to do this, as nose relies on this method existing
  if hasattr(app, "add_domain"):
    app.add_domain(CSharpDomain)