"""wt-maxwell — witwin.maxwell solver-scene round-trip + FDTD solve + field viz.

Importing this package (eager: no ``activationEvents``):
  1. registers the maxwell scene components (solver / materials / sources /
     monitors / ports) via their ``@component`` decorators, and
  2. registers :class:`MaxwellAdapter` under the ``"maxwell"`` domain with
     ``register_platform_adapter`` so ``load_platform_scene`` / ``export_platform_scene``
     dispatch maxwell scenes here.

No ``witwin.maxwell`` import happens at module load: the adapter maps lazy-import
it inside their methods, so the plugin still registers its (schema-only) components
on a machine without the maxwell solver installed. The shared base layer
(the platform-bridge maps in ``witwin_server.api`` + the unified ``Material`` component) is in
core and frozen; this plugin only reads/writes it.
"""
from witwin_server.api import register_platform_adapter

from . import components  # noqa: F401  (side-effect: registers maxwell components)
from . import library_items  # noqa: F401  (side-effect: registers Maxwell library prefabs)
from .adapter import MaxwellAdapter

register_platform_adapter("maxwell", MaxwellAdapter())
