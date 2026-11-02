"""Vivaldi (exponentially tapered slot) antenna with a microstrip-to-slotline feed.

Geometry (Z-up, mm): the substrate lies in the XY plane, 0 <= z <= h, with
the board from y = 0 (feed edge) to the mouth at the top edge. The slot
copper is a sheet at z = 0 (lower face): it fills the board except for a
circular cavity, a straight slotline of width ``throat_w`` and the
exponential taper that opens to ``aperture_w`` at the top edge. The
microstrip on top (z = h) enters at the bottom edge at x = -feed_x, runs up,
turns +x and crosses the slotline at right angles, then ends in an open
stub ``stub_l`` past the slot. Beam (end-fire) towards +y; polarization
linear along x (across the slot).

Taper edge: |x| = c1 exp(R (y - y_t)) + c2 through (y_t, throat_w/2) and
(y_t + taper_l, aperture_w/2), with R taper_l = ``taper_exp``.

Bodies: ``slot`` (slot copper), ``substrate``, ``top`` (microstrip).

Anchors: ``feed`` (port at the microstrip's board edge, normal -y) and
``feed_ref`` (on the slot copper below it); loose ``aperture`` (mouth
centre, +y) and ``board_bottom`` (-z).

``design(spec)``: lowest frequency set by the mouth, aperture_w =
lambda0_low/2, and taper_l = lambda0_low (Gibson 1979; Shin and Schaubert,
IEEE TAP 1999, use L >= lambda_low and W >= lambda_low/2). Cavity diameter
lambda_eff/4 at sqrt(f_low f_high) with eps_eff = (eps_r + 1)/2, open stub
a quarter guided wavelength there, 50 ohm line by Hammerstad (Pozar eq.
3.197). The transition is a starting point, not a matched design.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f_high, h/2, throat_w).
"""
import math

import numpy as np
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f_low": ws.param(3e9, unit="Hz", min=1e6, max=1e11, description="lowest operating frequency (loss conversion)"),
    "f_high": ws.param(10e9, unit="Hz", min=1e6, max=1e11, description="highest operating frequency (grid)"),
    "taper_l": ws.param(99.93, unit="mm", min=1, max=1e5, description="taper length (along y)"),
    "aperture_w": ws.param(49.97, unit="mm", min=0.5, max=1e5, description="slot width at the mouth"),
    "throat_w": ws.param(0.5, unit="mm", min=0.02, max=100, description="slotline width (taper throat)"),
    "taper_exp": ws.param(4.0, min=0.1, max=20, description="R * taper_l of the exponential taper"),
    "margin": ws.param(9.99, unit="mm", min=0, max=1e4, description="copper beyond the mouth on each side"),
    "cavity_d": ws.param(8.33, unit="mm", min=0.1, max=1e4, description="circular slot cavity diameter"),
    "gap_cav": ws.param(3.06, unit="mm", min=0, max=1e4, description="cavity edge to the microstrip crossing"),
    "slot_back": ws.param(3.06, unit="mm", min=0, max=1e4, description="microstrip crossing to the taper throat"),
    "bottom": ws.param(8.33, unit="mm", min=0, max=1e4, description="board below the cavity"),
    "feed_w": ws.param(1.53, unit="mm", min=0.05, max=50, description="microstrip width (50 ohm)"),
    "feed_x": ws.param(8.75, unit="mm", min=0.1, max=1e4, description="x offset of the microstrip's vertical run"),
    "stub_l": ws.param(7.5, unit="mm", min=0, max=1e4, description="open stub past the slot centre"),
    "h": ws.param(0.8, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
    "samples": ws.param(64, integer=True, min=8, max=1024, description="points along each taper edge"),
}

