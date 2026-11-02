"""Grid helpers shared by Maxwell solver UI and scene export."""
from __future__ import annotations

import math
from typing import Any, Iterable, List


SPEED_OF_LIGHT = 299792458.0
DEFAULT_FREQUENCY = 1e9
MIN_PPW = 4
MAX_PPW = 20
DEFAULT_PPW = 10
PPW_OPTIONS = [str(i) for i in range(MIN_PPW, MAX_PPW + 1)]


def _scalar(value: Any, default: float) -> float:
    if value is None:
        return default
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _iter_values(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if hasattr(value, "tolist"):
        value = value.tolist()
    return value


def grid_frequency(comp: Any) -> float:
    """Return the shortest-wavelength frequency that should drive the grid."""
    frequencies = []
    for value in _iter_values(getattr(comp, "frequencies", ())):
        freq = _scalar(value, 0.0)
        if freq > 0.0:
            frequencies.append(freq)
    if frequencies:
        return max(frequencies)
    freq = _scalar(getattr(comp, "frequency", None), DEFAULT_FREQUENCY)
    return freq if freq > 0.0 else DEFAULT_FREQUENCY


def quantize_ppw(value: Any) -> int:
    """Clamp and round PPW to the stepped-slider integer range."""
    ppw = _scalar(value, DEFAULT_PPW)
    return max(MIN_PPW, min(MAX_PPW, int(math.floor(ppw + 0.5))))


def grid_ppw(comp: Any) -> float:
    """Return the integer points-per-wavelength value from the component."""
    return float(quantize_ppw(getattr(comp, "ppw", None)))


def grid_cell_size(comp: Any) -> float:
    """Uniform FDTD cell size from wavelength / PPW."""
    return SPEED_OF_LIGHT / grid_frequency(comp) / grid_ppw(comp)


def resolution_from_bounds(bounds_min: Any, bounds_max: Any, cell_size: float) -> List[int]:
    lo = list(_iter_values(bounds_min))
    hi = list(_iter_values(bounds_max))
    return [max(1, int(math.ceil(abs(float(b) - float(a)) / cell_size)))
            for a, b in zip(lo, hi)]


_FACES = ("x_low", "x_high", "y_low", "y_high", "z_low", "z_high")


def boundary_face_kinds(comp: Any) -> List[str]:
    """Boundary kind of each domain face, in ``_FACES`` order, as the solver builds it."""
    mode = str(getattr(comp, "mode", "global"))
    if mode == "per_axis":
        return [str(getattr(comp, face[0], "pml")) for face in _FACES]
    if mode == "per_face":
        return [str(getattr(comp, face, "pml")) for face in _FACES]
    return [str(getattr(comp, "kind", "pml"))] * len(_FACES)


def pml_inset(comp: Any) -> List[float]:
    """PML thickness (m) on each face, x_low..z_high; 0 where the face is not PML.

    The viewport draws the inner PML boundary from this, so it uses the same
    layer count and cell size as the solve.
    """
    thickness = int(_scalar(getattr(comp, "num_layers", 0), 0)) * grid_cell_size(comp)
    return [thickness if kind == "pml" else 0.0 for kind in boundary_face_kinds(comp)]
