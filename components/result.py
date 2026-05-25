"""MaxwellResult — solve configuration, the Solve button, and field visualization.

Lives on the ``Maxwell Settings`` object. The Solve button rebuilds the platform
scene from the live editor scene, runs FDFD (single frequency) or FDTD (multi
frequency), keeps the ``Result`` server-side (runtime state, never persisted), and
shows a 2D field slice in its figure. A second button registers a 3D field volume
in the viewport via the shared ``FieldViz`` helper. Solve frequencies come from the
sibling ``MaxwellSolveSettings`` component.
"""
from witwin_server import Notifications
from witwin_server.components import (
    Component,
    bool_field,
    button,
    component,
    figure,
    float_field,
    int_field,
    string_field,
)
from witwin_server.platform_bridge import FieldViz

from ..adapter.common import num
from ..adapter.solve import SliceExtractor, SolveConfig, SolveRunner

_CAT = "Simulation/Maxwell"
FIELD_COMPONENTS = ["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]


@component(name="MaxwellResult", category=_CAT)
class MaxwellResultComponent(Component):
    """FDFD/FDTD solve + 2D slice / 3D volume field visualization."""

    _result = None     # runtime Result (never serialized)
    _volume_id = None  # id of the viewport volume object this component owns

    # --- solve config --------------------------------------------------------
    method = string_field("fdfd", options=["fdfd", "fdtd"], enum_toggle=True,
                          title="Solve", description="Solver method")
    gmres_max_iter = int_field(5000, min=1, show_if={"field_name": "method", "operator": "eq", "value": "fdfd"})
    gmres_tol = float_field(1e-6, min=0.0, show_if={"field_name": "method", "operator": "eq", "value": "fdfd"})
    gmres_restart = int_field(200, min=1, show_if={"field_name": "method", "operator": "eq", "value": "fdfd"})
    absorber = string_field("cpml", options=["cpml", "pml"],
                            show_if={"field_name": "method", "operator": "eq", "value": "fdtd"})
    full_field_dft = bool_field(False, show_if={"field_name": "method", "operator": "eq", "value": "fdtd"})
    time_steps_auto = bool_field(True, show_if={"field_name": "method", "operator": "eq", "value": "fdtd"})
    time_steps = int_field(1000, min=1, hide_if="time_steps_auto")

    # --- slice viz -----------------------------------------------------------
    slice_axis = string_field("z", options=["x", "y", "z"], enum_toggle=True, title="Field slice")
    slice_position = float_field(0.0, description="Slice coordinate along the axis (m)")
    component = string_field("Ez", options=FIELD_COMPONENTS, description="Field component")
    value_mode = string_field("abs", options=["abs", "real", "imag"], enum_toggle=True)
    frequency_index = int_field(0, min=0, description="Frequency index (multi-frequency results)")
    log_scale = bool_field(False, description="Log10 magnitude")
    show_3d_field = bool_field(True, description="Register the 3D field volume in the viewport after solving")
    slice_figure = figure(title="Field Slice")

    @button(display_name="Solve")
    def solve(self):
        config = self._solve_config()
        if config is None:
            return "No solve frequencies set"
        self._result = SolveRunner.run(self._owner.scene, config)
        self.update_slice()
        if bool(self.show_3d_field):
            self.show_volume()
        Notifications.success("Maxwell", f"{str(self.method).upper()} solve complete")
        return "Solve complete"

    @button(display_name="Update Slice")
    def update_slice(self):
        if self._result is None:
            return "Solve first"
        sl = SliceExtractor.extract(
            self._result, axis=str(self.slice_axis), position=float(num(self.slice_position)),
            component=str(self.component), value_mode=str(self.value_mode),
            freq_index=int(self.frequency_index), log_scale=bool(self.log_scale))
        self.slice_figure.clear().imshow(sl.data).title(f"{self.component} ({self.value_mode})")
        return "Slice updated"

    @button(display_name="Show 3D Volume")
    def show_volume(self):
        if self._result is None:
            return "Solve first"
        scene = self._owner.scene
        # Replace the volume from a previous solve so re-solving doesn't pile them up.
        if self._volume_id is not None and scene.get_object(self._volume_id) is not None:
            scene.remove_object(self._volume_id)
        vol = SliceExtractor.volume(self._result, component=str(self.component),
                                    value_mode=str(self.value_mode), freq_index=int(self.frequency_index))
        obj = FieldViz.show_3d(vol, scene=scene, bounds=self._result.scene.domain.bounds,
                               name=f"{self.component} Field")
        # FieldViz only stores the volume via set_volume_data; the bytes must be
        # uploaded (sets volume_id) for the viewport to render it — mirror the
        # library handler's post-creation hook.
        renderer = obj.get_component("VolumeRenderer")
        if renderer is not None:
            renderer.export_volume_data()
        self._volume_id = obj.id
        return "Volume added to viewport"

    def _solve_config(self):
        """Assemble a SolveConfig from this component + the sibling solve settings."""
        settings = self._owner.get_component("MaxwellSolveSettings") if self._owner else None
        freqs = tuple(num(f) for f in (settings.frequencies if settings else []))
        if not freqs:
            Notifications.warning("Maxwell", "Set solve frequencies in MaxwellSolveSettings first")
            return None
        if settings and str(settings.device) == "cpu":
            Notifications.warning("Maxwell", "Solving on CPU; large simulations require CUDA")
        return SolveConfig(
            method=str(self.method), frequencies=freqs,
            gmres_max_iter=int(self.gmres_max_iter), gmres_tol=float(num(self.gmres_tol)),
            gmres_restart=int(self.gmres_restart), absorber=str(self.absorber),
            full_field_dft=bool(self.full_field_dft),
            time_steps=None if bool(self.time_steps_auto) else int(self.time_steps))
