"""Test session setup.

SQLAlchemy resolves relationship targets lazily, so a test module that imports
one model pulls in a graph the other modules do not. A module that reaches
``blog.domain.models`` without ``orders`` fails at collection time with
"expression 'Payment.order_id' failed to locate a name" — a message that looks
like a broken model rather than a half-imported registry.

Importing the application's model modules once, here, configures every mapper
before any test module is collected. Tests then stop carrying a hand-maintained
list of imports that nobody remembers to update when a relationship is added.
"""

from __future__ import annotations

import importlib
import pkgutil

import app.modules


def _import_every_model_module() -> None:
    """Import every ``<pkg>.domain.models`` under ``app.modules``."""
    for module in pkgutil.walk_packages(app.modules.__path__, "app.modules."):
        name = module.name
        if name.endswith(".domain.models") or name.endswith(".domain.wp_parity_models"):
            importlib.import_module(name)


_import_every_model_module()
