"""Edge-coupled microstrip lines: a quarter-wave coupled-line section with four ports.

Two strips of width ``w`` run along x, ``s`` apart, over a grounded
substrate. Ports sit at the four strip ends on the board edges, normals out
along x: ``port1`` input (upper strip, left), ``port2`` through (upper,
right), ``port3`` coupled (lower, left; a backward coupler couples to the
input end) and ``port4`` isolated (lower, right).

``design`` turns a coupling level into even/odd impedances (Pozar eq.
7.79), then into W and S: Akhtarzad's synthesis refined on the Garg-Bahl
coupled-line model (3 % model accuracy). The length is a quarter wave at f0
for the mean even/odd phase velocity. A 10 dB, 50 ohm coupler on 1.6 mm
FR4 at 2.4 GHz gives W = 2.60 mm, S = 0.26 mm, L = 17.5 mm.

    python coupled_microstrip.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "w": ws.param(2.5965, unit="mm", min=0.01, max=50, description="strip width"),
    "s": ws.param(0.2645, unit="mm", min=0.005, max=50, description="edge-to-edge spacing"),
    "length": ws.param(17.52, unit="mm", min=0.5, max=1000, description="coupled length along x"),
    "margin": ws.param(8, unit="mm", min=0.1, max=500, description="board margin beside the strips (y)"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency (loss conductivity)"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="system impedance, ohm"),
    "coupling_db": ws.param(10, min=3, max=40, description="coupling, dB (positive)"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """W, S and a quarter-wave length for the coupling level (Pozar 7.79 + Garg-Bahl)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    z0e, z0o = F.coupled_impedances(v["z0"], F.db_to_voltage_coupling(v["coupling_db"]))
    w, s = F.coupled_microstrip_design(z0e, z0o, v["h"], v["eps_r"])
    length = F.coupled_quarter_wave(w, s, v["h"], v["eps_r"], v["f0"]) * 1e3  # m -> mm
    return {"w": round(w, 4), "s": round(s, 4), "length": round(length, 4),
            "h": v["h"], "eps_r": v["eps_r"], "f0": v["f0"]}


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    half = p.length / 2.0
    y0 = (p.s + p.w) / 2.0
    lay = L.Layout(unit="mm", outline=L.rect(p.length, 2.0 * (y0 + p.w / 2.0 + p.margin)))
    for y in (y0, -y0):
        lay.add("top", L.path([(-half, y), (half, y)], width=p.w))
    for name, x, y in (("port1", -half, y0), ("port2", half, y0), ("port3", -half, -y0), ("port4", half, -y0)):
        lay.port(name, "top", (x, y), direction=(1 if x > 0 else -1, 0), width=p.w, reference="bottom")
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
