"""Source interchange: maxwell sources <-> studio source components.

Each maxwell source becomes a studio ``Empty`` object carrying one source
component; position-bearing sources also use the object's ``Transform``. The
nested temporal profile (``st_*`` fields) is handled once by :class:`SourceTimeMap`
and shared by every source (and by ``ModePort`` in M3).
"""
from typing import Any, Optional

from witwin_server import SceneObject

from .common import axis_field as _axis_from_letter
from .common import axis_name as _axis_name
from .common import num as _f
from .common import vec as _vec

# Studio component name per maxwell source ``kind``.
SOURCE_COMPONENTS = ("PointDipoleSource", "PlaneWaveSource", "GaussianBeamSource", "ModeSource")


class SourceTimeMap:
    """Nested ``st_*`` fields <-> ``maxwell`` temporal profile (CW/GaussianPulse/Ricker)."""

    @staticmethod
    def to_platform(comp: Any, enabled: bool) -> Optional[Any]:
        """Build a ``SourceTime`` from a component's ``st_*`` fields (None if not enabled).

        ``enabled`` is passed explicitly so the gate field can be ``st_enabled``
        (sources) or ``is_source`` (ports).
        """
        if not enabled:
            return None
        import witwin.maxwell as mw

        kind = str(comp.st_kind)
        frequency, amplitude = _f(comp.st_frequency), _f(comp.st_amplitude)
        if kind == "cw":
            return mw.CW(frequency=frequency, amplitude=amplitude, phase=_f(comp.st_phase))
        delay = None if bool(comp.st_auto_delay) else _f(comp.st_delay)
        if kind == "gaussian_pulse":
            return mw.GaussianPulse(frequency=frequency, fwidth=_f(comp.st_fwidth),
                                    amplitude=amplitude, phase=_f(comp.st_phase), delay=delay)
        return mw.RickerWavelet(frequency=frequency, amplitude=amplitude, delay=delay)

    @staticmethod
    def to_studio(comp: Any, source_time: Any) -> bool:
        """Write a ``SourceTime`` (or None) onto a component's ``st_*`` fields.

        Returns whether a profile was present so the caller can set its gate field.
        """
        if source_time is None:
            return False
        comp.st_frequency = float(source_time.frequency)
        comp.st_amplitude = float(source_time.amplitude)
        kind = str(source_time.kind)
        if kind == "cw":
            comp.st_kind = "cw"
            comp.st_phase = float(source_time.phase)
        elif kind == "gaussian_pulse":
            comp.st_kind = "gaussian_pulse"
            comp.st_phase = float(source_time.phase)
            comp.st_fwidth = float(source_time.fwidth)
            comp.st_auto_delay = False
            comp.st_delay = float(source_time.delay)
        else:  # ricker_wavelet
            comp.st_kind = "ricker"
            comp.st_auto_delay = False
            comp.st_delay = float(source_time.delay)
        return True


