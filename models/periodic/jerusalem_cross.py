"""Jerusalem-cross metasurface / FSS unit cell on a substrate, with an optional ground plane.

A copper cross (arm ``arm`` tip to tip, strip ``width``) with an end cap
(``cap`` long, ``cap_width`` wide) across each tip, centered on a
``period`` x ``period`` substrate cell. ``ground = 1`` adds a ground plane
under the substrate. Copper is drawn as ``fill="surface"`` sheets carrying
the copper thickness.

Anchors: ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax``
(kind ``periodic``) for periodic or Floquet boundaries; ``port1`` (top,
normal +z) and, without ground, ``port2`` (bottom, normal -z) for the
Floquet ports.

No closed-form design: the resonance of a Jerusalem cross depends on the
arm inductance and the cap-to-cap capacitance of neighbouring cells
together; use an equivalent-circuit model (e.g. Langley & Drinkwater, IEE
Proc. H 129(1), 1982) or the solver to size it.

    python jerusalem_cross.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

from _periodic_cells import cell_stack, layout_cell

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "period": ws.param(8.0, unit="mm", min=0.05, max=500, description="cell period (x and y)"),
    "arm": ws.param(7.0, unit="mm", min=0.02, max=500, description="cross length, tip to tip"),
    "width": ws.param(0.5, unit="mm", min=0.005, max=100, description="cross strip width"),
    "cap": ws.param(4.0, unit="mm", min=0.01, max=500, description="end cap length"),
    "cap_width": ws.param(0.5, unit="mm", min=0.005, max=100, description="end cap width"),
    "ground": ws.param(1, integer=True, min=0, max=1, description="1: ground plane under the substrate"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=50, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(10, unit="GHz", min=0.001, max=10000, description="design frequency (loss conductivity)"),
}


def build(ctx):
    p = ctx.params
    if p.arm >= p.period or p.cap >= p.period:
        raise ValueError("arm and cap must be smaller than the period")
    if p.cap <= p.width or p.arm <= 2 * p.cap_width:
        raise ValueError("cap must be wider than the strip, and the arm longer than two caps")
    ground = bool(int(p.ground))
    stack = cell_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0, ground=ground)
    lay = L.Layout(unit="mm", outline=L.rect(p.period, p.period))
    tip = p.arm / 2.0 - p.cap_width / 2.0          # cap center distance from the cell center
    lay.add("top", L.rect(p.arm, p.width))
    lay.add("top", L.rect(p.width, p.arm))
    for sign in (-1.0, 1.0):
        lay.add("top", L.rect(p.cap_width, p.cap, center=(sign * tip, 0.0)))
        lay.add("top", L.rect(p.cap, p.cap_width, center=(0.0, sign * tip)))
    return layout_cell(lay, stack, p.period, p.period, ground=ground, h=p.h, t=p.t)


if __name__ == "__main__":
    ws.preview(build)
