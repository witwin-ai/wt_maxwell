"""Microstrip line: one copper strip on a grounded substrate, a port at each board edge.

The strip runs along x across the whole board, so both ports sit on the
board edge (x = -length/2 and +length/2) with their normals pointing out of
the board. The ground fills the underside. Copper is drawn as
``fill="surface"`` sheets that carry the real copper thickness.

``design`` sizes the strip for a characteristic impedance with the
Hammerstad-Jensen model (see ``_lines_formulas.microstrip``), including the
strip thickness correction: 50 ohm on 1.6 mm FR4 (eps_r 4.4, 35 um copper)
gives W = 3.04 mm.

    python microstrip.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _lines_formulas as F
from _lines_geom import board_stack

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "w": ws.param(3.04, unit="mm", min=0.01, max=50, description="strip width"),
    "length": ws.param(30, unit="mm", min=0.5, max=1000, description="line and board length along x"),
    "board_width": ws.param(20, unit="mm", min=0.5, max=1000, description="board width along y"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="frequency for the loss conductivity"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=5, max=200, description="characteristic impedance, ohm"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0, max=0.5, description="copper thickness (0: zero-thickness model)"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """Strip width for ``z0`` on the given substrate (Hammerstad-Jensen 1980, with thickness)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    w = F.microstrip_width(v["z0"], v["h"], v["eps_r"], v["t"])
    out = {"w": round(w, 4), "h": v["h"], "eps_r": v["eps_r"]}
    if v["t"] > 0:
        out["t"] = v["t"]
    return out


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    lay = L.Layout(unit="mm", outline=L.rect(p.length, p.board_width))
    half = p.length / 2.0
    lay.add("top", L.path([(-half, 0.0), (half, 0.0)], width=p.w))
    lay.port("port1", "top", (-half, 0.0), direction=(-1, 0), width=p.w, reference="bottom")
    lay.port("port2", "top", (half, 0.0), direction=(1, 0), width=p.w, reference="bottom")
    lay.anchor("center", "top", (0.0, 0.0), normal=(0, 0, 1))
    # Strip and board are centred on the origin: an edge moves half the change.
    # The top copper sheet sits at z = h (the ground occupies -t..0).
    handles = [ws.handle("w", point=(0.0, p.w / 2, p.h), axis=(0, 1, 0), scale=2),
               ws.handle("length", point=(half, 0.0, p.h), axis=(1, 0, 0), scale=2)]
    return lay.to_bodies(stack) + handles


if __name__ == "__main__":
    ws.preview(build)