class SourceMap:
    """maxwell sources <-> studio source objects."""

    @staticmethod
    def to_studio(source: Any) -> SceneObject:
        """Build an ``Empty`` source object from a maxwell source (dispatch by kind)."""
        from ..components.sources import (
            GaussianBeamSourceComponent,
            ModeSourceComponent,
            PlaneWaveSourceComponent,
            PointDipoleSourceComponent,
        )

        obj = SceneObject(name=source.name or "Source", mesh_type="Empty")
        kind = str(source.kind)
        if kind == "point_dipole":
            SourceMap._dipole_to_studio(obj.add_component(PointDipoleSourceComponent()), obj, source)
        elif kind == "plane_wave":
            SourceMap._plane_to_studio(obj.add_component(PlaneWaveSourceComponent()), source)
        elif kind == "gaussian_beam":
            SourceMap._beam_to_studio(obj.add_component(GaussianBeamSourceComponent()), source)
        elif kind == "mode_source":
            SourceMap._mode_to_studio(obj.add_component(ModeSourceComponent()), obj, source)
        else:
            raise ValueError(f"unsupported maxwell source kind: {kind!r}")
        return obj

    @staticmethod
    def to_platform(obj: SceneObject) -> Any:
        """Rebuild a maxwell source from a studio source object (dispatch by component)."""
        import witwin.maxwell as mw

        if obj.get_component("PointDipoleSource") is not None:
            return SourceMap._dipole_to_platform(mw, obj)
        if obj.get_component("PlaneWaveSource") is not None:
            return SourceMap._plane_to_platform(mw, obj)
        if obj.get_component("GaussianBeamSource") is not None:
            return SourceMap._beam_to_platform(mw, obj)
        return SourceMap._mode_to_platform(mw, obj)

    # --- PointDipole ---------------------------------------------------------

    @staticmethod
    def _dipole_to_studio(comp: Any, obj: SceneObject, source: Any) -> None:
        obj.get_component("Transform").position = list(source.position)
        axis = _axis_name(tuple(source.polarization))
        comp.polarization_mode = axis or "vector"
        comp.polarization = list(source.polarization)
        comp.width = float(source.width)
        comp.profile = str(source.profile)
        comp.st_enabled = SourceTimeMap.to_studio(comp, source.source_time)

    @staticmethod
    def _dipole_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("PointDipoleSource")
        mode = str(comp.polarization_mode)
        polarization = tuple(_vec(comp.polarization)) if mode == "vector" else mode
        return mw.PointDipole(
            position=tuple(_vec(obj.get_component("Transform").position)),
            polarization=polarization, width=_f(comp.width), profile=str(comp.profile),
            source_time=SourceTimeMap.to_platform(comp, bool(comp.st_enabled)), name=obj.name)

    # --- PlaneWave / GaussianBeam (shared injection handling) ----------------

    @staticmethod
    def _plane_to_studio(comp: Any, source: Any) -> None:
        comp.direction = list(source.direction)
        comp.polarization = list(source.polarization)
        SourceMap._read_injection(comp, source)
        comp.st_enabled = SourceTimeMap.to_studio(comp, source.source_time)

    @staticmethod
    def _plane_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("PlaneWaveSource")
        return mw.PlaneWave(
            direction=tuple(_vec(comp.direction)), polarization=tuple(_vec(comp.polarization)),
            source_time=SourceTimeMap.to_platform(comp, bool(comp.st_enabled)),
            injection=SourceMap._build_injection(mw, comp),
            injection_axis=SourceMap._injection_axis(comp), name=obj.name)

    @staticmethod
    def _beam_to_studio(comp: Any, source: Any) -> None:
        comp.direction = list(source.direction)
        comp.polarization = list(source.polarization)
        comp.beam_waist = float(source.beam_waist)
        comp.focus = list(source.focus)
        SourceMap._read_injection(comp, source)
        comp.st_enabled = SourceTimeMap.to_studio(comp, source.source_time)

    @staticmethod
    def _beam_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("GaussianBeamSource")
        return mw.GaussianBeam(
            direction=tuple(_vec(comp.direction)), polarization=tuple(_vec(comp.polarization)),
            beam_waist=_f(comp.beam_waist), focus=tuple(_vec(comp.focus)),
            source_time=SourceTimeMap.to_platform(comp, bool(comp.st_enabled)),
            injection=SourceMap._build_injection(mw, comp),
            injection_axis=SourceMap._injection_axis(comp), name=obj.name)

    @staticmethod
    def _read_injection(comp: Any, source: Any) -> None:
        # TFSF instances expose ``bounds``; the soft injection is the string "soft".
        injection = source.injection
        if hasattr(injection, "bounds"):
            comp.injection = "tfsf"
            bounds = injection.bounds
            comp.tfsf_min = [float(bounds[i][0]) for i in range(3)]
            comp.tfsf_max = [float(bounds[i][1]) for i in range(3)]
        else:
            comp.injection = "soft"
        comp.injection_axis = str(source.injection_axis) if source.injection_axis else "auto"

    @staticmethod
    def _build_injection(mw: Any, comp: Any) -> Any:
        if str(comp.injection) != "tfsf":
            return "soft"
        lo, hi = _vec(comp.tfsf_min), _vec(comp.tfsf_max)
        return mw.TFSF(bounds=((lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])))

    @staticmethod
    def _injection_axis(comp: Any) -> Optional[str]:
        axis = str(comp.injection_axis)
        return None if axis == "auto" else axis

    # --- ModeSource ----------------------------------------------------------

    @staticmethod
    def _mode_to_studio(comp: Any, obj: SceneObject, source: Any) -> None:
        obj.get_component("Transform").position = list(source.position)
        comp.size = list(source.size)
        comp.mode_index = int(source.mode_index)
        comp.direction = str(source.direction)
        comp.polarization = _axis_from_letter(source.polarization_axis)
        comp.st_enabled = SourceTimeMap.to_studio(comp, source.source_time)

    @staticmethod
    def _mode_to_platform(mw: Any, obj: SceneObject) -> Any:
        comp = obj.get_component("ModeSource")
        return mw.ModeSource(
            position=tuple(_vec(obj.get_component("Transform").position)),
            size=tuple(_vec(comp.size)), mode_index=int(comp.mode_index),
            direction=str(comp.direction), polarization=str(comp.polarization),
            source_time=SourceTimeMap.to_platform(comp, bool(comp.st_enabled)), name=obj.name)
