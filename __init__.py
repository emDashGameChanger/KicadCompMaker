# __init__.py  (inside KicadCompMaker/ folder)

from .plugin import DigikeyPlugin

# Create an instance and register it with pcbnew
# This is what makes the plugin appear in Tools → External Plugins
DigikeyPlugin().register()
