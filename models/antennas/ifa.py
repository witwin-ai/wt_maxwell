"""Printed inverted-F antenna (IFA) on the edge of a PCB, fed across a gap to its ground.

Geometry (Z-up, mm): an FR4 substrate occupies 0 <= z <= h in the XY plane;
all copper is one sheet on top (z = h). The ground fills the board for
y <= 0; the clearance area above it (0 < y <= clear_h) holds the IFA: a
shorting leg up from the ground edge at x = x_short, the arm running +x at
height ``arm_h``, and the feed leg dropping from the arm to ``gap`` above
the ground edge, ``feed_s`` from the short. The ``feed`` port bridges that
gap. The pattern is near-omnidirectional; the dominant polarization is
along x (the arm).

Bodies: ``substrate``, ``top`` (ground, short, arm and feed leg).

Anchors: ``feed`` (port at the gap centre, normal +y, on ``top``); loose
``ground_edge`` (ground edge under the feed) and ``board_bottom`` (origin,
-z).

``design(spec)``: quarter-wave rule of the inverted-F, arm_l + arm_h =
lambda_eff/4 (Hirasawa and Haneishi 1992, ch. 5), with lambda_eff for a
trace on a board edge from eps_eff = (eps_r + 1)/2 (quasi-static half-space
average). arm_h = 0.07 lambda_eff, feed_s = arm_h/2: starting values to tune
for 50 ohm. The ground (0.3 x 0.5 lambda0) is part of the radiator; its size
moves the resonance.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, h/2, trace_w,
gap).
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e8, max=1e11, description="design frequency (loss conversion, grid)"),
    "arm_l": ws.param(13.4, unit="mm", min=0.5, max=1000, description="arm length from the short leg (along x)"),
    "arm_h": ws.param(5.21, unit="mm", min=0.2, max=1000, description="arm height above the ground edge"),
    "feed_s": ws.param(2.61, unit="mm", min=0.1, max=1000, description="feed leg distance from the short leg"),
    "trace_w": ws.param(0.8, unit="mm", min=0.05, max=50, description="trace width"),
    "gap": ws.param(0.8, unit="mm", min=0.05, max=50, description="feed gap above the ground edge"),
    "x_short": ws.param(-14.5, unit="mm", min=-1e4, max=1e4, description="x of the short leg"),
    "board_w": ws.param(36.71, unit="mm", min=2, max=1e4, description="board width (along x)"),
    "ground_l": ws.param(61.18, unit="mm", min=2, max=1e4, description="ground length below the edge (along -y)"),
    "clear_h": ws.param(7.61, unit="mm", min=0.5, max=1e4, description="clearance area height above the ground edge"),
    "h": ws.param(1.6, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent at f0"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(1.6, unit="mm", description="substrate thickness"),
    "tan_delta": ws.param(0.02, description="substrate loss tangent"),
    "trace_w": ws.param(0.8, unit="mm", description="trace width"),
}

ARRAY_SHARED = ("substrate",)


def design(spec=None):
    """PARAMS overrides for a printed IFA resonant at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam0 = ac.wavelength_mm(f)
    lam_eff = ac.wavelength_mm(f, (s["eps_r"] + 1) / 2)
    arm_h = 0.07 * lam_eff
    arm_l = lam_eff / 4 - arm_h
    board_w = 0.3 * lam0
    return {"f0": f, "eps_r": s["eps_r"], "h": s["h"], "tan_delta": s["tan_delta"], "trace_w": s["trace_w"],
            "arm_h": ac.round_to(arm_h), "arm_l": ac.round_to(arm_l), "feed_s": ac.round_to(arm_h / 2),
            "gap": s["trace_w"], "board_w": ac.round_to(board_w), "ground_l": ac.round_to(0.5 * lam0),
            "x_short": ac.round_to(-board_w / 2 + 0.05 * lam0 / 2 + s["trace_w"]),
            "clear_h": ac.round_to(arm_h + 3 * s["trace_w"])}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, h/2, trace_w, gap)."""
    return ac.suggested_grid(p["f0"], p["h"] / 2, p["trace_w"], p["gap"])


def layout(p):
    """(Layout, LayerStack, extras) of one printed IFA."""
    stack = ac.board_stack(h=p["h"], eps_r=p["eps_r"], tan_delta=p["tan_delta"], f=p["f0"], copper=p["copper"],
                           ground=False)
    bw, tw = p["board_w"] / 2, p["trace_w"]
    xs, xf = p["x_short"], p["x_short"] + p["feed_s"]
    if xs - tw / 2 < -bw or xs + p["arm_l"] > bw or p["arm_h"] + tw / 2 > p["clear_h"] or p["feed_s"] >= p["arm_l"]:
        raise ValueError("the IFA must fit the clearance area: check x_short, arm_l, arm_h, clear_h, feed_s")
    lay = L.Layout(unit="mm", outline=L.polygon([(-bw, -p["ground_l"]), (bw, -p["ground_l"]),
                                                  (bw, p["clear_h"]), (-bw, p["clear_h"])]))
    lay.add("top", L.polygon([(-bw, -p["ground_l"]), (bw, -p["ground_l"]), (bw, 0), (-bw, 0)]))
    # Short leg and arm as one path; it starts a trace width inside the ground so they merge.
    lay.add("top", L.path([(xs, -tw), (xs, p["arm_h"]), (xs + p["arm_l"], p["arm_h"])], width=tw))
    lay.add("top", L.path([(xf, p["arm_h"]), (xf, p["gap"])], width=tw))
    lay.port("feed", "top", (xf, p["gap"] / 2), direction=(0, 1), width=tw)
    extras = [ws.anchor("ground_edge", point=(xf, 0, p["h"]), normal=(0, 1, 0)),
              ws.anchor("board_bottom", point=(0, 0, 0), normal=(0, 0, -1))]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
