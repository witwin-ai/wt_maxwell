"""Port interchange: maxwell ModePort <-> studio ModePort component.

A ``ModePort`` round-trips as a single object/component (never expanded into a
source + monitor in the editor — the platform expands it at solve time). When the
port injects a source (``is_source``), it carries a temporal profile via the
shared :class:`SourceTimeMap` (gated on ``is_source``).
"""
from typing import Any

from witwin_server.api import SceneObject

from .common import axis_field, freqs_to_platform, freqs_to_studio, num, vec
from .source_map import SourceTimeMap

PORT_COMPONENTS = ("ModePort",)


class PortMap:
    """maxwell ``ModePort`` <-> studio ModePort object."""

    @staticmethod
    def to_studio(port: Any) -> SceneObject:
        """Build an ``Empty`` port object from a maxwell ``ModePort``."""
        from ..components.ports import ModePortComponent

        obj = SceneObject(name=port.name or "ModePort", mesh_type="Empty")
        comp = obj.add_component(ModePortComponent())
        obj.get_component("Transform").position = list(port.position)
        comp.size = list(port.size)
        comp.mode_index = int(port.mode_index)
        comp.direction = str(port.direction)
        comp.polarization = axis_field(port.polarization_axis)
        comp.frequencies = freqs_to_studio(port.frequencies)
        comp.monitor_offset = float(port.monitor_offset)
        comp.normal_direction = str(port.normal_direction)
        comp.is_source = SourceTimeMap.to_studio(comp, port.source_time)
        return obj

    @staticmethod
    def to_platform(obj: SceneObject) -> Any:
        """Rebuild a maxwell ``ModePort`` from a studio port object."""
        import witwin.maxwell as mw

        comp = obj.get_component("ModePort")
        return mw.ModePort(
            name=obj.name, position=tuple(vec(obj.get_component("Transform").position)),
            size=tuple(vec(comp.size)), mode_index=int(comp.mode_index),
            direction=str(comp.direction), polarization=str(comp.polarization),
            frequencies=freqs_to_platform(comp.frequencies),
            source_time=SourceTimeMap.to_platform(comp, bool(comp.is_source)),
            monitor_offset=num(comp.monitor_offset),
            normal_direction=str(comp.normal_direction))
