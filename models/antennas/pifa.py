"""Planar inverted-F antenna (PIFA): a top plate over a ground, shorted at one edge, probe-fed.

Geometry (Z-up, mm): the ground is a rectangular PEC sheet in the XY plane at
z = 0, centred on the origin. The top plate (L1 along x, W1 along y) is a
sheet at z = H whose open end is flush with the ground's +x edge. A vertical
shorting plate of width ``ws`` joins the top plate's inner (-x) edge to the
ground at the +y corner. The feed pin rises from z = gap to the top plate at
distance ``feed_x`` from the short, in line with the short's centre; the
``feed`` port bridges the gap at its base. The pattern is broad and
near-omnidirectional with mixed polarization; the strongest component is
usually along x (the plate's resonant length).

Bodies: ``ground`` (sheet), ``radiator`` (top plate and shorting plate,
one sheet body), ``feed_pin`` (solid).

Anchors: ``feed`` (port at the pin base, normal +z, on ``feed_pin``);
loose ``top`` (top plate centre, +z) and ``ground_bottom`` (origin, -z).

``design(spec)``: Taga's resonance rule for an air PIFA, L1 + W1 + H - ws =
lambda0/4 (Hirasawa and Haneishi, *Analysis, Design, and Measurement of
Small and Low-Profile Antennas*, 1992, ch. 5), solved for L1 with
W1 = aspect * L1 and ws = short_ratio * W1. It reduces to L1 + H = lambda/4
for a full-width short. The feed position is only a starting value
(feed_x = 0.15 L1); tune it for 50 ohm in the solver.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, gap, pin radius).
"""
import witwin.studio as ws

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "L1": ws.param(17.88, unit="mm", min=1, max=5000, description="top plate length (along x)"),
    "W1": ws.param(8.94, unit="mm", min=1, max=5000, description="top plate width (along y)"),
    "H": ws.param(6.0, unit="mm", min=0.5, max=1000, description="top plate height above the ground"),
    "ws": ws.param(2.24, unit="mm", min=0.1, max=5000, description="shorting plate width (along y)"),
    "feed_x": ws.param(2.68, unit="mm", min=0.2, max=5000, description="feed pin distance from the shorting plate"),
    "pin_d": ws.param(1.0, unit="mm", min=0.05, max=50, description="feed pin diameter"),
    "gap": ws.param(1.0, unit="mm", min=0.05, max=50, description="feed gap between ground and pin"),
    "ground_x": ws.param(48.48, unit="mm", min=2, max=1e5, description="ground length (along x)"),
    "ground_y": ws.param(21.18, unit="mm", min=2, max=1e5, description="ground width (along y)"),
    "thickness": ws.param(0.2, unit="mm", min=0.001, max=10, description="sheet-metal thickness"),
    "sections": ws.param(16, integer=True, min=6, max=64, description="sides of the pin cross-section"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "H": ws.param(6.0, unit="mm", description="plate height"),
    "aspect": ws.param(0.5, description="W1 / L1"),
    "short_ratio": ws.param(0.25, description="ws / W1 (1 = shorted patch)"),
}

ARRAY_SHARED = ("ground",)


def design(spec=None):
    """PARAMS overrides for a PIFA resonant at spec f0 (Taga's rule)."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f, h = s["f0"], s["H"]
    lam = ac.wavelength_mm(f)
    l1 = (lam / 4 - h) / (1 + s["aspect"] * (1 - s["short_ratio"]))
    if l1 <= 0:
        raise ValueError(f"H = {h} mm is taller than lambda/4 = {lam / 4:.3g} mm")
    w1 = s["aspect"] * l1
    return {"f0": f, "H": h, "L1": ac.round_to(l1), "W1": ac.round_to(w1),
            "ws": ac.round_to(s["short_ratio"] * w1), "feed_x": ac.round_to(0.15 * l1),
            "ground_x": ac.round_to(l1 + 0.25 * lam), "ground_y": ac.round_to(w1 + 0.1 * lam)}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, gap, pin radius)."""
    return ac.suggested_grid(p["f0"], p["gap"], p["pin_d"] / 2)


def build(ctx):
    p = ctx.params
    if p["ws"] > p["W1"] or p["feed_x"] >= p["L1"] or p["gap"] >= p["H"]:
        raise ValueError("need ws <= W1, feed_x < L1 and gap < H")
    gx, gy = p["ground_x"] / 2, p["ground_y"] / 2
    xs, xe = gx - p["L1"], gx
    y0, y1 = -p["W1"] / 2, p["W1"] / 2
    h = p["H"]
    ground = ac.quad((-gx, -gy, 0), (gx, -gy, 0), (gx, gy, 0), (-gx, gy, 0))
    plate = ac.quad((xs, y0, h), (xe, y0, h), (xe, y1, h), (xs, y1, h))
    short = ac.quad((xs, y1 - p["ws"], 0), (xs, y1, 0), (xs, y1, h), (xs, y1 - p["ws"], h))
    yf = y1 - p["ws"] / 2
    xf = xs + p["feed_x"]
    pin = ac.cylinder((xf, yf, p["gap"]), (xf, yf, h), p["pin_d"] / 2, int(p["sections"]))
    t = p["thickness"] * 1e-3
    return [
        ws.Body(ground, name="ground", material="PEC", role="conductor", fill="surface", surface_thickness=t),
        ws.Body(ac.merge([plate, short]), name="radiator", material="PEC", role="conductor", fill="surface",
                surface_thickness=t),
        ws.Body(pin, name="feed_pin", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(xf, yf, p["gap"] / 2), normal=(0, 0, 1), kind="port")]),
        ws.anchor("top", point=((xs + xe) / 2, 0, h), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
