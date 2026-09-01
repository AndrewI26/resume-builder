"""Importing this package registers every mapped class.

SQLAlchemy resolves ``relationship()`` targets by name when mappers are first
configured, so a class named only as a string — ``User.oauth_accounts`` names
``OAuthAccount`` — has to have been imported by then or the first query fails.

The app reaches every model transitively through its routers, which is why
this only ever bites somewhere with a narrower import graph: the PDF worker
loads one service, not the whole application. Walking the package here means
importing any model is enough to make all of them resolvable.
"""

import importlib
import pkgutil

for _module in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_module.name}")
