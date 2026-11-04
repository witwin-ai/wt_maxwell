"""Maxwell scene components (auto-registered on import).

Each submodule defines ``@component`` classes that register themselves when the
module is imported. The unified ``Material`` component (PBR + EM superset) lives in core
(``witwin_server.api.MaterialComponent``); this package only adds the maxwell-specific
configuration/solver, region, source, monitor, and port components.
"""
from . import solver  # noqa: F401
from . import materials  # noqa: F401
from . import sources  # noqa: F401
from . import monitors  # noqa: F401
from . import ports  # noqa: F401
