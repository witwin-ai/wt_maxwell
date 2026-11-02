"""Grounded (conductor-backed) coplanar waveguide with an optional via fence.

Like ``cpw.py`` plus a ground plane under the substrate. With ``vias = 1``
two rows of vias tie the coplanar grounds to the backing ground, which keeps
the parallel-plate mode down. Ports sit on the strip at the two board edges
(normals out along x).

``design`` finds the slot width with the conductor-backed CPW model (Simons
2001, sec. 2.4.1, eqs. 2.40-2.42): 50 ohm with a 1.5 mm strip on 1.6 mm FR4
gives a 0.255 mm slot. The model ignores the via fence and assumes wide
coplanar grounds.

    python grounded_cpw.py
"""
import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import cpw_bodies

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "s": ws.param(1.5, unit="mm", min=0.005, max=50, description="center strip width"),
    "gap": ws.param(0.2546, unit="mm", min=0.005, max=50, description="slot width between strip and ground"),
    "ground_width": ws.param(5, unit="mm", min=0.05, max=500, description="coplanar ground width per side"),
    "length": ws.param(30, unit="mm", min=0.5, max=1000, description="line and board length along x"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(2.4, unit="GHz", min=0.001, max=1000, description="frequency for the loss conductivity"),
    "vias": ws.param(1, integer=True, min=0, max=1, description="1: via fence on both sides"),
    "via_drill": ws.param(0.4, unit="mm", min=0.01, max=5, description="via drill diameter"),
    "via_pitch": ws.param(2.5, unit="mm", min=0.05, max=50, description="via spacing along the line"),
    "via_offset": ws.param(0.75, unit="mm", min=0.01, max=50, description="via center distance from the slot edge"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=20, max=150, description="characteristic impedance, ohm"),
    "s": ws.param(1.5, unit="mm", min=0.005, max=50, description="center strip width (kept)"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
}


def design(spec=None):
    """Slot width for ``z0`` with the given strip (conductor-backed CPW, Simons 2001 eqs. 2.40-2.42)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    gap = F.cpw_gap(v["z0"], v["s"], v["h"], v["eps_r"], grounded=True)
    return {"gap": round(gap, 4), "s": v["s"], "h": v["h"], "eps_r": v["eps_r"]}


def build(ctx):
    return cpw_bodies(ctx.params, grounded=True)


if __name__ == "__main__":
    ws.preview(build)
