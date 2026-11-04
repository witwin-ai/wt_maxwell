"""Monitor interchange: maxwell monitors <-> studio monitor components.

Each maxwell monitor becomes a studio ``Empty`` object carrying one monitor
component (dispatch by ``monitor.kind``). ``FluxMonitor`` is emitted for a
``PlaneMonitor`` with ``compute_flux=True``; ``ClosedSurfaceMonitor`` is authored
as a box (center via Transform + extent via ``size``).
"""
from typing import Any

from witwin_server.api import SceneObject

from .common import axis_field, freqs_to_platform, freqs_to_studio, num, vec

MONITOR_COMPONENTS = ("PointMonitor", "PlaneMonitor", "FinitePlaneMonitor",
                      "ClosedSurfaceMonitor", "ModeMonitor")


class MonitorMap:
    """maxwell monitors <-> studio monitor objects."""

    @staticmethod
    def to_studio(monitor: Any) -> SceneObject:
        """Build an ``Empty`` monitor object from a maxwell monitor (dispatch by kind)."""
        from ..components.monitors import (
            ClosedSurfaceMonitorComponent,
            FinitePlaneMonitorComponent,
            ModeMonitorComponent,
            PlaneMonitorComponent,
            PointMonitorComponent,
        )

        obj = SceneObject(name=monitor.name or "Monitor", mesh_type="Empty")
        kind = str(monitor.kind)
        if kind == "point":
            MonitorMap._point_to_studio(obj.add_component(PointMonitorComponent()), obj, monitor)
        elif kind == "plane":
            MonitorMap._plane_to_studio(obj.add_component(PlaneMonitorComponent()), monitor)
        elif kind == "finite_plane":
            MonitorMap._finite_to_studio(obj.add_component(FinitePlaneMonitorComponent()), obj, monitor)
        elif kind == "closed_surface":
            MonitorMap._closed_to_studio(obj.add_component(ClosedSurfaceMonitorComponent()), obj, monitor)
        elif kind == "mode":
            MonitorMap._mode_to_studio(obj.add_component(ModeMonitorComponent()), obj, monitor)
        else:
            raise ValueError(f"unsupported maxwell monitor kind: {kind!r}")
        return obj

    @staticmethod
    def to_platform(obj: SceneObject) -> Any:
        """Rebuild a maxwell monitor from a studio monitor object (dispatch by component)."""
        import witwin.maxwell as mw

        if obj.get_component("PointMonitor") is not None:
            return MonitorMap._point_to_platform(mw, obj)
        if obj.get_component("PlaneMonitor") is not None:
            return MonitorMap._plane_to_platform(mw, obj)
        if obj.get_component("FinitePlaneMonitor") is not None:
            return MonitorMap._finite_to_platform(mw, obj)
        if obj.get_component("ClosedSurfaceMonitor") is not None:
            return MonitorMap._closed_to_platform(mw, obj)
        return MonitorMap._mode_to_platform(mw, obj)

    # --- PointMonitor --------------------------------------------------------

    @staticmethod
    def _point_to_studio(comp: Any, obj: SceneObject, monitor: Any) -> None:
        obj.get_component("Transform").position = list(monitor.position)
        comp.fields = list(monitor.fields)

    @staticmethod
    def _point_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("PointMonitor")
        return mw.PointMonitor(name=obj.name,
                               position=tuple(vec(obj.get_component("Transform").position)),
                               fields=tuple(str(f) for f in comp.fields))

    # --- PlaneMonitor / FluxMonitor ------------------------------------------

    @staticmethod
    def _plane_to_studio(comp: Any, monitor: Any) -> None:
        comp.axis = str(monitor.axis)
        comp.position = float(monitor.position)
        comp.fields = list(monitor.fields)
        comp.frequencies = freqs_to_studio(monitor.frequencies)
        comp.compute_flux = bool(monitor.compute_flux)
        comp.normal_direction = str(monitor.normal_direction)

    @staticmethod
    def _plane_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("PlaneMonitor")
        freqs = freqs_to_platform(comp.frequencies)
        if bool(comp.compute_flux):
            return mw.FluxMonitor(name=obj.name, axis=str(comp.axis), position=num(comp.position),
                                  frequencies=freqs, normal_direction=str(comp.normal_direction))
        return mw.PlaneMonitor(name=obj.name, axis=str(comp.axis), position=num(comp.position),
                               fields=tuple(str(f) for f in comp.fields), frequencies=freqs,
                               compute_flux=False, normal_direction=str(comp.normal_direction))

    # --- FinitePlaneMonitor --------------------------------------------------

    @staticmethod
    def _finite_to_studio(comp: Any, obj: SceneObject, monitor: Any) -> None:
        obj.get_component("Transform").position = list(monitor.position)
        comp.size = list(monitor.size)
        comp.fields = list(monitor.fields)
        comp.frequencies = freqs_to_studio(monitor.frequencies)
        comp.compute_flux = bool(monitor.compute_flux)
        comp.normal_direction = str(monitor.normal_direction)
        comp.face_label = monitor.face_label or ""
        comp.surface_name = monitor.surface_name or ""

    @staticmethod
    def _finite_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("FinitePlaneMonitor")
        return mw.FinitePlaneMonitor(
            name=obj.name, position=tuple(vec(obj.get_component("Transform").position)),
            size=tuple(vec(comp.size)), fields=tuple(str(f) for f in comp.fields),
            frequencies=freqs_to_platform(comp.frequencies), compute_flux=bool(comp.compute_flux),
            normal_direction=str(comp.normal_direction),
            face_label=str(comp.face_label) or None, surface_name=str(comp.surface_name) or None)

    # --- ClosedSurfaceMonitor ------------------------------------------------

    @staticmethod
    def _closed_to_studio(comp: Any, obj: SceneObject, monitor: Any) -> None:
        bounds = monitor.bounds
        center = [(bounds[i][0] + bounds[i][1]) / 2.0 for i in range(3)]
        extent = [bounds[i][1] - bounds[i][0] for i in range(3)]
        obj.get_component("Transform").position = center
        comp.size = extent
        comp.frequencies = freqs_to_studio(monitor.frequencies)

    @staticmethod
    def _closed_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("ClosedSurfaceMonitor")
        return mw.ClosedSurfaceMonitor.box(
            obj.name, position=tuple(vec(obj.get_component("Transform").position)),
            size=tuple(vec(comp.size)), frequencies=freqs_to_platform(comp.frequencies))

    # --- ModeMonitor ---------------------------------------------------------

    @staticmethod
    def _mode_to_studio(comp: Any, obj: SceneObject, monitor: Any) -> None:
        obj.get_component("Transform").position = list(monitor.position)
        comp.size = list(monitor.size)
        comp.mode_index = int(monitor.mode_index)
        comp.direction = str(monitor.direction)
        comp.polarization = axis_field(monitor.polarization_axis)
        comp.frequencies = freqs_to_studio(monitor.frequencies)
        comp.normal_direction = str(monitor.normal_direction)

    @staticmethod
    def _mode_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("ModeMonitor")
        return mw.ModeMonitor(
            name=obj.name, position=tuple(vec(obj.get_component("Transform").position)),
            size=tuple(vec(comp.size)), mode_index=int(comp.mode_index),
            direction=str(comp.direction), polarization=str(comp.polarization),
            frequencies=freqs_to_platform(comp.frequencies),
            normal_direction=str(comp.normal_direction))
