"""Split-ring resonator (SRR) metasurface unit cell: one or two square split rings on a substrate.

The outer ring (side ``ring``, strip ``width``) has its split ``gap`` in the
+y side; with ``rings = 2`` an inner ring, ``spacing`` inside it, has its
split in the -y side (the edge-coupled double SRR of Pendry et al., IEEE
Trans. MTT-47(11), 1999). The rings sit on a ``period`` x ``period``
substrate cell; ``ground = 1`` adds a ground plane under it. Copper is
drawn as ``fill="surface"`` sheets carrying the copper thickness.

Anchors: ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax``
(kind ``periodic``) for periodic or Floquet boundaries; ``port1`` (top,
normal +z) and, without ground, ``port2`` (bottom, normal -z) for the
Floquet ports; ``split_outer`` / ``split_inner`` mark the gaps.

No closed-form design: quasi-static LC models of the SRR (e.g. Marques et
al., Phys. Rev. B 65, 144440, 2002) need the ring and gap capacitances and
are good to about 10 %; size the cell with the solver.

    python split_ring.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

from _periodic_cells import cell_stack, layout_cell

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "period": ws.param(5.0, unit="mm", min=0.05, max=500, description="cell period (x and y)"),
    "ring": ws.param(4.0, unit="mm", min=0.02, max=500, description="outer ring side"),
    "width": ws.param(0.3, unit="mm", min=0.005, max=50, description="ring strip width"),
    "spacing": ws.param(0.3, unit="mm", min=0.005, max=50, description="gap between the outer and inner ring"),
    "gap": ws.param(0.4, unit="mm", min=0.005, max=50, description="split width in each ring"),
    "rings": ws.param(2, integer=True, min=1, max=2, description="1: single split ring, 2: double SRR"),
    "ground": ws.param(0, integer=True, min=0, max=1, description="1: ground plane under the substrate"),
    "h": ws.param(0.8, unit="mm", min=0.01, max=50, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(1e10, unit="Hz", min=1e6, max=1e13, description="design frequency (loss conductivity)"),
}


def _split_ring(side, width, gap, split_side):
    """A square ring of outer ``side`` and strip ``width`` with a ``gap`` cut in its +y (1) or -y (-1) side."""
    ring = L.boolean(L.rect(side, side), L.rect(side - 2 * width, side - 2 * width), "difference")
    cut = L.rect(gap, 2 * width, center=(0.0, split_side * (side / 2.0 - width / 2.0)))
    return L.boolean(ring, cut, "difference")


def build(ctx):
    p = ctx.params
    if p.ring >= p.period:
        raise ValueError("ring must be smaller than the period")
    inner = p.ring - 2 * (p.width + p.spacing)
    rings = int(p.rings)
    if 2 * p.width >= p.ring or p.gap >= p.ring - 2 * p.width:
        raise ValueError("width or gap leaves no ring")
    if rings == 2 and (inner <= 2 * p.width or p.gap >= inner - 2 * p.width):
        raise ValueError("the inner ring does not fit: reduce width, spacing or gap")
    ground = bool(int(p.ground))
    stack = cell_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0, ground=ground)
    lay = L.Layout(unit="mm", outline=L.rect(p.period, p.period))
    lay.add("top", _split_ring(p.ring, p.width, p.gap, 1))
    lay.anchor("split_outer", "top", (0.0, p.ring / 2.0 - p.width / 2.0))
    if rings == 2:
        lay.add("top", _split_ring(inner, p.width, p.gap, -1))
        lay.anchor("split_inner", "top", (0.0, -(inner / 2.0 - p.width / 2.0)))
    return layout_cell(lay, stack, p.period, p.period, ground=ground, h=p.h, t=p.t)


if __name__ == "__main__":
    ws.preview(build)
