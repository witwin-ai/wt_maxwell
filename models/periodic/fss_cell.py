"""FSS unit cell: a square patch, or its complement, a square aperture in a metal sheet.

``aperture = 0``: a copper patch of side ``size`` centered in a ``period``
cell (band-stop, capacitive). ``aperture = 1``: a copper sheet over the
whole cell with a square hole of side ``size`` (band-pass, inductive).
``substrate = 1`` puts the sheet on a dielectric slab of height ``h``;
``substrate = 0`` leaves it free-standing. Copper is a ``fill="surface"``
sheet carrying the copper thickness.

Anchors: ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax``
(kind ``periodic``) for periodic or Floquet boundaries; ``port1`` (top,
normal +z) and ``port2`` (bottom, normal -z) for the Floquet ports.

``design`` uses the half-wave rule for patch elements, side = lambda/2
with lambda shortened by sqrt((eps_r + 1)/2) on a substrate (Munk,
Frequency Selective Surfaces, 2000, ch. 2 and 4). By Babinet's principle
the complementary aperture resonates at the same frequency in a
free-standing screen. A first cut (roughly 10-20 %); the gap between
patches pulls the resonance down, so tune with the solver.

    python fss_cell.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _periodic_cells import C0, cell_stack, eps_eff_sheet, layout_cell, spec_values

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "period": ws.param(12.0, unit="mm", min=0.05, max=500, description="cell period (x and y)"),
    "size": ws.param(9.1224, unit="mm", min=0.02, max=500, description="patch or aperture side"),
    "aperture": ws.param(0, integer=True, min=0, max=1, description="0: patch, 1: aperture in a full sheet"),
    "substrate": ws.param(1, integer=True, min=0, max=1, description="1: on a dielectric slab, 0: free-standing"),
    "h": ws.param(0.8, unit="mm", min=0.01, max=50, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(10, unit="GHz", min=0.001, max=10000, description="design frequency (loss conductivity)"),
}

DESIGN_SPEC = {
    "f0": ws.param(10, unit="GHz", min=0.001, max=10000, description="element resonance frequency"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "substrate": ws.param(1, integer=True, min=0, max=1, description="1: on a slab, 0: free-standing"),
    "fill": ws.param(0.7602, min=0.1, max=0.99, description="element side over period"),
}


def design(spec=None):
    """Element side from the half-wave rule; period = side / fill."""
    v = spec_values(DESIGN_SPEC, spec)
    substrate = bool(round(v["substrate"]))
    lam = C0 / (v["f0"] * 1e9) / math.sqrt(eps_eff_sheet(v["eps_r"], substrate)) * 1e3  # mm
    size = lam / 2.0
    out = {"size": round(size, 4), "period": round(size / v["fill"], 4), "substrate": int(substrate), "f0": v["f0"]}
    if substrate:
        out["eps_r"] = v["eps_r"]
    return out


def build(ctx):
    p = ctx.params
    if p.size >= p.period:
        raise ValueError("size must be smaller than the period")
    substrate = bool(int(p.substrate))
    aperture = bool(int(p.aperture))
    stack = cell_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0, ground=False, substrate=substrate,
                       top_kind="ground" if aperture else "conductor")
    lay = L.Layout(unit="mm", outline=L.rect(p.period, p.period))
    if aperture:
        lay.cut("top", L.rect(p.size, p.size))     # a ground layer fills the cell; the cut opens the hole
    else:
        lay.add("top", L.rect(p.size, p.size))
    return layout_cell(lay, stack, p.period, p.period, ground=False, substrate=substrate, h=p.h, t=p.t)


if __name__ == "__main__":
    ws.preview(build)
