"""Stripline: a strip centered between two ground planes in a homogeneous dielectric.

Layers bottom to top: ground, lower dielectric (b/2), the strip sheet at
z = b/2, upper dielectric (b/2), ground. The strip is a ``fill="surface"``
sheet with its real thickness, so the two dielectric slabs meet at the strip
plane with no air gap. Ports sit on the strip at both board edges, normals
pointing out along x.

``design`` uses Pozar's zero-thickness stripline synthesis (eq. 3.181, about
1 % from the exact conformal-mapping result): 50 ohm with b = 3.2 mm on
eps_r 4.4 gives W = 1.46 mm.

    python stripline.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _lines_formulas as F
from _lines_geom import PEC, substrate_material

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "w": ws.param(1.464, unit="mm", min=0.01, max=50, description="strip width"),
    "b": ws.param(3.2, unit="mm", min=0.02, max=40, description="ground plane spacing"),
    "length": ws.param(30, unit="mm", min=0.5, max=1000, description="line and board length along x"),
    "board_width": ws.param(16, unit="mm", min=0.5, max=1000, description="board width along y"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="dielectric relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="dielectric loss tangent"),
    "f0": ws.param(2.4, unit="GHz", min=0.001, max=1000, description="frequency for the loss conductivity"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=5, max=200, description="characteristic impedance, ohm"),
    "b": ws.param(3.2, unit="mm", min=0.02, max=40, description="ground plane spacing"),
    "eps_r": ws.param(4.4, min=1, max=100, description="dielectric relative permittivity"),
}


def design(spec=None):
    """Strip width for ``z0`` between grounds ``b`` apart (Pozar eq. 3.181)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    return {"w": round(F.stripline_width(v["z0"], v["b"], v["eps_r"]), 4), "b": v["b"], "eps_r": v["eps_r"]}


def build(ctx):
    p = ctx.params
    half_b = p.b / 2.0
    dielectric = {"material": substrate_material(p.eps_r, p.tan_delta, p.f0)}
    # Explicit z_min keeps both slabs touching at the strip plane; the strip
    # layer straddles it, and a sheet between two dielectrics sits at its middle.
    stack = L.LayerStack([
        ("ground_bottom", "ground", p.t, {"material": PEC, "z_min": -p.t}),
        ("lower", "dielectric", half_b, {**dielectric, "z_min": 0.0}),
        ("strip", "conductor", p.t, {"material": PEC, "z_min": half_b - p.t / 2.0}),
        ("upper", "dielectric", half_b, {**dielectric, "z_min": half_b}),
        ("ground_top", "ground", p.t, {"material": PEC, "z_min": p.b}),
    ], unit="mm")
    lay = L.Layout(unit="mm", outline=L.rect(p.length, p.board_width))
    half = p.length / 2.0
    lay.add("strip", L.path([(-half, 0.0), (half, 0.0)], width=p.w))
    lay.port("port1", "strip", (-half, 0.0), direction=(-1, 0), width=p.w, reference="ground_bottom")
    lay.port("port2", "strip", (half, 0.0), direction=(1, 0), width=p.w, reference="ground_bottom")
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
