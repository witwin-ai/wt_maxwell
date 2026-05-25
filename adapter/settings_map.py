"""Scene-level config interchange: maxwell scene config <-> Maxwell Settings object.

``to_studio`` reads a ``maxwell.Scene`` (duck-typed) into a single ``Empty``
``SceneObject`` carrying MaxwellDomain / MaxwellGrid / MaxwellBoundary /
MaxwellSolveSettings. ``build_config`` reads those components back into the
``maxwell`` objects needed to construct a ``Scene`` (lazy-imports witwin.maxwell).
"""
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from witwin_server import SceneObject

SETTINGS_NAME = "Maxwell Settings"
MARKER_COMPONENT = "MaxwellDomain"


def _f(value: Any) -> float:
    # Component scalar (tensor or number) -> python float.
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _vec3(value: Any) -> List[float]:
    # Component vector3 (tensor or list) -> 3 python floats.
    seq = value.tolist() if hasattr(value, "tolist") else value
    return [float(v) for v in seq]


@dataclass
class SceneConfig:
    """The ``maxwell`` objects needed to build a ``Scene`` (see :class:`MaxwellAdapter`)."""

    domain: Any
    grid: Any
    boundary: Any
    subpixel_samples: Any              # int or (int, int, int)
    symmetry: Optional[Tuple[Optional[str], Optional[str], Optional[str]]]
    device: str


