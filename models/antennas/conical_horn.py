"""Conical horn fed by a circular waveguide, sized as an optimum conical horn.

Geometry (Z-up, mm): a straight circular waveguide of inside radius ``a``
runs from z = 0 to z = feed_len along the z axis, then the wall flares as a
cone to an inside aperture diameter ``aperture_d`` at z = feed_len +
horn_len. The metal is one closed solid of thickness ``wall`` (outside minus
the air; the air runs past both open ends). Beam towards +z; the TE11 mode
gives linear polarization, set by how the solver excites the port.

Bodies: ``horn`` (PEC solid).

Anchors: ``feed`` (port in the waveguide input plane z = 0, normal -z, on
``horn``); loose ``aperture`` (mouth centre, +z) and ``throat``.

``design(spec)``: optimum conical horn (Balanis, *Antenna Theory*, 3rd ed.,
section 13.6): directivity D = (pi d_m / lambda)^2 - L(s) in dB with
L(s = 3/8) = 2.91 dB, so d_m = (lambda/pi) 10^((G + 2.91)/20); the optimum
slant length is l = d_m^2 / (3 lambda). The waveguide radius puts f0 at
1.2 x the TE11 cutoff (below TM01, single-mode).

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, wall).
"""
import math

import witwin.studio as ws
from build123d import Circle, Plane, loft

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z", "angular_tolerance": 0.2}

PARAMS = {
    "f0": ws.param(10e9, unit="Hz", min=1e8, max=1e12, description="design frequency (grid)"),
    "a": ws.param(10.54, unit="mm", min=0.1, max=2000, description="waveguide inside radius"),
    "feed_len": ws.param(29.98, unit="mm", min=0.5, max=1e4, description="straight waveguide length"),
    "aperture_d": ws.param(133.4, unit="mm", min=0.5, max=1e5, description="aperture inside diameter"),
    "horn_len": ws.param(156.85, unit="mm", min=0.5, max=1e5, description="flare length along z"),
    "wall": ws.param(1.0, unit="mm", min=0.05, max=50, description="wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(10e9, unit="Hz", description="design frequency"),
    "gain_dbi": ws.param(20.0, description="target directivity (dBi)"),
}

OPTIMUM_LOSS_DB = 2.91  # L(s) at s = 3/8, Balanis section 13.6


def optimum_cone(f, gain_dbi, a):
    """(aperture diameter, slant length, flare length along z) of the optimum conical horn, mm."""
    lam = ac.wavelength_mm(f)
    d_m = lam / math.pi * 10 ** ((gain_dbi + OPTIMUM_LOSS_DB) / 20)
    slant = d_m ** 2 / (3 * lam)
    rm = d_m / 2
    apex_to_mouth = math.sqrt(slant ** 2 - rm ** 2)
    return d_m, slant, apex_to_mouth * (rm - a) / rm


def design(spec=None):
    """PARAMS overrides for an optimum conical horn at spec f0 and gain."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    a = ac.circular_waveguide_radius(f)
    d_m, _, length = optimum_cone(f, s["gain_dbi"], a)
    return {"f0": f, "a": ac.round_to(a), "aperture_d": ac.round_to(d_m), "horn_len": ac.round_to(length),
            "feed_len": ac.round_to(lam), "wall": ac.round_to(min(1.0, lam / 20))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, wall)."""
    return ac.suggested_grid(p["f0"], p["wall"])


def _ring(z, r):
    return Plane.XY.offset(z) * Circle(r)


def build(ctx):
    p = ctx.params
    t, lw, lh = p["wall"], p["feed_len"], p["horn_len"]
    rm = p["aperture_d"] / 2
    if rm <= p["a"]:
        raise ValueError("aperture_d must exceed the waveguide diameter")
    top = lw + lh
    outer = loft([_ring(0, p["a"] + t), _ring(lw, p["a"] + t), _ring(top, rm + t)], ruled=True)
    e = t
    grow = (rm - p["a"]) / lh
    inner = loft([_ring(-e, p["a"]), _ring(lw, p["a"]), _ring(top + e, rm + grow * e)], ruled=True)
    return [
        ws.Body(outer - inner, name="horn", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, 0), normal=(0, 0, -1), kind="port")]),
        ws.anchor("aperture", point=(0, 0, top), normal=(0, 0, 1)),
        ws.anchor("throat", point=(0, 0, lw), normal=(0, 0, 1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
