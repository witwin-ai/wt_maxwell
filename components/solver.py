"""Unified Maxwell solver component.

``MaxwellSolver`` is the single scene-level component for a Maxwell simulation:
domain, grid, boundary, solver settings, and result visualization live together
as foldout groups on the Maxwell Settings object. The component subclasses the
core Field component so solved field data is written back onto the solver itself
via ``set_volume_data`` instead of creating a separate field object.
"""
import io
import asyncio

import numpy as np
from dataclasses import asdict

from witwin_server.api import (
    Notifications,
    SceneObject,
    api,
    bool_field,
    button,
    component,
    define_group,
    figure,
    float_field,
    foldout_group,
    int_field,
    list_field,
    string_field,
    tab_group,
    vector3_field,
)
from witwin_server.plugins_builtin.em.api import FieldComponent

from ..adapter.common import num
from ..adapter.grid import PPW_OPTIONS, grid_cell_size, grid_frequency, pml_inset, resolution_from_bounds
from ..adapter.solve import SolveConfig
from .mode_profiles import publish_value

BOUNDARY_KINDS = ["none", "pml", "periodic", "bloch", "pec", "pmc"]
SYMMETRY_KINDS = ["none", "PEC", "PMC"]
SYMMETRY_FACES = ["low", "high"]
FIELD_COMPONENTS = ["Ex", "Ey", "Ez", "Hx", "Hy", "Hz"]

_CAT = "Simulation/Maxwell"
_DOMAIN = "Domain"
_GRID = "Grid"
_BOUNDARY = "Boundary"
_SETTINGS = "Settings"
_RESULTS = "Results"
_FDTD = {"field_name": "method", "operator": "eq", "value": "fdtd"}
_GRID_FIELDS = ("min_bound", "max_bound", "bounds_min", "bounds_max", "ppw", "frequencies", "frequency")
_BOUNDARY_FIELDS = ("mode", "kind", "num_layers", "x", "y", "z",
                    "x_low", "x_high", "y_low", "y_high", "z_low", "z_high")