class SettingsMap:
    """Maxwell scene config <-> the Maxwell Settings object's four components."""

    @staticmethod
    def to_studio(scene: Any) -> SceneObject:
        """Build the Maxwell Settings ``Empty`` object from a ``maxwell.Scene``."""
        from ..components.result import MaxwellResultComponent
        from ..components.settings import (
            MaxwellBoundaryComponent,
            MaxwellDomainComponent,
            MaxwellGridComponent,
            MaxwellSolveSettingsComponent,
        )

        obj = SceneObject(name=SETTINGS_NAME, mesh_type="Empty")
        SettingsMap._read_domain(obj.add_component(MaxwellDomainComponent()), scene.domain)
        SettingsMap._read_grid(obj.add_component(MaxwellGridComponent()), scene.grid)
        SettingsMap._read_boundary(obj.add_component(MaxwellBoundaryComponent()), scene.boundary)
        SettingsMap._read_solve(obj.add_component(MaxwellSolveSettingsComponent()), scene)
        obj.add_component(MaxwellResultComponent())  # solve button + field viz (no round-trip data)
        return obj

    @staticmethod
    def build_config(settings_obj: SceneObject) -> SceneConfig:
        """Read the four components back into ``maxwell`` objects for ``Scene(...)``."""
        import witwin.maxwell as mw

        domain = settings_obj.get_component("MaxwellDomain")
        grid = settings_obj.get_component("MaxwellGrid")
        boundary = settings_obj.get_component("MaxwellBoundary")
        solve = settings_obj.get_component("MaxwellSolveSettings")
        return SceneConfig(
            domain=SettingsMap._build_domain(mw, domain),
            grid=SettingsMap._build_grid(mw, grid),
            boundary=SettingsMap._build_boundary(mw, boundary),
            subpixel_samples=SettingsMap._build_subpixel(solve),
            symmetry=SettingsMap._build_symmetry(solve),
            device=str(solve.device),
        )

    # --- domain --------------------------------------------------------------

    @staticmethod
    def _read_domain(comp: Any, domain: Any) -> None:
        bounds = domain.bounds
        comp.bounds_min = [float(bounds[i][0]) for i in range(3)]
        comp.bounds_max = [float(bounds[i][1]) for i in range(3)]

    @staticmethod
    def _build_domain(mw: Any, comp: Any) -> Any:
        lo, hi = _vec3(comp.bounds_min), _vec3(comp.bounds_max)
        return mw.Domain(bounds=((lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2])))

    # --- grid ----------------------------------------------------------------

    @staticmethod
    def _read_grid(comp: Any, grid: Any) -> None:
        if grid.is_uniform:
            comp.uniform = True
            comp.dl = float(grid.dx)
        else:
            comp.uniform = False
            comp.dx, comp.dy, comp.dz = float(grid.dx), float(grid.dy), float(grid.dz)

    @staticmethod
    def _build_grid(mw: Any, comp: Any) -> Any:
        if bool(comp.uniform):
            return mw.GridSpec.uniform(_f(comp.dl))
        return mw.GridSpec.anisotropic(_f(comp.dx), _f(comp.dy), _f(comp.dz))

    # --- boundary ------------------------------------------------------------

    @staticmethod
    def _read_boundary(comp: Any, boundary: Any) -> None:
        comp.num_layers = int(boundary.num_layers)
        comp.strength = float(boundary.strength)
        comp.bloch_wavevector = [float(v) for v in boundary.bloch_wavevector]

        faces = {(axis, side): str(boundary.face_kind(axis, side))
                 for axis in ("x", "y", "z") for side in ("low", "high")}
        uniform = len(set(faces.values())) == 1
        if uniform:
            comp.mode = "global"
            comp.kind = next(iter(faces.values()))
            return
        per_axis = all(faces[(a, "low")] == faces[(a, "high")] for a in ("x", "y", "z"))
        if per_axis:
            comp.mode = "per_axis"
            comp.x = faces[("x", "low")]
            comp.y = faces[("y", "low")]
            comp.z = faces[("z", "low")]
        else:
            comp.mode = "per_face"
            for axis in ("x", "y", "z"):
                setattr(comp, f"{axis}_low", faces[(axis, "low")])
                setattr(comp, f"{axis}_high", faces[(axis, "high")])

    @staticmethod
    def _build_boundary(mw: Any, comp: Any) -> Any:
        mode = str(comp.mode)
        if mode == "global":
            return SettingsMap._build_global_boundary(mw, comp, str(comp.kind))
        layers, strength = int(comp.num_layers), _f(comp.strength)
        bloch = tuple(_vec3(comp.bloch_wavevector))
        if mode == "per_axis":
            return mw.BoundarySpec.faces(default=str(comp.kind), num_layers=layers,
                                         strength=strength, bloch_wavevector=bloch,
                                         x=str(comp.x), y=str(comp.y), z=str(comp.z))
        return mw.BoundarySpec.faces(
            default=str(comp.kind), num_layers=layers, strength=strength, bloch_wavevector=bloch,
            x_low=str(comp.x_low), x_high=str(comp.x_high),
            y_low=str(comp.y_low), y_high=str(comp.y_high),
            z_low=str(comp.z_low), z_high=str(comp.z_high))

    @staticmethod
    def _build_global_boundary(mw: Any, comp: Any, kind: str) -> Any:
        if kind == "pml":
            return mw.BoundarySpec.pml(num_layers=int(comp.num_layers), strength=_f(comp.strength))
        if kind == "bloch":
            return mw.BoundarySpec.bloch(tuple(_vec3(comp.bloch_wavevector)))
        return getattr(mw.BoundarySpec, kind)()  # none / periodic / pec / pmc

    # --- solve settings ------------------------------------------------------

    @staticmethod
    def _read_solve(comp: Any, scene: Any) -> None:
        sub = scene.subpixel_samples
        sub = list(sub) if isinstance(sub, (tuple, list)) else [int(sub)] * 3
        if len(set(sub)) == 1:
            comp.subpixel_uniform = True
            comp.subpixel = int(sub[0])
        else:
            comp.subpixel_uniform = False
            comp.subpixel_x, comp.subpixel_y, comp.subpixel_z = (int(s) for s in sub)
        sym = scene.symmetry or (None, None, None)
        comp.symmetry_x = sym[0] or "none"
        comp.symmetry_y = sym[1] or "none"
        comp.symmetry_z = sym[2] or "none"
        comp.device = str(scene.device)

    @staticmethod
    def _build_subpixel(comp: Any) -> Any:
        if bool(comp.subpixel_uniform):
            return int(comp.subpixel)
        return (int(comp.subpixel_x), int(comp.subpixel_y), int(comp.subpixel_z))

    @staticmethod
    def _build_symmetry(comp: Any) -> Optional[Tuple[Optional[str], ...]]:
        axes = tuple(None if str(getattr(comp, f"symmetry_{a}")) == "none"
                     else str(getattr(comp, f"symmetry_{a}")) for a in ("x", "y", "z"))
        return None if axes == (None, None, None) else axes
