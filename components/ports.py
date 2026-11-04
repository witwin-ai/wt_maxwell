"""Maxwell port component.

``ModePort`` is kept as a single component (never expanded into source + monitor
in the editor, or the round trip is lost — master §5.1); the platform expands it
at solve time via ``Scene.resolved_sources()`` / ``resolved_monitors()``. When
``is_source`` is set, the port carries a temporal profile (the shared ``st_*``
fields, gated on ``is_source``).
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

from .source_time import (
    st_amplitude_field,
    st_auto_delay_field,
    st_delay_field,
    st_frequency_field,
    st_fwidth_field,
    st_kind_field,
    st_phase_field,
)

_CAT = "Simulation/Maxwell"
AXIS_POL = ["auto", "Ex", "Ey", "Ez"]


@component(name="ModePort", category=_CAT)
class ModePortComponent(Component):
    """Mode port -> ``maxwell.ModePort`` (position via Transform; emits source+monitor)."""

    size = vector3_field([1.0, 1.0, 0.0], description="Port plane size (one axis zero)")
    mode_index = int_field(0, min=0, description="Mode index")
    direction = string_field("+", options=["+", "-"], enum_toggle=True, description="Propagation sign")
    polarization = string_field("auto", options=AXIS_POL, description="Mode polarization")
    frequencies = list_field(float_field(1e9, min=0.0), default=[],
                             description="Port frequencies (Hz); empty = broadband")
    monitor_offset = float_field(0.0, description="Monitor plane offset along the normal (m)")
    normal_direction = string_field("+", options=["+", "-"], enum_toggle=True)

    is_source = bool_field(False, description="Port injects a source (carries a temporal profile)")
    st_kind = st_kind_field(gate="is_source")
    st_frequency = st_frequency_field(gate="is_source")
    st_amplitude = st_amplitude_field(gate="is_source")
    st_phase = st_phase_field(gate="is_source")
    st_fwidth = st_fwidth_field()
    st_auto_delay = st_auto_delay_field(gate="is_source")
    st_delay = st_delay_field()
