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
    component,
    float_field,
    int_field,
    string_field,
    vector3_field,
)

from .source_time import (
    st_amplitude_field,
    st_auto_delay_field,
    st_delay_field,
    st_enabled_field,
    st_frequency_field,
    st_fwidth_field,
    st_kind_field,
    st_phase_field,
)

_CAT = "Simulation/Maxwell"
AXIS_POL = ["auto", "Ex", "Ey", "Ez"]
INJECTION_AXES = ["auto", "x", "y", "z"]


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

    st_enabled = st_enabled_field()
    st_kind = st_kind_field()
    st_frequency = st_frequency_field()
    st_amplitude = st_amplitude_field()
    st_phase = st_phase_field()
    st_fwidth = st_fwidth_field()
    st_auto_delay = st_auto_delay_field()
    st_delay = st_delay_field()


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

    st_enabled = st_enabled_field()
    st_kind = st_kind_field()
    st_frequency = st_frequency_field()
    st_amplitude = st_amplitude_field()
    st_phase = st_phase_field()
    st_fwidth = st_fwidth_field()
    st_auto_delay = st_auto_delay_field()
    st_delay = st_delay_field()


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

    st_enabled = st_enabled_field()
    st_kind = st_kind_field()
    st_frequency = st_frequency_field()
    st_amplitude = st_amplitude_field()
    st_phase = st_phase_field()
    st_fwidth = st_fwidth_field()
    st_auto_delay = st_auto_delay_field()
    st_delay = st_delay_field()


@component(name="ModeSource", category=_CAT)
class ModeSourceComponent(Component):
    """Waveguide mode source -> ``maxwell.ModeSource`` (position via Transform)."""

    size = vector3_field([1.0, 1.0, 0.0], description="Mode plane size (one axis zero)")
    mode_index = int_field(0, min=0, description="Mode index")
    direction = string_field("+", options=["+", "-"], enum_toggle=True, description="Propagation sign")
    polarization = string_field("auto", options=AXIS_POL, description="Mode polarization")

    st_enabled = st_enabled_field()
    st_kind = st_kind_field()
    st_frequency = st_frequency_field()
    st_amplitude = st_amplitude_field()
    st_phase = st_phase_field()
    st_fwidth = st_fwidth_field()
    st_auto_delay = st_auto_delay_field()
    st_delay = st_delay_field()
