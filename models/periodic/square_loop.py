"""Square-loop metasurface / FSS unit cell on a substrate, with an optional ground plane.

A square copper loop (outer side ``loop``, strip ``width``) is centered on
a ``period`` x ``period`` cell of substrate. With ``ground = 1`` a ground
plane backs the cell (a reflective metasurface, e.g. an AMC or absorber
cell); with ``ground = 0`` it is a band-stop FSS cell. Copper is drawn as
``fill="surface"`` sheets carrying the copper thickness.

Anchors: ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax``
(kind ``periodic``) mark the cell faces for periodic or Floquet boundaries;
``port1`` (top, normal +z) and, without ground, ``port2`` (bottom, normal
-z) mark the Floquet ports.

``design`` uses the loop resonance rule for a free-standing loop array,
mean perimeter = one wavelength (Munk, Frequency Selective Surfaces, 2000,
ch. 2), with the wavelength shortened by sqrt((eps_r + 1)/2) for the
substrate under the pattern. It is a first cut, good to roughly 10-20 %;
the ground plane, the gap and the substrate thickness all move the
resonance, so tune with the solver.

    python square_loop.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _periodic_cells import C0, cell_stack, eps_eff_sheet, layout_cell, spec_values

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "period": ws.param(6.0, unit="mm", min=0.05, max=500, description="cell period (x and y)"),
    "loop": ws.param(5.0612, unit="mm", min=0.02, max=500, description="loop outer side"),
    "width": ws.param(0.5, unit="mm", min=0.005, max=100, description="loop strip width"),
    "ground": ws.param(1, integer=True, min=0, max=1, description="1: ground plane under the substrate"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=50, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(1e10, unit="Hz", min=1e6, max=1e13, description="design frequency (loss conductivity)"),
}

DESIGN_SPEC = {
    "f0": ws.param(1e10, unit="Hz", min=1e6, max=1e13, description="loop resonance frequency"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "width": ws.param(0.5, unit="mm", min=0.005, max=100, description="loop strip width (kept)"),
    "gap": ws.param(0.9388, unit="mm", min=0.005, max=100, description="gap between loops of adjacent cells"),
}


def design(spec=None):
    """Loop side from the one-wavelength-perimeter rule; period = loop + gap."""
    v = spec_values(DESIGN_SPEC, spec)
    lam = C0 / v["f0"] / math.sqrt(eps_eff_sheet(v["eps_r"])) * 1e3  # mm
    loop = lam / 4.0 + v["width"]  # mean side = lambda/4, outer side adds one strip width
    return {"loop": round(loop, 4), "period": round(loop + v["gap"], 4), "width": v["width"],
            "eps_r": v["eps_r"], "f0": v["f0"]}


def build(ctx):
    p = ctx.params
    if p.loop >= p.period:
        raise ValueError("loop must be smaller than the period")
    if 2 * p.width >= p.loop:
        raise ValueError("width leaves no opening inside the loop")
    ground = bool(int(p.ground))
    stack = cell_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0, ground=ground)
    lay = L.Layout(unit="mm", outline=L.rect(p.period, p.period))
    lay.add("top", L.boolean(L.rect(p.loop, p.loop), L.rect(p.loop - 2 * p.width, p.loop - 2 * p.width),
                             "difference"))
    return layout_cell(lay, stack, p.period, p.period, ground=ground, h=p.h, t=p.t)


if __name__ == "__main__":
    ws.preview(build)
