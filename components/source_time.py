"""Shared temporal-profile (source_time) field builders.

The CW / GaussianPulse / RickerWavelet profile is nested into both source
components (:mod:`components.sources`) and ``ModePort`` (:mod:`components.ports`).
Defining the field schema once here keeps it consistent; the conversion logic
lives once in ``adapter/source_map.py`` (:class:`SourceTimeMap`). Each builder
takes the name of the boolean ``gate`` field that enables the profile so a source
can gate on ``st_enabled`` while a port gates on ``is_source``.
"""
from witwin_server.core.components import bool_field, float_field, string_field

GROUP = "Source Time"
TIME_KINDS = ["cw", "gaussian_pulse", "ricker"]


def st_enabled_field():
    return bool_field(True, group=GROUP, description="Source has a temporal profile")


def st_kind_field(gate: str = "st_enabled"):
    return string_field("cw", options=TIME_KINDS, enum_toggle=True, group=GROUP,
                        show_if=gate, description="Temporal profile")


def st_frequency_field(gate: str = "st_enabled"):
    return float_field(1e9, min=0.0, group=GROUP, show_if=gate, description="Center frequency (Hz)")


def st_amplitude_field(gate: str = "st_enabled"):
    return float_field(1.0, group=GROUP, show_if=gate, description="Amplitude")


def st_phase_field(gate: str = "st_enabled"):
    return float_field(0.0, group=GROUP, show_if=gate, description="Phase (rad)")


def st_fwidth_field():
    return float_field(1e8, min=0.0, group=GROUP,
                       show_if={"field_name": "st_kind", "operator": "eq", "value": "gaussian_pulse"},
                       description="Spectral width (Hz)")


def st_auto_delay_field(gate: str = "st_enabled"):
    return bool_field(True, group=GROUP, show_if=gate, description="Auto-compute pulse delay")


def st_delay_field():
    return float_field(0.0, min=0.0, group=GROUP, hide_if="st_auto_delay", description="Pulse delay (s)")
