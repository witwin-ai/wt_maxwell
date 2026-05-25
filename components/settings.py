"""Scene-level maxwell configuration components.

These live on a single ``Maxwell Settings`` object (mesh_type ``Empty``). The
adapter recognizes that object by the presence of a :class:`MaxwellDomain`
component and reads the four components back into a ``maxwell.Scene``:

    MaxwellDomain        -> Domain(((x0,x1),(y0,y1),(z0,z1)))
    MaxwellGrid          -> GridSpec.uniform(dl) / GridSpec.anisotropic(dx,dy,dz)
    MaxwellBoundary      -> BoundarySpec.<kind>(...) / BoundarySpec.faces(...)
    MaxwellSolveSettings -> Scene(subpixel_samples=, symmetry=, device=) + solve frequencies

Units: meters, Hz. Boundary frequencies are not a ``Scene`` attribute (they are a
solve parameter), so they live here and feed the M4 solve, not the scene round trip.
"""
from witwin_server.components import (
    Component,
    bool_field,
    component,
    float_field,
    int_field,
    list_field,
    string_field,
    vector3_field,
)

# Boundary kinds, mirrored from maxwell.BoundaryKind.
BOUNDARY_KINDS = ["none", "pml", "periodic", "bloch", "pec", "pmc"]
# Per-axis symmetry planes, mirrored from Scene.symmetry entries.
SYMMETRY_KINDS = ["none", "PEC", "PMC"]
_CAT = "Simulation/Maxwell"


@component(name="MaxwellDomain", category=_CAT)
class MaxwellDomainComponent(Component):
    """Simulation bounds -> ``maxwell.Domain``. Marks the Maxwell Settings object."""

    bounds_min = vector3_field([-1.0, -1.0, -1.0], description="Domain min corner (m)")
    bounds_max = vector3_field([1.0, 1.0, 1.0], description="Domain max corner (m)")


@component(name="MaxwellGrid", category=_CAT)
class MaxwellGridComponent(Component):
    """Yee grid spacing -> ``GridSpec.uniform`` / ``GridSpec.anisotropic``."""

    uniform = bool_field(True, description="Use a single spacing for all axes")
    dl = float_field(0.05, min=1e-9, show_if="uniform", description="Uniform cell size (m)")
    dx = float_field(0.05, min=1e-9, hide_if="uniform", description="Cell size along x (m)")
    dy = float_field(0.05, min=1e-9, hide_if="uniform", description="Cell size along y (m)")
    dz = float_field(0.05, min=1e-9, hide_if="uniform", description="Cell size along z (m)")


@component(name="MaxwellBoundary", category=_CAT)
class MaxwellBoundaryComponent(Component):
    """Boundary conditions -> ``BoundarySpec`` (global / per-axis / per-face)."""

    mode = string_field("global", options=["global", "per_axis", "per_face"],
                        enum_toggle=True, description="Boundary specification scope")

    # global default kind (also the per_face/per_axis default)
    kind = string_field("pml", options=BOUNDARY_KINDS, description="Boundary kind")
    num_layers = int_field(15, min=1, show_if={"field_name": "kind", "operator": "eq", "value": "pml"},
                           description="PML layers")
    strength = float_field(1e6, min=0.0, show_if={"field_name": "kind", "operator": "eq", "value": "pml"},
                           description="PML strength")
    bloch_wavevector = vector3_field(
        [0.0, 0.0, 0.0],
        show_if={"field_name": "kind", "operator": "eq", "value": "bloch"},
        description="Bloch wavevector (rad/m)")

    # per-axis overrides
    x = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"})
    y = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"})
    z = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"})

    # per-face overrides
    x_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})
    x_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})
    y_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})
    y_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})
    z_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})
    z_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"})


@component(name="MaxwellSolveSettings", category=_CAT)
class MaxwellSolveSettingsComponent(Component):
    """Subpixel / symmetry / device + solve frequency list."""

    subpixel_uniform = bool_field(True, description="One subpixel sample count for all axes")
    subpixel = int_field(1, min=1, show_if="subpixel_uniform",
                         description="Subpixel material samples per axis")
    subpixel_x = int_field(1, min=1, hide_if="subpixel_uniform")
    subpixel_y = int_field(1, min=1, hide_if="subpixel_uniform")
    subpixel_z = int_field(1, min=1, hide_if="subpixel_uniform")

    symmetry_x = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to x")
    symmetry_y = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to y")
    symmetry_z = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to z")

    device = string_field("cuda", options=["cuda", "cpu"], enum_toggle=True,
                          description="Solve device (FDFD/FDTD require CUDA)")
    frequencies = list_field(float_field(1e9, min=0.0), default=[],
                             description="Solve frequencies (Hz)")
