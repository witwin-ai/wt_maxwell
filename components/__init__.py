"""Maxwell scene components (auto-registered on import).

Each submodule defines ``@component`` classes that register themselves when the
module is imported. The unified ``EMMaterial`` material component lives in core
(``witwin_server.components``); this package only adds the maxwell-specific
configuration, region, source, monitor, port, and result components.
"""
from . import settings  # noqa: F401
from . import materials  # noqa: F401
from . import sources  # noqa: F401
from . import monitors  # noqa: F401
from . import ports  # noqa: F401
