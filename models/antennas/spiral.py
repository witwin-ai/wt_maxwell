"""Planar two-arm Archimedean spiral antenna, self-complementary, printed on a thin substrate.

Geometry (Z-up, mm): a square substrate 0 <= z <= h in the XY plane, no
ground (an absorber-lined cavity is usually added behind it; not modelled).
The two arms are copper sheets on top (z = h): the centre line of arm 1 is
r = r_in + a*phi for 0 <= phi <= (r_out - r_in)/a, arm 2 is arm 1 turned
180 deg, and a = 2 arm_w / pi makes the gap between turns equal to the arm
width (self-complementary). The arms start at (+-r_in, 0); the ``feed``
port bridges them at the centre. Bidirectional broadside beams along +z
and -z; polarization circular (the arms wind counter-clockwise seen from
+z, so the +z beam is left-hand circular).

Bodies: ``substrate``, ``top`` (both arms).

Anchors: ``feed`` (port at the centre, normal +x, on ``top``); loose
``top_center`` (+z) and ``board_bottom`` (-z).

``design(spec)``: band-limit rule of the active-region model (Balanis,
*Antenna Theory*, 3rd ed., section 11.5; Kaiser 1960): radiation comes from
the ring whose circumference is about one wavelength, so r_out =
lambda_low/(2 pi); the feed region must be well inside the smallest active
ring, r_in = lambda_high/(4 pi) (half its radius, a rule of thumb). The
substrate is taken as thin: wavelengths are free-space. ``turns`` sets
the growth rate.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f_high, h/2, arm_w/2).
"""
import math

import numpy as np
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f_low": ws.param(2e9, unit="Hz", min=1e6, max=1e11, description="lowest operating frequency (loss conversion)"),
    "f_high": ws.param(10e9, unit="Hz", min=1e6, max=1e11, description="highest operating frequency (grid)"),
    "r_in": ws.param(2.39, unit="mm", min=0.05, max=1e4, description="arm start radius"),
    "r_out": ws.param(23.86, unit="mm", min=0.5, max=1e5, description="arm end radius"),
    "arm_w": ws.param(1.07, unit="mm", min=0.01, max=1000, description="arm width (gap is equal)"),
    "margin": ws.param(7.49, unit="mm", min=0, max=1e4, description="substrate beyond the spiral"),
    "h": ws.param(0.8, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
    "step_deg": ws.param(5.0, unit="deg", min=0.5, max=30, description="angular step of the arm polyline"),
}

DESIGN_SPEC = {
    "f_low": ws.param(2e9, unit="Hz", description="lowest operating frequency"),
    "f_high": ws.param(10e9, unit="Hz", description="highest operating frequency"),
    "turns": ws.param(5.0, description="turns of each arm"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(0.8, unit="mm", description="substrate thickness"),
}

ARRAY_SHARED = ("substrate",)


def design(spec=None):
    """PARAMS overrides for a spiral covering spec f_low..f_high."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    if s["f_high"] <= s["f_low"]:
        raise ValueError("f_high must exceed f_low")
    r_out = ac.wavelength_mm(s["f_low"]) / (2 * math.pi)
    r_in = ac.wavelength_mm(s["f_high"]) / (4 * math.pi)
    a = (r_out - r_in) / (2 * math.pi * s["turns"])
    return {"f_low": s["f_low"], "f_high": s["f_high"], "eps_r": s["eps_r"], "h": s["h"],
            "r_in": ac.round_to(r_in), "r_out": ac.round_to(r_out), "arm_w": ac.round_to(math.pi * a / 2),
            "margin": ac.round_to(0.05 * ac.wavelength_mm(s["f_low"]))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f_high, h/2, arm_w/2)."""
    return ac.suggested_grid(p["f_high"], p["h"] / 2, p["arm_w"] / 2)


def arm_points(p, rotation=0.0):
    """Centre line of one arm (r = r_in + a phi), turned by ``rotation`` radians."""
    a = 2 * p["arm_w"] / math.pi
    phi_end = (p["r_out"] - p["r_in"]) / a
    n = max(8, int(math.ceil(math.degrees(phi_end) / p["step_deg"])))
    phi = np.linspace(0.0, phi_end, n + 1)
    r = p["r_in"] + a * phi
    return list(zip(r * np.cos(phi + rotation), r * np.sin(phi + rotation)))


def layout(p):
    """(Layout, LayerStack, extras) of one spiral."""
    if p["r_out"] <= p["r_in"] + p["arm_w"]:
        raise ValueError("r_out must exceed r_in by more than one arm width")
    stack = ac.board_stack(h=p["h"], eps_r=p["eps_r"], tan_delta=p["tan_delta"], f=p["f_low"], copper=p["copper"],
                           ground=False)
    side = 2 * (p["r_out"] + p["arm_w"] + p["margin"])
    lay = L.Layout(unit="mm", outline=L.rect(side, side))
    for rot in (0.0, math.pi):
        lay.add("top", L.path(arm_points(p, rot), width=p["arm_w"], corner="round"))
    lay.port("feed", "top", (0, 0), direction=(1, 0), width=p["arm_w"])
    extras = [ws.anchor("top_center", point=(0, 0, p["h"]), normal=(0, 0, 1)),
              ws.anchor("board_bottom", point=(0, 0, 0), normal=(0, 0, -1))]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