DESIGN_SPEC = {
    "f_low": ws.param(3e9, unit="Hz", description="lowest operating frequency"),
    "f_high": ws.param(10e9, unit="Hz", description="highest operating frequency"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(0.8, unit="mm", description="substrate thickness"),
    "tan_delta": ws.param(0.02, description="substrate loss tangent"),
}

ARRAY_SHARED = ("substrate",)


def design(spec=None):
    """PARAMS overrides for a Vivaldi covering spec f_low..f_high."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    if s["f_high"] <= s["f_low"]:
        raise ValueError("f_high must exceed f_low")
    er, h = s["eps_r"], s["h"]
    lam_low = ac.wavelength_mm(s["f_low"])
    f_c = math.sqrt(s["f_low"] * s["f_high"])
    lam_eff = ac.wavelength_mm(f_c, (er + 1) / 2)
    feed_w = ac.microstrip_width(50.0, er, h)
    cavity = lam_eff / 4
    return {"f_low": s["f_low"], "f_high": s["f_high"], "eps_r": er, "h": h, "tan_delta": s["tan_delta"],
            "aperture_w": ac.round_to(lam_low / 2), "taper_l": ac.round_to(lam_low),
            "throat_w": ac.round_to(max(0.1, min(0.5, ac.wavelength_mm(s["f_high"]) / 60))),
            "margin": ac.round_to(0.1 * lam_low), "cavity_d": ac.round_to(cavity),
            "feed_w": ac.round_to(feed_w),
            "stub_l": ac.round_to(ac.microstrip_guided_wavelength(f_c, 50.0, er, h) / 4),
            "feed_x": ac.round_to(cavity / 2 + 3 * feed_w), "gap_cav": ac.round_to(2 * feed_w),
            "slot_back": ac.round_to(2 * feed_w), "bottom": ac.round_to(max(cavity, 0.05 * lam_low))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f_high, h/2, throat_w)."""
    return ac.suggested_grid(p["f_high"], p["h"] / 2, p["throat_w"])


def heights(p):
    """(y of cavity centre, microstrip crossing, taper throat, mouth) in mm."""
    y_cav = p["bottom"] + p["cavity_d"] / 2
    y_c = y_cav + p["cavity_d"] / 2 + p["gap_cav"]
    y_t = y_c + p["slot_back"]
    return y_cav, y_c, y_t, y_t + p["taper_l"]


def taper_polygon(p, y_t):
    """The exponentially opening slot, run a little past the mouth so the cut is clean."""
    length, r = p["taper_l"], p["taper_exp"] / p["taper_l"]
    w0, w1 = p["throat_w"] / 2, p["aperture_w"] / 2
    c1 = (w1 - w0) / (math.exp(r * length) - 1)
    c2 = w0 - c1
    ys = np.linspace(0.0, length, int(p["samples"]))
    xs = c1 * np.exp(r * ys) + c2
    right = list(zip(xs, ys + y_t)) + [(w1, y_t + length + 1.0)]
    left = [(-x, y) for x, y in reversed(right)]
    return L.polygon(right + left)


def layout(p):
    """(Layout, LayerStack, extras) of one Vivaldi."""
    if p["aperture_w"] <= p["throat_w"]:
        raise ValueError("aperture_w must exceed throat_w")
    stack = L.LayerStack([
        ("slot", "ground", p["copper"]),
        ("substrate", "dielectric", p["h"], {"eps_r": p["eps_r"], "tan_delta": p["tan_delta"]}),
        ("top", "conductor", p["copper"]),
    ], unit="mm", z0=-p["copper"], frequency=p["f_low"])
    y_cav, y_c, y_t, y_top = heights(p)
    hw = max(p["aperture_w"] / 2 + p["margin"], p["feed_x"] + p["feed_w"] + p["margin"],
             p["stub_l"] + p["margin"])
    lay = L.Layout(unit="mm", outline=L.polygon([(-hw, 0), (hw, 0), (hw, y_top), (-hw, y_top)]))
    slot = L.boolean(taper_polygon(p, y_t), L.rect(p["throat_w"], y_t - y_cav, center=(0, (y_t + y_cav) / 2)))
    slot = L.boolean(slot, L.circle(p["cavity_d"] / 2, center=(0, y_cav), segments=64))
    lay.cut("slot", slot)
    lay.add("top", L.path([(-p["feed_x"], 0), (-p["feed_x"], y_c), (p["stub_l"], y_c)], width=p["feed_w"]))
    lay.port("feed", "top", (-p["feed_x"], 0), direction=(0, -1), width=p["feed_w"], reference="slot")
    extras = [ws.anchor("aperture", point=(0, y_top, p["h"] / 2), normal=(0, 1, 0)),
              ws.anchor("board_bottom", point=(0, y_top / 2, 0), normal=(0, 0, -1))]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
