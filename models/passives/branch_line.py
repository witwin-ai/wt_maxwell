"""Microstrip branch-line (90 degree hybrid) coupler.

A square of four quarter-wave lines: the two series arms along x
(impedance Z0/sqrt(2), width ``w_series``) and the two shunt arms along y
(impedance Z0, width ``w_shunt``). A feed of width ``w0`` leaves each corner
along x to the board edge. Ports follow Pozar's Fig. 7.21: ``port1`` input
(upper left), ``port2`` through (upper right, -90 deg), ``port3`` coupled
(lower right, -180 deg), ``port4`` isolated (lower left); normals point out
along x.

``build`` derives the arm lengths from f0: each arm's centerline is a
quarter guided wavelength of its own width (Hammerstad-Jensen eps_eff).
``design`` gives the three widths (Pozar sec. 7.5). Junction (T and cross)
discontinuities are ignored.

    python branch_line.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack, guided_wavelength_mm, width

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "w0": ws.param(3.039, unit="mm", min=0.01, max=50, description="feed width (Z0)"),
    "w_series": ws.param(5.1998, unit="mm", min=0.01, max=50, description="series arm width (Z0/sqrt(2))"),
    "w_shunt": ws.param(3.039, unit="mm", min=0.01, max=50, description="shunt arm width (Z0)"),
    "feed_length": ws.param(8, unit="mm", min=0.1, max=500, description="feed length from each corner"),
    "margin": ws.param(5, unit="mm", min=0.1, max=500, description="board margin above and below"),
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
    """Widths for Z0 (feeds, shunt arms) and Z0/sqrt(2) (series arms), Pozar sec. 7.5."""
    v = F.spec_values(DESIGN_SPEC, spec)
    w0 = width(v["z0"], v["h"], v["eps_r"], v["t"])
    return {"w0": w0, "w_shunt": w0, "w_series": width(v["z0"] / math.sqrt(2.0), v["h"], v["eps_r"], v["t"]),
            "f0": v["f0"], "h": v["h"], "t": v["t"], "eps_r": v["eps_r"]}


def arms(p):
    """``(series arm length, shunt arm length)`` in mm: quarter guided wavelengths at f0."""
    return (guided_wavelength_mm(p.w_series, p.h, p.eps_r, p.t, p.f0) / 4.0,
            guided_wavelength_mm(p.w_shunt, p.h, p.eps_r, p.t, p.f0) / 4.0)


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    ls, lp = arms(p)
    x, y = ls / 2.0, lp / 2.0
    lay = L.Layout(unit="mm")
    for sy in (1.0, -1.0):
        lay.add("top", L.rect(ls + p.w_shunt, p.w_series, center=(0.0, sy * y)))
    for sx in (1.0, -1.0):
        lay.add("top", L.rect(p.w_shunt, lp + p.w_series, center=(sx * x, 0.0)))
    edge = x + p.w_shunt / 2.0 + p.feed_length
    for name, sx, sy in (("port1", -1, 1), ("port2", 1, 1), ("port3", 1, -1), ("port4", -1, -1)):
        lay.add("top", L.path([(sx * x, sy * y), (sx * edge, sy * y)], width=p.w0))
        lay.port(name, "top", (sx * edge, sy * y), direction=(sx, 0), width=p.w0, reference="bottom")
    half_y = y + max(p.w_series, p.w0) / 2.0 + p.margin
    lay.outline = L.rect(2.0 * edge, 2.0 * half_y)
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
