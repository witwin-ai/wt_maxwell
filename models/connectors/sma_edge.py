"""SMA edge-launch (end-launch) connector, simplified: center pin, PTFE insulator, shell.

The connector axis runs along x. The board it mounts on is not part of the
model: its edge is the plane x = 0 and its top face is z = ``board_thickness``,
so the pin rests on a trace (axis at z = board_thickness + pin radius). The
shell is a round barrel plus a square flange with two ground legs above the
board and two below; the bore holds the PTFE insulator, the pin runs through
it and sticks out ``pin_length`` over the board.

Simplified on purpose: no thread, no female contact slots, a round pin
instead of a flattened tab, legs as plain bars. Ports: ``port1`` on the
mating face (normal -x) and ``port2`` at the pin tip on the board side
(normal +x). ``board_edge`` (normal +x, toward the board) marks where the
board edge port of a microstrip should be mated (face to face).

``design`` sizes the pin for an impedance inside the given PTFE diameter
with the coaxial-line formula Z0 = eta0 / (2 pi sqrt(eps_r)) ln(D/d)
(Pozar, Table 2.1): 50 ohm in a 4.2 mm PTFE bore gives d = 1.25 mm (the
SMA standard pin is 1.27 mm).

    python sma_edge.py
"""
import math

import witwin.studio as ws

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3, "tolerance": 0.005, "angular_tolerance": 0.2}
PARAMS = {
    "d_pin": ws.param(1.27, unit="mm", min=0.05, max=10, description="center pin diameter"),
    "d_ptfe": ws.param(4.2, unit="mm", min=0.1, max=20, description="PTFE insulator (bore) diameter"),
    "d_barrel": ws.param(6.35, unit="mm", min=0.2, max=30, description="barrel outside diameter (1/4-36 thread)"),
    "barrel_length": ws.param(6.0, unit="mm", min=0.1, max=50, description="barrel length behind the flange"),
    "flange": ws.param(9.5, unit="mm", min=0.5, max=50, description="square flange size (y and z)"),
    "flange_thickness": ws.param(1.6, unit="mm", min=0.05, max=20, description="flange thickness along x"),
    "pin_length": ws.param(3.0, unit="mm", min=0, max=30, description="pin reach over the board from its edge"),
    "leg_length": ws.param(4.0, unit="mm", min=0.1, max=30, description="ground leg reach over the board"),
    "leg_width": ws.param(1.0, unit="mm", min=0.05, max=10, description="ground leg width (y)"),
    "leg_thickness": ws.param(0.6, unit="mm", min=0.05, max=5, description="ground leg thickness (z)"),
    "leg_offset": ws.param(3.0, unit="mm", min=0.1, max=20, description="leg center distance from the axis (y)"),
    "board_thickness": ws.param(1.6, unit="mm", min=0.05, max=10, description="board the connector clamps"),
    "eps_r": ws.param(2.1, min=1, max=20, description="insulator relative permittivity (PTFE 2.1)"),
    "tan_delta": ws.param(0.0002, min=0, max=1, description="insulator loss tangent"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="characteristic impedance, ohm"),
    "d_ptfe": ws.param(4.2, unit="mm", min=0.1, max=20, description="insulator diameter (kept)"),
    "eps_r": ws.param(2.1, min=1, max=20, description="insulator relative permittivity"),
}

ETA0 = 376.730313668  # free-space wave impedance, ohm


def design(spec=None):
    """Pin diameter for ``z0``: d = D exp(-2 pi sqrt(eps_r) Z0 / eta0)."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(DESIGN_SPEC))
    if unknown:
        raise KeyError(f"unknown design spec keys {unknown}; known: {sorted(DESIGN_SPEC)}")
    v = {k: float(spec.get(k, p.value)) for k, p in DESIGN_SPEC.items()}
    d = v["d_ptfe"] * math.exp(-2.0 * math.pi * math.sqrt(v["eps_r"]) * v["z0"] / ETA0)
    return {"d_pin": round(d, 4), "d_ptfe": v["d_ptfe"], "eps_r": v["eps_r"]}


def _cyl_x(radius, x0, x1, z):
    from build123d import Align, Cylinder, Pos, Rot

    return Pos(x0, 0, z) * (Rot(0, 90, 0) * Cylinder(radius, x1 - x0, align=(Align.CENTER, Align.CENTER, Align.MIN)))


def _box(x0, x1, y0, y1, z0, z1):
    from build123d import Align, Box, Pos

    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def build(ctx):
    p = ctx.params
    rp, rd, rb = p.d_pin / 2.0, p.d_ptfe / 2.0, p.d_barrel / 2.0
    if not rp < rd < rb:
        raise ValueError("need d_pin < d_ptfe < d_barrel")
    hb, ft = p.board_thickness, p.flange_thickness
    za = hb + rp                                   # axis height: the pin rests on the board top
    x_mate = -(ft + p.barrel_length)
    e = 0.5                                        # cut tools run past every opening
    half_f = p.flange / 2.0
    if p.flange <= p.d_ptfe or za - half_f > -p.leg_thickness or za + half_f < hb + p.leg_thickness:
        raise ValueError("the flange must be wider than the bore and cover the legs above and below the board")
    if p.leg_offset - p.leg_width / 2.0 <= rp:
        raise ValueError("the top legs would touch the pin: increase leg_offset")

    shell = _cyl_x(rb, x_mate, -ft, za) + _box(-ft, 0.0, -half_f, half_f, za - half_f, za + half_f)
    for side in (-1.0, 1.0):
        y0 = side * p.leg_offset - p.leg_width / 2.0
        shell = shell + _box(-ft / 2.0, p.leg_length, y0, y0 + p.leg_width, hb, hb + p.leg_thickness)
        shell = shell + _box(-ft / 2.0, p.leg_length, y0, y0 + p.leg_width, -p.leg_thickness, 0.0)
    shell = shell - _cyl_x(rd, x_mate - e, e, za)
    insulator = _cyl_x(rd, x_mate, 0.0, za) - _cyl_x(rp, x_mate - e, e, za)
    pin = _cyl_x(rp, x_mate, p.pin_length, za)
    expected = math.pi * (rd * rd - rp * rp) * (-x_mate)
    if abs(insulator.volume - expected) > 0.02 * expected:
        raise RuntimeError("the insulator boolean failed")
    if not shell.is_valid or shell.volume <= 0:
        raise RuntimeError("the shell boolean failed")
    ptfe = {"name": "PTFE" if abs(p.eps_r - 2.1) < 1e-9 else "insulator", "eps_r": p.eps_r, "tan_delta": p.tan_delta}
    return [
        ws.Body(pin, name="pin", material="PEC", role="conductor", anchors=[
            ws.anchor("port1", point=(x_mate, 0, za), normal=(-1, 0, 0), kind="port"),
            ws.anchor("port2", point=(p.pin_length, 0, za), normal=(1, 0, 0), kind="port")]),
        ws.Body(insulator, name="insulator", material=ptfe, role="dielectric"),
        ws.Body(shell, name="shell", material="PEC", role="conductor", anchors=[
            ws.anchor("board_edge", point=(0, 0, hb), normal=(1, 0, 0)),
            ws.anchor("mating_face", point=(x_mate, 0, za), normal=(-1, 0, 0))]),
    ]


if __name__ == "__main__":
    ws.preview(build)
