"""Conical corrugated (scalar) horn fed by a circular waveguide.

Geometry (Z-up, mm): a straight circular waveguide of inside radius ``a``
from z = -feed_len to z = 0, then a cone whose tooth tips flare linearly to
the inside aperture diameter ``aperture_d`` at z = horn_len. Ring grooves
(``depth`` deep, perpendicular to the axis) are cut into the cone wall with
period ``pitch``; each tooth is ``tooth`` long along z, and the mouth ends
on a tooth. The metal is one closed solid of revolution (build123d
``revolve`` of the wall's r-z profile). Beam towards +z; nearly symmetric
E- and H-plane patterns with low cross-polarization (HE11 hybrid mode);
linear polarization set by the port excitation.

Bodies: ``horn`` (PEC solid).

Anchors: ``feed`` (port in the waveguide input plane z = -feed_len, normal
-z, on ``horn``); loose ``aperture`` (mouth centre, +z) and ``throat``
(z = 0).

``design(spec)``: groove depth lambda0/4 and period lambda0/5 with a 0.8
slot-to-period ratio (Clarricoats and Olver, *Corrugated Horns for
Microwave Antennas*, 1984; Balanis, *Antenna Theory*, 3rd ed., section
13.7). The aperture follows D = eta (pi d / lambda)^2 with eta = 0.75 for a
small-flare scalar horn, and the flare length from the semi-flare angle.
Not modelled: the throat mode converter (grooves tapering from lambda/2 to
lambda/4 depth), so the match at the throat is not optimized.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, tooth, wall).
"""
import math

import witwin.studio as ws
from build123d import Axis, BuildLine, BuildPart, BuildSketch, Plane, Polyline, make_face, revolve

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z", "angular_tolerance": 0.2}

PARAMS = {
    "f0": ws.param(10e9, unit="Hz", min=1e8, max=1e12, description="design frequency (grid)"),
    "a": ws.param(10.54, unit="mm", min=0.1, max=2000, description="waveguide inside radius"),
    "feed_len": ws.param(29.98, unit="mm", min=0.5, max=1e4, description="straight waveguide length"),
    "aperture_d": ws.param(110.19, unit="mm", min=0.5, max=1e5, description="aperture diameter at the tooth tips"),
    "horn_len": ws.param(209.6, unit="mm", min=0.5, max=1e5, description="flare length along z"),
    "depth": ws.param(7.49, unit="mm", min=0.05, max=1e4, description="groove depth (radial)"),
    "pitch": ws.param(6.0, unit="mm", min=0.1, max=1e4, description="corrugation period along z"),
    "tooth": ws.param(1.2, unit="mm", min=0.05, max=1e4, description="tooth length along z"),
    "wall": ws.param(1.5, unit="mm", min=0.05, max=50, description="wall thickness behind the grooves"),
}

DESIGN_SPEC = {
    "f0": ws.param(10e9, unit="Hz", description="design frequency"),
    "gain_dbi": ws.param(20.0, description="target directivity (dBi)"),
    "flare_deg": ws.param(12.0, description="semi-flare angle (deg)"),
}

APERTURE_EFFICIENCY = 0.75


def design(spec=None):
    """PARAMS overrides for a corrugated horn at spec f0, gain and flare angle."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    a = ac.circular_waveguide_radius(f)
    g = 10 ** (s["gain_dbi"] / 10)
    d = lam / math.pi * math.sqrt(g / APERTURE_EFFICIENCY)
    length = (d / 2 - a) / math.tan(math.radians(s["flare_deg"]))
    pitch = lam / 5
    return {"f0": f, "a": ac.round_to(a), "feed_len": ac.round_to(lam), "aperture_d": ac.round_to(d),
            "horn_len": ac.round_to(length), "depth": ac.round_to(lam / 4), "pitch": ac.round_to(pitch),
            "tooth": ac.round_to(0.2 * pitch), "wall": ac.round_to(min(1.5, lam / 20))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, tooth, wall)."""
    return ac.suggested_grid(p["f0"], p["tooth"], p["wall"])


def profile(p):
    """Closed r-z polygon of the wall, counter-clockwise from the waveguide input."""
    a, lh, d, pitch, tooth = p["a"], p["horn_len"], p["depth"], p["pitch"], p["tooth"]
    rm = p["aperture_d"] / 2
    if rm <= a or tooth >= pitch:
        raise ValueError("need aperture_d > 2a and tooth < pitch")

    def r(z):
        return a + (rm - a) * z / lh

    pts = [(a, -p["feed_len"]), (a, 0.0)]
    n = int((lh - tooth) // pitch)
    for k in range(n):
        z1, z2 = k * pitch + tooth, (k + 1) * pitch
        pts += [(r(z1), z1), (r(z1) + d, z1), (r(z2) + d, z2), (r(z2), z2)]
    out = d + p["wall"]
    pts += [(rm, lh), (rm + out, lh), (a + out, 0.0), (a + p["wall"], 0.0), (a + p["wall"], -p["feed_len"])]
    # Drop repeats (a groove ending exactly where the next tooth starts).
    clean = [pts[0]]
    for q in pts[1:]:
        if abs(q[0] - clean[-1][0]) > 1e-9 or abs(q[1] - clean[-1][1]) > 1e-9:
            clean.append(q)
    return clean


def build(ctx):
    p = ctx.params
    with BuildPart() as horn:
        with BuildSketch(Plane.XZ):  # local (x, y) = global (r, z)
            with BuildLine():
                Polyline(*profile(p), close=True)
            make_face()
        revolve(axis=Axis.Z)
    return [
        ws.Body(horn.part, name="horn", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, -p["feed_len"]), normal=(0, 0, -1), kind="port")]),
        ws.anchor("aperture", point=(0, 0, p["horn_len"]), normal=(0, 0, 1)),
        ws.anchor("throat", point=(0, 0, 0), normal=(0, 0, 1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
