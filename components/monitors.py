"""Maxwell monitor components.

Each monitor becomes a ``SceneObject`` (mesh_type ``Empty``). Monitors with a 3D
position (Point / FinitePlane / ClosedSurface / Mode) use the object's
``Transform``; ``PlaneMonitor`` stores its scalar plane position as a field.

``FluxMonitor`` is not a separate component: it is a ``PlaneMonitor`` with
``compute_flux=True`` (the adapter emits a ``FluxMonitor`` for that case and a
``PlaneMonitor`` otherwise). ``ClosedSurfaceMonitor`` is authored as a box
(center via Transform + extent via ``size``); the six faces are derived by the
platform, not expanded into editor objects.
"""
from witwin_server.api import (
    Component,
    bool_field,
    component,
    float_field,
    int_field,
    list_field,
    string_field,
    vector3_field,
)
from .mode_profiles import ModeProfilesMixin

_CAT = "Simulation/Maxwell"
FIELD_COMPONENTS = ["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]
AXIS_POL = ["auto", "Ex", "Ey", "Ez"]


def _fields_field():
    return list_field(string_field("Ez", options=FIELD_COMPONENTS), default=["Ez"],
                      description="Recorded field components")


def _frequencies_field():
    return list_field(float_field(1e9, min=0.0), default=[],
                      description="Monitor frequencies (Hz); empty = broadband DFT")


@component(name="PointMonitor", category=_CAT)
class PointMonitorComponent(Component):
    """Single-point field probe -> ``maxwell.PointMonitor`` (position via Transform)."""

    fields = _fields_field()


@component(name="PlaneMonitor", category=_CAT)
class PlaneMonitorComponent(Component):
    """Axis-aligned infinite plane -> ``maxwell.PlaneMonitor`` / ``FluxMonitor``."""

    axis = string_field("z", options=["x", "y", "z"], enum_toggle=True, description="Plane normal axis")
    position = float_field(0.0, description="Plane position along the axis (m)")
    fields = _fields_field()
    frequencies = _frequencies_field()
    compute_flux = bool_field(False, description="Compute Poynting flux (emits a FluxMonitor)")
    normal_direction = string_field("+", options=["+", "-"], enum_toggle=True)


@component(name="FinitePlaneMonitor", category=_CAT)
class FinitePlaneMonitorComponent(Component):
    """Finite rectangular plane -> ``maxwell.FinitePlaneMonitor`` (position via Transform)."""

    size = vector3_field([1.0, 1.0, 0.0], description="Plane size (one axis zero-thickness)")
    fields = _fields_field()
    frequencies = _frequencies_field()
    compute_flux = bool_field(False, description="Compute Poynting flux")
    normal_direction = string_field("+", options=["+", "-"], enum_toggle=True)
    face_label = string_field("", description="Internal face label (ClosedSurface)", no_sync=True)
    surface_name = string_field("", description="Internal surface name (ClosedSurface)", no_sync=True)


@component(name="ClosedSurfaceMonitor", category=_CAT)
class ClosedSurfaceMonitorComponent(Component):
    """Closed box surface -> ``maxwell.ClosedSurfaceMonitor.box`` (center via Transform)."""

    size = vector3_field([1.0, 1.0, 1.0], description="Box extent (m)")
    frequencies = _frequencies_field()


@component(name="ModeMonitor", category=_CAT)
class ModeMonitorComponent(ModeProfilesMixin, Component):
    """Waveguide mode monitor -> ``maxwell.ModeMonitor`` (position via Transform)."""

    size = vector3_field([1.0, 1.0, 0.0], description="Mode plane size (one axis zero)")
    mode_index = int_field(0, min=0, description="Mode index")
    direction = string_field("+", options=["+", "-"], enum_toggle=True, description="Propagation sign")
    polarization = string_field("auto", options=AXIS_POL, description="Mode polarization")
    frequencies = _frequencies_field()
    normal_direction = string_field("+", options=["+", "-"], enum_toggle=True)
