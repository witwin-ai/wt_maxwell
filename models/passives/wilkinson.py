"""Equal-split Wilkinson power divider in microstrip (ring layout) with its isolation resistor.

The input line enters a ring from the left. Its two halves are the
quarter-wave arms (impedance sqrt(2) Z0, width ``w_arm``); they end next to
each other on the right, where the two outputs leave along +x, then step
apart by ``out_spread`` and run to the board edge. The isolation resistor
(2 Z0) bridges the two outputs right after the ring.

The resistor is a small resistive block on the board (role "other", its
conductivity set so the block between the two output lines measures
``r_iso``), plus the anchors ``iso_a`` / ``iso_b`` on its contacts for
solvers that model it as a lumped element instead. Ports: ``port1`` input
(normal -x), ``port2`` upper output, ``port3`` lower output (normals +x).

``build`` derives the arm length from f0: each arm's centerline is a
quarter guided wavelength (Hammerstad-Jensen eps_eff of ``w_arm``); the ring
radius follows from that length and the output gap ``res_gap``. ``design``
gives the widths for Z0 and sqrt(2) Z0 and r_iso = 2 Z0 (Pozar sec. 7.3).

    python wilkinson.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack, guided_wavelength_mm, width

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "w0": ws.param(3.039, unit="mm", min=0.01, max=50, description="port line width (Z0)"),
    "w_arm": ws.param(1.5919, unit="mm", min=0.01, max=50, description="quarter-wave arm width (sqrt(2) Z0)"),
    "r_iso": ws.param(100, min=0.1, max=10000, description="isolation resistor, ohm (2 Z0)"),
    "res_gap": ws.param(1.0, unit="mm", min=0.05, max=50, description="gap between the two output lines at the resistor"),
    "res_width": ws.param(0.8, unit="mm", min=0.05, max=10, description="resistor body width along x"),
    "res_thickness": ws.param(0.45, unit="mm", min=0.01, max=5, description="resistor body height"),
    "feed_length": ws.param(10, unit="mm", min=0.1, max=500, description="input line length"),
    "out_straight": ws.param(3, unit="mm", min=0.1, max=500, description="output run before the outputs step apart"),
    "out_spread": ws.param(6, unit="mm", min=0, max=500, description="extra separation of each output"),
    "out_length": ws.param(10, unit="mm", min=0.1, max=500, description="output run after the step"),
    "margin": ws.param(5, unit="mm", min=0.1, max=500, description="board margin"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="port impedance, ohm"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """Widths for Z0 and sqrt(2) Z0, resistor 2 Z0 (Pozar sec. 7.3)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    return {"w0": width(v["z0"], v["h"], v["eps_r"], v["t"]),
            "w_arm": width(math.sqrt(2.0) * v["z0"], v["h"], v["eps_r"], v["t"]),
            "r_iso": 2.0 * v["z0"], "f0": v["f0"], "h": v["h"], "t": v["t"], "eps_r": v["eps_r"]}


def ring(p):
    """``(radius, end angle delta in rad, arm length)`` in mm for the parameters ``p``."""
    arm = guided_wavelength_mm(p.w_arm, p.h, p.eps_r, p.t, p.f0) / 4.0
    gap = p.res_gap + max(p.w0, p.w_arm)   # center-to-center distance of the arm ends
    radius = F.bisect(lambda r: 2.0 * r * math.sin(arm / r) - gap, arm / math.pi * (1 + 1e-9), 1e4 * arm)
    return radius, math.pi - arm / radius, arm


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    r, delta, _ = ring(p)
    d_deg = math.degrees(delta)
    inner, outer = r - p.w_arm / 2.0, r + p.w_arm / 2.0
    if inner <= 0:
        raise ValueError("the arms are too wide for the ring radius; increase res_gap or narrow w_arm")
    lay = L.Layout(unit="mm")
    lay.add("top", L.arc_ring(inner, outer, start=d_deg, end=180.0, segments=128))
    lay.add("top", L.arc_ring(inner, outer, start=180.0, end=360.0 - d_deg, segments=128))
    x_in = -r - p.feed_length
    lay.add("top", L.path([(x_in, 0.0), (-r, 0.0)], width=p.w0))
    ya = r * math.sin(delta)
    xa = r * math.cos(delta) - p.w_arm / 2.0
    x_step = xa + p.w_arm + p.out_straight
    x_out = x_step + p.out_length
    for sign, name in ((1.0, "port2"), (-1.0, "port3")):
        y = sign * ya
        y2 = sign * (ya + p.out_spread)
        points = [(xa, y), (x_step, y), (x_step, y2), (x_out, y2)] if p.out_spread > 0 else [(xa, y), (x_out, y)]
        lay.add("top", L.path(points, width=p.w0, corner="miter"))
        lay.port(name, "top", (x_out, y2), direction=(1, 0), width=p.w0, reference="bottom")
    lay.port("port1", "top", (x_in, 0.0), direction=(-1, 0), width=p.w0, reference="bottom")
    half_y = max(ya + p.out_spread, r) + max(p.w0, p.w_arm) / 2.0 + p.margin
    lay.outline = L.rect(x_out - x_in, 2.0 * half_y, center=((x_in + x_out) / 2.0, 0.0))
    bodies = lay.to_bodies(stack)

    # Isolation resistor: a block on the board top across the two output lines.
    import numpy as np

    x0 = xa + p.w_arm + 0.5 * max(p.out_straight - p.res_width, 0.0)
    x1 = x0 + p.res_width
    y_edge = ya - p.w0 / 2.0                       # inner edge of each output line
    z0 = p.h
    z1 = z0 + p.res_thickness
    lo, hi = (x0, -ya, z0), (x1, ya, z1)
    verts = np.array([[lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]], [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]],
                      [lo[0], lo[1], hi[2]], [hi[0], lo[1], hi[2]], [hi[0], hi[1], hi[2]], [lo[0], hi[1], hi[2]]])
    faces = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4],
                      [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    # R = L / (sigma A): L is the gap between the output lines, A the block cross-section (all in m).
    sigma = (2.0 * y_edge * 1e-3) / (p.r_iso * (p.res_width * 1e-3) * (p.res_thickness * 1e-3))
    xc = (x0 + x1) / 2.0
    resistor = ws.Body((verts, faces), name="r_iso", role="other",
                       material={"name": f"resistor {p.r_iso:g} ohm", "eps_r": 1.0, "sigma_e": sigma},
                       anchors=[ws.anchor("iso_a", point=(xc, y_edge, z0), kind="lumped"),
                                ws.anchor("iso_b", point=(xc, -y_edge, z0), kind="lumped")])
    return bodies + [resistor]


if __name__ == "__main__":
    ws.preview(build)