@component(name="MaxwellSolver", display_name="Maxwell Solver", category=_CAT)
class MaxwellSolverComponent(FieldComponent):
    """Maxwell scene configuration, solve controls, and field visualization."""

    _solver_result_handle = ""
    _solver_run_id = ""

    define_group(foldout_group(_DOMAIN, display_name="Domain"))
    define_group(foldout_group(_GRID, display_name="Grid"))
    define_group(foldout_group(_BOUNDARY, display_name="Boundary"))
    define_group(foldout_group(_SETTINGS, display_name="Settings"))
    define_group(foldout_group(_RESULTS, display_name="Results"))
    define_group(tab_group("Renderer", "None", "Slices", "Volume", "SDF", "Vector",
                           display_name="Rendering", sync_field="render_mode",
                           tab_conditions={
                               "Volume": {"field_name": "dimension", "operator": "eq", "value": "3D"},
                               "SDF": {"field_name": "dimension", "operator": "eq", "value": "3D"},
                           }))

    # FieldComponent state used by the viewport visualizer. ``min_bound`` and
    # ``max_bound`` are also the Maxwell domain source because Field gizmos edit
    # these inherited fields directly.
    dimension = string_field("3D", options=["2D", "3D"], hidden=True)
    plane = string_field("XZ", options=["XY", "XZ", "YZ"], hidden=True)
    frequency_dependent_resolution = bool_field(False, hidden=True)
    frequency = float_field(1e9, hidden=True)
    min_bound = vector3_field([-1.0, -1.0, -1.0], description="Domain min corner (m)", group=_DOMAIN)
    max_bound = vector3_field([1.0, 1.0, 1.0], description="Domain max corner (m)", group=_DOMAIN)
    resolution = vector3_field([1.0, 1.0, 1.0], hidden=True)
    render_mode = string_field("None", options=["None", "Slices", "Volume", "SDF", "Vector"], hidden=True)
    cache_in_memory = bool_field(True, hidden=True)

    # Legacy aliases kept for old serialized scenes and plugin versions.
    bounds_min = vector3_field([-1.0, -1.0, -1.0], hidden=True)
    bounds_max = vector3_field([1.0, 1.0, 1.0], hidden=True)

    # Grid.
    ppw = string_field("10", options=PPW_OPTIONS, widget="stepped-slider",
                       description="Points per wavelength", group=_GRID)
    uniform = bool_field(True, hidden=True)
    dl = float_field(0.05, min=1e-9, hidden=True)
    dx = float_field(0.05, min=1e-9, hidden=True)
    dy = float_field(0.05, min=1e-9, hidden=True)
    dz = float_field(0.05, min=1e-9, hidden=True)

    # Boundary.
    mode = string_field("global", options=["global", "per_axis", "per_face"],
                        enum_toggle=True, description="Boundary specification scope", group=_BOUNDARY)
    kind = string_field("pml", options=BOUNDARY_KINDS, description="Boundary kind", group=_BOUNDARY)
    num_layers = int_field(15, min=1, show_if={"field_name": "kind", "operator": "eq", "value": "pml"},
                           description="PML layers", group=_BOUNDARY)
    strength = float_field(1e6, min=0.0, show_if={"field_name": "kind", "operator": "eq", "value": "pml"},
                           description="PML strength", group=_BOUNDARY)
    bloch_wavevector = vector3_field(
        [0.0, 0.0, 0.0],
        show_if={"field_name": "kind", "operator": "eq", "value": "bloch"},
        description="Bloch wavevector (rad/m)", group=_BOUNDARY)
    x = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"}, group=_BOUNDARY)
    y = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"}, group=_BOUNDARY)
    z = string_field("pml", options=BOUNDARY_KINDS,
                     show_if={"field_name": "mode", "operator": "eq", "value": "per_axis"}, group=_BOUNDARY)
    x_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)
    x_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)
    y_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)
    y_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)
    z_low = string_field("pml", options=BOUNDARY_KINDS,
                         show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)
    z_high = string_field("pml", options=BOUNDARY_KINDS,
                          show_if={"field_name": "mode", "operator": "eq", "value": "per_face"}, group=_BOUNDARY)

    # Scene / solve settings.
    subpixel_uniform = bool_field(True, description="One subpixel sample count for all axes", group=_SETTINGS)
    subpixel = int_field(1, min=1, show_if="subpixel_uniform",
                         description="Subpixel material samples per axis", group=_SETTINGS)
    subpixel_x = int_field(1, min=1, hide_if="subpixel_uniform", group=_SETTINGS)
    subpixel_y = int_field(1, min=1, hide_if="subpixel_uniform", group=_SETTINGS)
    subpixel_z = int_field(1, min=1, hide_if="subpixel_uniform", group=_SETTINGS)
    symmetry_x = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to x",
                              group=_SETTINGS)
    symmetry_y = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to y",
                              group=_SETTINGS)
    symmetry_z = string_field("none", options=SYMMETRY_KINDS, description="Symmetry plane normal to z",
                              group=_SETTINGS)
    symmetry_x_face = string_field("low", options=SYMMETRY_FACES, hidden=True)
    symmetry_y_face = string_field("low", options=SYMMETRY_FACES, hidden=True)
    symmetry_z_face = string_field("low", options=SYMMETRY_FACES, hidden=True)
    device = string_field("cuda", options=["cuda", "cpu"], enum_toggle=True,
                          description="Solve device (FDTD requires CUDA for practical scenes)", group=_SETTINGS)
    frequencies = list_field(float_field(1e9, min=0.0), default=[],
                             description="Solve frequencies (Hz)", group=_SETTINGS)
    method = string_field("fdtd", options=["fdtd"], hidden=True)
    absorber = string_field("cpml", options=["cpml", "pml"], show_if=_FDTD, group=_SETTINGS)
    full_field_dft = bool_field(True, hidden=True)
    time_steps_auto = bool_field(True, show_if=_FDTD, group=_SETTINGS)
    time_steps = int_field(1000, min=1, hide_if="time_steps_auto", group=_SETTINGS)

    # Results.
    slice_axis = string_field("z", options=["x", "y", "z"], enum_toggle=True, title="Field slice", group=_RESULTS)
    slice_position = float_field(0.0, description="Slice coordinate along the axis (m)", group=_RESULTS)
    component = string_field("Ez", options=FIELD_COMPONENTS, description="Field component", group=_RESULTS)
    value_mode = string_field("abs", options=["abs", "real", "imag"], enum_toggle=True, group=_RESULTS)
    frequency_index = int_field(0, min=0, description="Frequency index (multi-frequency results)", group=_RESULTS)
    log_scale = bool_field(False, description="Log10 magnitude", group=_RESULTS)
    show_3d_field = bool_field(True, description="Update this solver's 3D field volume after solving", group=_RESULTS)
    slice_figure = figure(title="Field Slice", group=_RESULTS)

    @button(display_name="Solve", group=_RESULTS, operation="solver", cancellable=True,
            progress_surface="component")
    def solve(self):
        async def _run():
            return await self._solve_async()

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())
        return _run()

    async def _solve_async(self):
        config = self._solve_config()
        if config is None:
            return "No solve frequencies set"
        self._ensure_default_source()
        self._apply_current_timeline_pose()
        run = await asyncio.to_thread(
            api.solvers.solve,
            "witwin.maxwell.fdtd",
            scene=self._owner.scene,
            config=asdict(config),
        )
        if run.status != "succeeded":
            message = (run.error or {}).get("message") or "solve failed"
            Notifications.error("Maxwell", message)
            return f"Solve failed: {message}"
        handle = (run.outputs or {}).get("resultHandle")
        if not handle:
            Notifications.error("Maxwell", "Solver returned no result handle")
            return "Solve failed: no result handle"
        self._solver_result_handle = str(handle)
        self._solver_run_id = run.run_id
        self.update_slice()
        if bool(self.show_3d_field):
            self.show_volume()
        Notifications.success("Maxwell", f"{str(self.method).upper()} solve complete")
        return "Solve complete"

    def _apply_current_timeline_pose(self) -> None:
        scene = getattr(self._owner, "scene", None)
        timeline = getattr(scene, "timeline_manager", None) if scene is not None else None
        apply_to_scene = getattr(timeline, "apply_to_scene", None)
        if callable(apply_to_scene):
            apply_to_scene()

    @button(display_name="Update Slice", group=_RESULTS)
    def update_slice(self):
        if not self._solver_result_handle:
            return "Solve first"
        sl = self._query_result("extract_slice", {
            "axis": str(self.slice_axis),
            "position": float(num(self.slice_position)),
            "component": str(self.component),
            "value_mode": str(self.value_mode),
            "freq_index": int(self.frequency_index),
            "log_scale": bool(self.log_scale),
        })
        data = np.asarray(sl["data"], dtype=np.float32)
        self.slice_figure.clear().imshow(data).title(f"{self.component} ({self.value_mode})")
        return "Slice updated"

    @button(display_name="Show 3D Volume", group=_RESULTS)
    def show_volume(self):
        if not self._solver_result_handle:
            return "Solve first"
        payload = self._query_result("extract_volume", {
            "component": str(self.component),
            "value_mode": str(self.value_mode),
            "freq_index": int(self.frequency_index),
        })
        vol = self._load_volume_payload(payload)
        self._sync_field_bounds()
        self.set_volume_data(np.asarray(vol, dtype=np.float32))
        self.set_field("render_mode", "Volume", force=True)
        self.export_volume_data()
        return "Volume updated"

    def _query_result(self, op: str, params: dict):
        response = api.solvers.query(
            "witwin.maxwell.fdtd",
            self._solver_result_handle,
            op,
            params,
            run_id=self._solver_run_id or None,
        )
        return response.get("data") or {}

    @staticmethod
    def _load_volume_payload(payload: dict) -> np.ndarray:
        ref = payload.get("resultRef")
        if not isinstance(ref, dict) or not ref.get("path"):
            raise ValueError("Maxwell volume query did not return a resultRef")
        expected = str(ref.get("contentHash") or "")
        if not expected.startswith("sha256:") or len(expected.split(":", 1)[1]) != 64:
            raise ValueError("Maxwell volume resultRef contentHash must be sha256")
        raw = api.solvers.read_result_ref("witwin.maxwell.fdtd", ref)
        volume = np.load(io.BytesIO(raw), allow_pickle=False)
        shape = payload.get("shape")
        if shape:
            volume = volume.reshape(tuple(int(v) for v in shape))
        return np.asarray(volume, dtype=np.float32)

    def _ensure_default_source(self) -> bool:
        """Create a small FDTD-compatible point source if the scene has none."""
        from ..adapter.source_map import SOURCE_COMPONENTS

        scene = self._owner.scene if self._owner else None
        if scene is None:
            return False
        for obj in scene.objects.values():
            if any(obj.get_component(name) is not None for name in SOURCE_COMPONENTS):
                return False

        frequency = next((num(f) for f in self.frequencies), 1e9)
        source = SceneObject(name="Default FDTD Source", mesh_type="Empty")
        comp = source.add_component("PointDipoleSource")
        if comp is not None:
            comp.polarization_mode = "Ez"
            comp.st_kind = "gaussian_pulse"
            comp.st_frequency = frequency
            comp.st_fwidth = frequency * 0.2
        scene.add_object(source)
        return True

    def _solve_config(self):
        freqs = tuple(num(f) for f in self.frequencies)
        if not freqs:
            Notifications.warning("Maxwell", "Set solve frequencies in Maxwell Solver first")
            return None
        if str(self.device) == "cpu":
            Notifications.warning("Maxwell", "Solving on CPU; large simulations require CUDA")
        return SolveConfig.from_component(self)

    def set_field(self, field_name: str, value, *, silent: bool = False, force: bool = False):
        super().set_field(field_name, value, silent=silent, force=force)
        if field_name == "bounds_min":
            super().set_field("min_bound", value, silent=silent, force=True)
        elif field_name == "bounds_max":
            super().set_field("max_bound", value, silent=silent, force=True)
        if field_name in _GRID_FIELDS:
            self._sync_field_bounds()
        if field_name in _GRID_FIELDS or field_name in _BOUNDARY_FIELDS:
            publish_value(self, "pml_inset", pml_inset(self))

    # ``pml_inset`` (m per face, x_low..z_high) is derived for the viewport's
    # dashed PML box: sent with every sync, never saved.
    def to_dict(self):
        self._values["pml_inset"] = pml_inset(self)
        return super().to_dict()

    def to_properties_dict(self):
        result = super().to_properties_dict()
        result["properties"].pop("pml_inset", None)
        return result

    def _sync_field_bounds(self) -> None:
        bounds_min = [float(num(v)) for v in self.min_bound]
        bounds_max = [float(num(v)) for v in self.max_bound]
        cell_size = grid_cell_size(self)
        resolution = resolution_from_bounds(bounds_min, bounds_max, cell_size)
        super().set_field("bounds_min", bounds_min, silent=True, force=True)
        super().set_field("bounds_max", bounds_max, silent=True, force=True)
        super().set_field("frequency", grid_frequency(self), silent=True, force=True)
        super().set_field("resolution", resolution, silent=True, force=True)
