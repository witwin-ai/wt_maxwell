"""Microstrip shunt stub, open or shorted, on a through line.

A through line of width ``w0`` runs along x across the board; a stub of
width ``w_stub`` and length ``stub_length`` leaves its upper edge at x = 0
along +y. ``short = 1`` ends the stub in a via to the ground. Ports sit on
the through line at the board edges (normals out along x); the anchor
``stub_end`` marks the stub's far end.

``stub_length`` is measured from the through line's edge, so the T-junction
reference-plane shift is not included. ``design`` sizes both widths with
Hammerstad-Jensen and sets the stub to ``length_deg`` electrical degrees at
f0: a 90 degree open stub is a band stop at f0, a 90 degree shorted stub a
band pass.

    python stub.py
"""
import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack, guided_wavelength_mm, width

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "w0": ws.param(3.039, unit="mm", min=0.01, max=50, description="through line width"),
    "w_stub": ws.param(3.039, unit="mm", min=0.01, max=50, description="stub width"),
    "stub_length": ws.param(17.06, unit="mm", min=0.1, max=1000, description="stub length from the through line edge"),
    "length": ws.param(40, unit="mm", min=1, max=1000, description="through line and board length along x"),
    "margin": ws.param(6, unit="mm", min=0.1, max=500, description="board margin around the stub"),
    "short": ws.param(0, integer=True, min=0, max=1, description="0: open stub, 1: shorted by a via"),
    "via_drill": ws.param(0.6, unit="mm", min=0.01, max=10, description="shorting via drill diameter"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="design frequency (loss conductivity)"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="through line impedance, ohm"),
    "z_stub": ws.param(50, min=10, max=150, description="stub impedance, ohm"),
    "length_deg": ws.param(90, unit="deg", min=1, max=360, description="stub electrical length at f0"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="design frequency"),
    "h": ws.param(1.6, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """Line and stub widths for their impedances, stub length for ``length_deg`` at f0."""
    v = F.spec_values(DESIGN_SPEC, spec)
    w0 = width(v["z0"], v["h"], v["eps_r"], v["t"])
    ws_ = width(v["z_stub"], v["h"], v["eps_r"], v["t"])
    lam = guided_wavelength_mm(ws_, v["h"], v["eps_r"], v["t"], v["f0"])
    return {"w0": w0, "w_stub": ws_, "stub_length": round(lam * v["length_deg"] / 360.0, 4),
            "h": v["h"], "eps_r": v["eps_r"], "t": v["t"], "f0": v["f0"]}


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    half = p.length / 2.0
    y_edge = p.w0 / 2.0
    y_end = y_edge + p.stub_length
    top = y_end + p.margin
    bottom = -(y_edge + p.margin)
    if p.w_stub + 2 * p.margin > p.length:
        raise ValueError("the stub and its margins do not fit on the board: increase length")
    lay = L.Layout(unit="mm", outline=L.rect(p.length, top - bottom, center=(0.0, (top + bottom) / 2.0)))
    lay.add("top", L.path([(-half, 0.0), (half, 0.0)], width=p.w0))
    lay.add("top", L.path([(0.0, 0.0), (0.0, y_end)], width=p.w_stub))
    if int(p.short):
        if p.via_drill >= p.w_stub:
            raise ValueError("via_drill must be smaller than w_stub")
        lay.via((0.0, y_end - p.w_stub / 2.0), drill=p.via_drill, from_layer="bottom", to_layer="top")
    lay.port("port1", "top", (-half, 0.0), direction=(-1, 0), width=p.w0, reference="bottom")
    lay.port("port2", "top", (half, 0.0), direction=(1, 0), width=p.w0, reference="bottom")
    lay.anchor("stub_end", "top", (0.0, y_end), normal=(0, 1, 0))
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
