"""Helpers shared by the passive generators: line formulas, the board stack, microstrip sizing.

The closed-form formulas live in ``models/lines/_lines_formulas.py``. A model
folder is the only one on ``sys.path`` when Studio runs a model, so this
module loads that file by path, once per process, under a private module
name.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional, Tuple

PEC = "PEC"


def _load_formulas():
    name = "_wt_maxwell_lines_formulas"
    module = sys.modules.get(name)
    if module is None:
        path = Path(__file__).resolve().parents[1] / "lines" / "_lines_formulas.py"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return module


F = _load_formulas()


def board_stack(h: float, t: float, eps_r: float, tan_delta: float, f0_ghz: Optional[float] = None,
                *, unit: str = "mm"):
    """Microstrip board: ``bottom`` ground, ``core`` dielectric, ``top`` copper (same as the line generators)."""
    from witwin.studio import layout as L

    material = F.dielectric("substrate", eps_r, tan_delta, None if not f0_ghz else f0_ghz * 1e9)
    return L.LayerStack([
        ("bottom", "ground", t, {"material": PEC}),
        ("core", "dielectric", h, {"material": material}),
        ("top", "conductor", t, {"material": PEC}),
    ], unit=unit, z0=-t)


def line(w: float, h: float, eps_r: float, t: float = 0.0) -> Tuple[float, float]:
    """``(Z0 ohm, eps_eff)`` of a microstrip of width ``w`` (Hammerstad-Jensen, with thickness)."""
    return F.microstrip(w, h, eps_r, t)


def width(z0: float, h: float, eps_r: float, t: float = 0.0) -> float:
    """Microstrip width for ``z0`` (Hammerstad-Jensen, with thickness), rounded to 0.1 um."""
    return round(F.microstrip_width(z0, h, eps_r, t), 4)


def guided_wavelength_mm(w: float, h: float, eps_r: float, t: float, f0_ghz: float) -> float:
    """Guided wavelength (mm) of a microstrip of width ``w`` at ``f0_ghz``."""
    _, eps_eff = line(w, h, eps_r, t)
    return F.guided_wavelength(f0_ghz * 1e9, eps_eff) * 1e3
