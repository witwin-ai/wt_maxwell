"""Solve hand-off + field-slice extraction (master §7).

``SolveRunner`` is the export->solve half of the edit loop: it rebuilds the
platform ``maxwell.Scene`` from the live studio scene (via :class:`MaxwellAdapter`)
and runs ``Simulation.fdtd``. ``SliceExtractor`` turns a solved field volume into
a 2D orthogonal slice (reusing maxwell's own ``extract_orthogonal_slice``) for the
figure surface; 3D volumes are written back onto the solver's own Field surface.

Result tensors are runtime state — never serialized into the scene.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Any, List, Optional, Tuple

import numpy as np
from witwin_server.api import get_logger

from .maxwell_adapter import MaxwellAdapter

logger = get_logger("MaxwellSolve")


@dataclass
class SolveConfig:
    """Solve configuration mirrored from the MaxwellSolver component."""

    method: str = "fdtd"
    frequencies: Tuple[float, ...] = ()
    absorber: str = "cpml"               # FDTD: "cpml" | "pml"
    full_field_dft: bool = False         # FDTD
    time_steps: Optional[int] = None     # FDTD: None = auto

    @classmethod
    def from_component(cls, comp: Any) -> "SolveConfig":
        """Read a MaxwellSolver component; the Studio button and ``witwin solve`` both use it."""
        from .common import num

        return cls(
            method=str(comp.method),
            frequencies=tuple(num(f) for f in (comp.frequencies or ())),
            absorber=str(comp.absorber),
            full_field_dft=True,
            time_steps=None if bool(comp.time_steps_auto) else int(num(comp.time_steps)),
        )

    @classmethod
    def for_scene(cls, studio_scene: Any, overrides: Optional[dict] = None) -> "SolveConfig":
        """The scene's MaxwellSolver settings, with explicit ``overrides`` winning.

        A headless solve (``project.solve``) sends no config, so the scene is
        the source of truth; the Studio button sends the same fields explicitly.
        """
        settings = MaxwellAdapter._find_settings(studio_scene)
        comp = settings.get_component("MaxwellSolver") if settings is not None else None
        base = cls.from_component(comp) if comp is not None else cls()
        for key, value in (overrides or {}).items():
            if value is None or value == () or value == []:
                continue
            if key == "frequencies":
                value = tuple(float(v) for v in value)
            elif key == "time_steps":
                value = int(value)
            if hasattr(base, key):
                setattr(base, key, value)
        return base


@dataclass
class SliceResult:
    """A 2D field slice ready for imshow (data + matplotlib-style extent + labels)."""

    data: np.ndarray
    extent: List[float]
    xlabel: str
    ylabel: str


class SolveRunner:
    """Build + run a ``maxwell.Simulation`` from a studio scene."""

    @staticmethod
    def build(platform_scene: Any, config: SolveConfig) -> Any:
        """Build an FDTD ``Simulation`` for a platform scene + config."""
        import witwin.maxwell as mw

        if config.method != "fdtd":
            raise ValueError("Maxwell Solver only supports FDTD")
        run_time = None if config.time_steps is None else mw.TimeConfig(time_steps=int(config.time_steps))
        return mw.Simulation.fdtd(
            platform_scene, frequencies=tuple(config.frequencies) or None,
            absorber=config.absorber, full_field_dft=config.full_field_dft, run_time=run_time)

    @staticmethod
    def run(studio_scene: Any, config: SolveConfig) -> Any:
        """Rebuild the platform scene from the studio scene and run the solve."""
        _ensure_mesh_sdf_runtime_env()
        platform_scene = MaxwellAdapter().to_platform(studio_scene)
        if any(str(s.geometry.kind) == "mesh" for s in platform_scene.structures):
            _warn_if_mesh_sdf_slow()
        return SolveRunner.build(platform_scene, config).run()


def _warn_if_mesh_sdf_slow() -> bool:
    """Log once when mesh structures will voxelize on the torch path.

    ``witwin.core`` falls back to a torch mesh SDF when no accelerator is
    registered; witwin-maxwell 0.5 ships none, so the solve still runs, only
    slower. ``import witwin.maxwell`` registers an accelerator in builds that
    have one, and ``to_platform`` has done that import by the time this runs.
    Returns True when the accelerator is present.
    """
    global _MESH_SDF_WARNED
    from witwin.core.geometry import mesh_sdf

    if mesh_sdf._mesh_sdf_available():
        return True
    if not _MESH_SDF_WARNED:
        _MESH_SDF_WARNED = True
        logger.warning("No CUDA mesh SDF accelerator; mesh structures use the slower torch path. "
                       + _mesh_sdf_native_diagnostics(mesh_sdf))
    return False


_MESH_SDF_WARNED = False


def _ensure_mesh_sdf_runtime_env() -> None:
    """Expose conda/CUDA paths the CUDA JIT builds (FDTD extension, mesh SDF) need: nvcc + linker.

    The solver child calls this through ``SolveRunner.run``; there is no
    second copy in ``solver_host``.
    """
    env_prefix = Path(sys.executable).resolve().parent
    if (env_prefix / "python.exe").exists():
        conda_prefix = env_prefix
    else:
        conda_prefix = Path(os.environ.get("CONDA_PREFIX", env_prefix))

    cuda_root = os.environ.get("CUDA_PATH")
    if not cuda_root:
        candidates = sorted(
            Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA").glob("v*"),
            reverse=True,
        )
        if candidates:
            cuda_root = str(candidates[0])
            os.environ["CUDA_PATH"] = cuda_root

    def prepend_env(name: str, entries: list[Path]) -> None:
        current = os.environ.get(name, "")
        parts = [part for part in current.split(os.pathsep) if part]
        seen = {os.path.normcase(part) for part in parts}
        prefix: list[str] = []
        for entry in entries:
            if not entry.exists():
                continue
            text = str(entry)
            key = os.path.normcase(text)
            if key in seen:
                continue
            prefix.append(text)
            seen.add(key)
        if prefix:
            os.environ[name] = os.pathsep.join(prefix + parts)

    path_entries = [
        conda_prefix,
        conda_prefix / "Library" / "bin",
        conda_prefix / "Scripts",
    ]
    lib_entries = [conda_prefix / "Library" / "lib"]
    include_entries = [conda_prefix / "Library" / "include"]
    if cuda_root:
        cuda_path = Path(cuda_root)
        path_entries.append(cuda_path / "bin")
        lib_entries.append(cuda_path / "lib" / "x64")
        include_entries.append(cuda_path / "include")

    prepend_env("PATH", path_entries)
    prepend_env("LIB", lib_entries)
    prepend_env("INCLUDE", include_entries)


def _mesh_sdf_native_diagnostics(mesh_sdf: Any) -> str:
    details: list[str] = []
    details.append(f"python={sys.executable}")
    details.append(f"cuda_path={os.environ.get('CUDA_PATH', '')}")
    details.append(f"lib_has_conda={_env_contains('LIB', 'Library' + os.sep + 'lib')}")
    details.append(f"path_has_cuda={_env_contains('PATH', 'CUDA')}")
    try:
        import torch

        details.append(f"cuda_available={torch.cuda.is_available()}")
    except Exception as exc:
        details.append(f"torch_error={type(exc).__name__}: {str(exc)[:500]}")

    try:
        build_error = mesh_sdf._mesh_sdf_build_error()
    except Exception:
        build_error = None
    if build_error:
        details.append(f"build_error={str(build_error)[:1000]}")
    return "; ".join(details)


def _env_contains(name: str, needle: str) -> bool:
    value = os.environ.get(name, "")
    return needle.lower() in value.lower()


class SliceExtractor:
    """Extract a 2D orthogonal slice of a solved field volume."""

    @staticmethod
    def extract(result: Any, *, axis: str = "z", position: float = 0.0, component: str = "Ez",
                value_mode: str = "abs", freq_index: int = 0, log_scale: bool = False) -> SliceResult:
        """Slice ``component`` of ``result`` along ``axis`` at ``position`` (world coords)."""
        from witwin.maxwell.visualization import extract_orthogonal_slice

        selection = result.at(freq_index=freq_index) if freq_index else result
        volume = SliceExtractor._to_real(selection.field(component.upper()), value_mode)
        if log_scale:
            volume = np.log10(np.abs(volume) + 1e-30)

        bounds = result.scene.domain.bounds
        coords = [np.linspace(bounds[i][0], bounds[i][1], volume.shape[i]) for i in range(3)]
        out = extract_orthogonal_slice(volume, axis, position, coords[0], coords[1], coords[2])
        return SliceResult(np.asarray(out["slice"], dtype=np.float32),
                           list(out["extent"]), str(out["xlabel"]), str(out["ylabel"]))

    @staticmethod
    def _to_real(tensor: Any, value_mode: str) -> np.ndarray:
        # Complex (or real) field tensor -> real numpy volume per value_mode.
        import torch

        if value_mode == "real":
            real = tensor.real if torch.is_complex(tensor) else tensor
        elif value_mode == "imag":
            real = tensor.imag if torch.is_complex(tensor) else torch.zeros_like(tensor)
        else:
            real = torch.abs(tensor)
        return real.detach().cpu().numpy().astype(np.float32)

    @staticmethod
    def volume(result: Any, *, component: str = "Ez", value_mode: str = "abs",
               freq_index: int = 0) -> np.ndarray:
        """Return the full 3D real volume of ``component`` (for viewport rendering)."""
        selection = result.at(freq_index=freq_index) if freq_index else result
        return SliceExtractor._to_real(selection.field(component.upper()), value_mode)
