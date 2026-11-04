"""MaterialRegion — maxwell topology-optimization region (maxwell-only component).

The material *component* is the shared unified ``Material`` (core); this adds
only the optimization region. It lives on an object that also carries a
``PlatformGeometry`` of ``kind="box"`` (the platform enforces Box-only regions).

The optimization design variable — the ``density`` tensor ``(Nx,Ny,Nz)`` — is
runtime/optimization state, not editor state, so only its **shape** and the
bounds round-trip; the values are never serialized (master §5.1). The adjoint /
optimization loop itself is out of scope for v1.
"""
from witwin_server.api import (
    Component,
    bool_field,
    component,
    float_field,
    int_field,
    string_field,
    vector2_field,
)

_CAT = "Simulation/Maxwell"


@component(name="MaterialRegion", category=_CAT)
class MaterialRegionComponent(Component):
    """Density-parameterized material region for topology optimization."""

    region_name = string_field("", description="Region name")
    basis = string_field("density", options=["density"], description="Parameterization basis")

    bounds = vector2_field([0.0, 1.0], description="Density input range (lower, upper)")
    eps_bounds = vector2_field([1.0, 1.0], description="Permittivity at density 0 / 1")
    mu_bounds = vector2_field([1.0, 1.0], description="Permeability at density 0 / 1")

    density_nx = int_field(8, min=1, horizontal_group="Density shape",
                           description="Design grid resolution (runtime values not stored)")
    density_ny = int_field(8, min=1, horizontal_group="Density shape")
    density_nz = int_field(8, min=1, horizontal_group="Density shape")

    use_filter = bool_field(False, description="Apply a density blur filter")
    filter_radius = float_field(0.1, min=1e-9, show_if="use_filter", description="Blur radius (m)")
    use_projection = bool_field(False, description="Apply tanh density projection")
    projection_beta = float_field(8.0, min=1e-9, show_if="use_projection",
                                  description="Projection sharpness (beta)")

    symmetry = string_field("", description="Optional density symmetry (e.g. 'density')")
