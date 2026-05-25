"""EMMaterial <-> maxwell.Material.

The maxwell adapter is the only adapter that reads the unified ``EMMaterial``
component's *advanced* fields (dispersion poles, diagonal anisotropy tensors,
Kerr) and builds the full ``maxwell.Material`` superset. The base
``MaterialMap`` (in core) handles only the scalar subset and builds a
``core.Material``; this builds a ``maxwell.Material`` instead.

M0 implements the scalar subset; advanced dispersion/anisotropy/Kerr are added in
M1 (with the platform's NotImplemented combination guards mirrored as errors).
"""
from typing import Any

from witwin_server.platform_bridge.material_map import _to_py


class MaterialAdapter:
    """Scalar EMMaterial <-> ``maxwell.Material`` (advanced fields added in M1)."""

    @staticmethod
    def to_platform(em: Any) -> Any:
        """Build a ``maxwell.Material`` from an EMMaterial component (scalar subset)."""
        import witwin.maxwell as mw

        name = str(em.material_name) if em.material_name else None
        return mw.Material(
            eps_r=float(_to_py(em.eps_r)),
            mu_r=float(_to_py(em.mu_r)),
            sigma_e=float(_to_py(em.sigma_e)),
            name=name,
        )
