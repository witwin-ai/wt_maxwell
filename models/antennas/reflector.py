"""Prime-focus parabolic reflector with an open-ended circular waveguide as feed placeholder.

Geometry (Z-up, mm): the dish is a solid of revolution about the z axis;
its inner (reflecting) surface is z = r^2 / (4 F) for r <= D/2, with the
vertex at the origin, and it is ``thickness`` thick behind that surface.
The feed is a PEC tube (circular waveguide, inside radius ``feed_a``) on the
axis whose open mouth sits at the focus z = F and faces the dish; it runs
up to z = F + feed_len. The ``feed`` port is the waveguide's back plane.
Replace the tube with a horn generator for a real feed. Struts are not
modelled. Beam towards +z; polarization follows the feed (TE11, linear).

Bodies: ``dish``, ``feed`` (both PEC solids).

Anchors: ``feed`` (port in the feed's back plane, normal +z, on ``feed``);
loose ``focus`` (the focal point, -z towards the dish) and ``vertex``.

``design(spec)``: aperture efficiency eta_ap = 0.55 (Balanis, *Antenna
Theory*, 3rd ed., section 15.4), so D = (lambda/pi) sqrt(G / eta_ap);
F = (F/D) D; the open-waveguide feed radius puts f0 at 1.2 x the TE11
cutoff. Its pattern is not matched to the dish edge angle, so the real
efficiency will differ.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, thickness,
feed wall).
"""
import math

import numpy as np
import witwin.studio as ws
from build123d import Axis, BuildLine, BuildPart, BuildSketch, Plane, Polyline, make_face, revolve

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z", "angular_tolerance": 0.2}

PARAMS = {
    "f0": ws.param(10e9, unit="Hz", min=1e8, max=1e12, description="design frequency (grid)"),
    "D": ws.param(406.9, unit="mm", min=1, max=1e6, description="dish diameter"),
    "F": ws.param(162.76, unit="mm", min=1, max=1e6, description="focal length"),
    "thickness": ws.param(1.5, unit="mm", min=0.01, max=1000, description="dish thickness"),
    "feed_a": ws.param(10.54, unit="mm", min=0.1, max=1e4, description="feed waveguide inside radius"),
    "feed_len": ws.param(29.98, unit="mm", min=0.5, max=1e4, description="feed waveguide length"),
    "feed_wall": ws.param(1.5, unit="mm", min=0.01, max=100, description="feed wall thickness"),
    "samples": ws.param(48, integer=True, min=8, max=1000, description="points along the parabola profile"),
}

DESIGN_SPEC = {
    "f0": ws.param(10e9, unit="Hz", description="design frequency"),
    "gain_dbi": ws.param(30.0, description="target gain (dBi)"),
    "f_over_d": ws.param(0.4, description="focal length / diameter"),
}

APERTURE_EFFICIENCY = 0.55


def design(spec=None):
    """PARAMS overrides for a prime-focus dish at spec f0, gain and F/D."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    d = lam / math.pi * math.sqrt(10 ** (s["gain_dbi"] / 10) / APERTURE_EFFICIENCY)
    return {"f0": f, "D": ac.round_to(d), "F": ac.round_to(s["f_over_d"] * d),
            "feed_a": ac.round_to(ac.circular_waveguide_radius(f)), "feed_len": ac.round_to(lam),
            "thickness": ac.round_to(min(1.5, lam / 20)), "feed_wall": ac.round_to(min(1.5, lam / 20))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, thickness, feed wall)."""
    return ac.suggested_grid(p["f0"], p["thickness"], p["feed_wall"])


def _revolve(points):
    with BuildPart() as part:
        with BuildSketch(Plane.XZ):  # local (x, y) = global (r, z)
            with BuildLine():
                Polyline(*points, close=True)
            make_face()
        revolve(axis=Axis.Z)
    return part.part


def build(ctx):
    p = ctx.params
    rad, focal, t = p["D"] / 2, p["F"], p["thickness"]
    if focal <= rad ** 2 / (4 * focal):
        raise ValueError("the focus must lie above the dish rim (F/D > 0.25)")
    r = np.linspace(0.0, rad, int(p["samples"]))
    z = r ** 2 / (4 * focal)
    front = list(zip(r, z))
    back = [(x, y - t) for x, y in reversed(front)]
    dish = _revolve(front + back)
    a, w = p["feed_a"], p["feed_wall"]
    z0, z1 = focal, focal + p["feed_len"]
    feed = _revolve([(a, z0), (a + w, z0), (a + w, z1), (a, z1)])
    return [
        ws.Body(dish, name="dish", material="PEC", role="conductor"),
        ws.Body(feed, name="feed", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, z1), normal=(0, 0, 1), kind="port")]),
        ws.anchor("focus", point=(0, 0, focal), normal=(0, 0, -1)),
        ws.anchor("vertex", point=(0, 0, 0), normal=(0, 0, 1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
