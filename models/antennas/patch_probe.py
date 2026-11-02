"""Rectangular microstrip patch antenna fed by a 50 ohm coaxial probe from below the ground.

Geometry (Z-up, mm): ground sheet at z = 0 in the XY plane, substrate
0 <= z <= h, patch sheet at z = h centred on the origin. The probe pin rises
through a clearance hole in the ground at (0, y_feed) and joins the patch; a
short coax section (pin, PTFE fill, shield) hangs below the ground and ends
in the ``feed`` port plane at z = -coax_len. Boresight +z; polarization
linear along y (L is along y).

Bodies: ``ground``, ``substrate``, ``top`` (patch), ``vias`` (the probe
inside the substrate), ``coax_pin``, ``coax_dielectric``, ``coax_shield``.

Anchors: ``feed`` (port, on ``coax_pin`` at its lower end, normal -z); loose
``top`` (patch centre, +z) and ``ground_bottom`` (origin, -z).

``design(spec)``: W and L from the transmission-line model (Balanis eqs.
14-1, 14-2, 14-6, 14-7). The probe sits where R_edge cos^2(pi y0 / L) equals
the line impedance (Balanis eq. 14-20a applied to a probe feed; the probe
inductance is not compensated). The coax shield diameter follows
Z0 = 60/sqrt(eps_r) ln(D/d) for a PTFE-filled line.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, h/2, pin radius,
shield wall).
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e8, max=1e11, description="design frequency (loss conversion, grid)"),
    "W": ws.param(37.23, unit="mm", min=1, max=500, description="patch width (along x)"),
    "L": ws.param(28.81, unit="mm", min=1, max=500, description="patch resonant length (along y)"),
    "y0": ws.param(10.69, unit="mm", min=0.5, max=250, description="probe distance from the lower radiating edge"),
    "margin": ws.param(9.6, unit="mm", min=0, max=500, description="ground/substrate beyond the patch"),
    "h": ws.param(1.6, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent at f0"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
    "pin_d": ws.param(1.27, unit="mm", min=0.1, max=10, description="probe pin diameter (SMA: 1.27)"),
    "coax_d": ws.param(4.25, unit="mm", min=0.3, max=40, description="coax shield inner diameter (ground hole)"),
    "coax_eps_r": ws.param(2.1, min=1, max=20, description="coax fill relative permittivity (PTFE)"),
    "coax_len": ws.param(5.0, unit="mm", min=0.5, max=200, description="coax length below the ground"),
    "shield_wall": ws.param(1.0, unit="mm", min=0.05, max=5, description="coax shield wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(1.6, unit="mm", description="substrate thickness"),
    "tan_delta": ws.param(0.02, description="substrate loss tangent"),
    "z0": ws.param(50.0, description="coax impedance (ohm)"),
    "pin_d": ws.param(1.27, unit="mm", description="probe pin diameter"),
}

ARRAY_SHARED = ("ground", "substrate")


def design(spec=None):
    """PARAMS overrides for a probe-fed patch resonant at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f, er, h = s["f0"], s["eps_r"], s["h"]
    w, length, _ = ac.patch_size(f, er, h)
    return {
        "f0": f, "eps_r": er, "h": h, "tan_delta": s["tan_delta"], "pin_d": s["pin_d"],
        "W": ac.round_to(w), "L": ac.round_to(length),
        "y0": ac.round_to(max(0.5, ac.patch_inset(f, w, length, s["z0"]))),
        "coax_d": ac.round_to(ac.coax_outer_diameter(s["z0"], s["pin_d"], 2.1)), "coax_eps_r": 2.1,
        "margin": ac.round_to(6 * h),
    }


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, h/2, pin radius, shield wall)."""
    return ac.suggested_grid(p["f0"], p["h"] / 2, p["pin_d"] / 2, p["shield_wall"])


def layout(p):
    """(Layout, LayerStack, extras) of one probe-fed patch."""
    stack = ac.board_stack(h=p["h"], eps_r=p["eps_r"], tan_delta=p["tan_delta"], f=p["f0"], copper=p["copper"])
    m = p["margin"]
    hw, hl = p["W"] / 2 + m, p["L"] / 2 + m
    lay = L.Layout(unit="mm", outline=L.rect(2 * hw, 2 * hl))
    lay.add("top", L.rect(p["W"], p["L"]))
    yf = -p["L"] / 2 + p["y0"]
    lay.cut("ground", L.circle(p["coax_d"] / 2, center=(0, yf), segments=32))
    lay.via((0, yf), drill=p["pin_d"], from_layer="ground", to_layer="top")
    extras = ac.coax_feed(p, 0.0, yf) + [
        ws.anchor("top", point=(0, 0, p["h"]), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
