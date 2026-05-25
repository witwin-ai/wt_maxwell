"""Maxwell source components + the nested temporal profile (source_time).

Each source becomes a ``SceneObject`` (mesh_type ``Empty``); position-bearing
sources (PointDipole, ModeSource) use the object's ``Transform`` for position,
while direction-only sources (PlaneWave, GaussianBeam) carry their direction as a
field (lossless, master §5.1).

The temporal profile (CW / GaussianPulse / RickerWavelet) is nested into every
source as ``st_*`` fields gated by ``st_kind`` (master §4.5). To keep the schema
in one place, the field *builders* live as module-level ``_st_*`` functions and
each source lists which it uses; the conversion logic lives once in
``adapter/source_map.py``.
"""
from witwin_server.components import (
    Component,
    bool_field,
    component,
    float_field,
    int_field,
    string_field,
    vector3_field,
)

_CAT = "Simulation/Maxwell"
_ST_GROUP = "Source Time"
TIME_KINDS = ["cw", "gaussian_pulse", "ricker"]
AXIS_POL = ["auto", "Ex", "Ey", "Ez"]
INJECTION_AXES = ["auto", "x", "y", "z"]


# --- temporal-profile field builders (one definition, reused per source) ------

def _st_enabled():
    return bool_field(True, group=_ST_GROUP, description="Source has a temporal profile")


def _st_kind():
    return string_field("cw", options=TIME_KINDS, enum_toggle=True, group=_ST_GROUP,
                        show_if="st_enabled", description="Temporal profile")


def _st_frequency():
    return float_field(1e9, min=0.0, group=_ST_GROUP, show_if="st_enabled",
                       description="Center frequency (Hz)")


def _st_amplitude():
    return float_field(1.0, group=_ST_GROUP, show_if="st_enabled", description="Amplitude")


def _st_phase():
    return float_field(0.0, group=_ST_GROUP, show_if="st_enabled", description="Phase (rad)")


def _st_fwidth():
    return float_field(1e8, min=0.0, group=_ST_GROUP,
                       show_if={"field_name": "st_kind", "operator": "eq", "value": "gaussian_pulse"},
                       description="Spectral width (Hz)")


def _st_auto_delay():
    return bool_field(True, group=_ST_GROUP, show_if="st_enabled",
                      description="Auto-compute pulse delay")


def _st_delay():
    return float_field(0.0, min=0.0, group=_ST_GROUP, hide_if="st_auto_delay",
                       description="Pulse delay (s)")


@component(name="PointDipoleSource", category=_CAT)
class PointDipoleSourceComponent(Component):
    """Point dipole -> ``maxwell.PointDipole`` (position via Transform)."""

    polarization_mode = string_field("Ez", options=["Ex", "Ey", "Ez", "vector"],
                                     description="Dipole polarization")
    polarization = vector3_field([0.0, 0.0, 1.0],
                                 show_if={"field_name": "polarization_mode", "operator": "eq", "value": "vector"},
                                 description="Polarization vector")
    width = float_field(0.02, min=1e-9, description="Source width (m)")
    profile = string_field("gaussian", options=["gaussian", "ideal"], enum_toggle=True)

    st_enabled = _st_enabled()
    st_kind = _st_kind()
    st_frequency = _st_frequency()
    st_amplitude = _st_amplitude()
    st_phase = _st_phase()
    st_fwidth = _st_fwidth()
    st_auto_delay = _st_auto_delay()
    st_delay = _st_delay()


@component(name="PlaneWaveSource", category=_CAT)
class PlaneWaveSourceComponent(Component):
    """Plane wave -> ``maxwell.PlaneWave`` (direction-only; soft or TFSF injection)."""

    direction = vector3_field([0.0, 0.0, 1.0], description="Propagation direction (unit)")
    polarization = vector3_field([1.0, 0.0, 0.0], description="Polarization (perp. direction)")
    injection = string_field("soft", options=["soft", "tfsf"], enum_toggle=True)
    injection_axis = string_field("auto", options=INJECTION_AXES, description="Injection axis")
    tfsf_min = vector3_field([-0.5, -0.5, -0.5],
                             show_if={"field_name": "injection", "operator": "eq", "value": "tfsf"},
                             description="TFSF region min corner (m)")
    tfsf_max = vector3_field([0.5, 0.5, 0.5],
                             show_if={"field_name": "injection", "operator": "eq", "value": "tfsf"},
                             description="TFSF region max corner (m)")

    st_enabled = _st_enabled()
    st_kind = _st_kind()
    st_frequency = _st_frequency()
    st_amplitude = _st_amplitude()
    st_phase = _st_phase()
    st_fwidth = _st_fwidth()
    st_auto_delay = _st_auto_delay()
    st_delay = _st_delay()


@component(name="GaussianBeamSource", category=_CAT)
class GaussianBeamSourceComponent(Component):
    """Gaussian beam -> ``maxwell.GaussianBeam`` (PlaneWave fields + waist/focus)."""

    direction = vector3_field([0.0, 0.0, 1.0], description="Propagation direction (unit)")
    polarization = vector3_field([1.0, 0.0, 0.0], description="Polarization (perp. direction)")
    beam_waist = float_field(0.5, min=1e-9, description="Beam waist (m)")
    focus = vector3_field([0.0, 0.0, 0.0], description="Focus point (m)")
    injection = string_field("soft", options=["soft", "tfsf"], enum_toggle=True)
    injection_axis = string_field("auto", options=INJECTION_AXES, description="Injection axis")
    tfsf_min = vector3_field([-0.5, -0.5, -0.5],
                             show_if={"field_name": "injection", "operator": "eq", "value": "tfsf"},
                             description="TFSF region min corner (m)")
    tfsf_max = vector3_field([0.5, 0.5, 0.5],
                             show_if={"field_name": "injection", "operator": "eq", "value": "tfsf"},
                             description="TFSF region max corner (m)")

    st_enabled = _st_enabled()
    st_kind = _st_kind()
    st_frequency = _st_frequency()
    st_amplitude = _st_amplitude()
    st_phase = _st_phase()
    st_fwidth = _st_fwidth()
    st_auto_delay = _st_auto_delay()
    st_delay = _st_delay()


@component(name="ModeSource", category=_CAT)
class ModeSourceComponent(Component):
    """Waveguide mode source -> ``maxwell.ModeSource`` (position via Transform)."""

    size = vector3_field([1.0, 1.0, 0.0], description="Mode plane size (one axis zero)")
    mode_index = int_field(0, min=0, description="Mode index")
    direction = string_field("+", options=["+", "-"], enum_toggle=True, description="Propagation sign")
    polarization = string_field("auto", options=AXIS_POL, description="Mode polarization")

    st_enabled = _st_enabled()
    st_kind = _st_kind()
    st_frequency = _st_frequency()
    st_amplitude = _st_amplitude()
    st_phase = _st_phase()
    st_fwidth = _st_fwidth()
    st_auto_delay = _st_auto_delay()
    st_delay = _st_delay()
