"""Solve hand-off + field-slice extraction (master §7).

``SolveRunner`` is the export->solve half of the edit loop: it rebuilds the
platform ``maxwell.Scene`` from the live studio scene (via :class:`MaxwellAdapter`)
and runs ``Simulation.fdfd`` (single frequency) or ``Simulation.fdtd`` (multi
frequency). ``SliceExtractor`` turns a solved field volume into a 2D orthogonal
slice (reusing maxwell's own ``extract_orthogonal_slice``) for the Results-panel /
figure surface; 3D volumes go to the viewport via the shared ``FieldViz`` helper.

Result tensors are runtime state — never serialized into the scene.
"""
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple

import numpy as np

from .maxwell_adapter import MaxwellAdapter


@dataclass
class SolveConfig:
    """Solve configuration mirrored from the MaxwellResult component + solve settings."""

    method: str = "fdfd"                 # "fdfd" | "fdtd"
    frequencies: Tuple[float, ...] = ()  # Hz; FDFD uses the first, FDTD uses all
    gmres_max_iter: int = 5000
    gmres_tol: float = 1e-6
    gmres_restart: int = 200
    absorber: str = "cpml"               # FDTD: "cpml" | "pml"
    full_field_dft: bool = False         # FDTD
    time_steps: Optional[int] = None     # FDTD: None = auto


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
        """Build a ``Simulation`` (FDFD or FDTD) for a platform scene + config."""
        import witwin.maxwell as mw

        if config.method == "fdfd":
            solver = mw.GMRES(max_iter=config.gmres_max_iter, tol=config.gmres_tol,
                              restart=config.gmres_restart)
            frequency = config.frequencies[0] if config.frequencies else None
            return mw.Simulation.fdfd(platform_scene, frequency=frequency, solver=solver)
        run_time = None if config.time_steps is None else mw.TimeConfig(time_steps=int(config.time_steps))
        return mw.Simulation.fdtd(
            platform_scene, frequencies=tuple(config.frequencies) or None,
            absorber=config.absorber, full_field_dft=config.full_field_dft, run_time=run_time)

    @staticmethod
    def run(studio_scene: Any, config: SolveConfig) -> Any:
        """Rebuild the platform scene from the studio scene and run the solve."""
        platform_scene = MaxwellAdapter().to_platform(studio_scene)
        return SolveRunner.build(platform_scene, config).run()


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
