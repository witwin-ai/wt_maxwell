"""Pyramidal horn fed by a rectangular waveguide, sized by Balanis' optimum-gain procedure.

Geometry (Z-up, mm): a straight rectangular waveguide (inside a x b, a along
x) runs from z = 0 to z = feed_len, then the walls flare to an aperture
A x B (inside) at z = feed_len + horn_len. The metal is one closed solid of
thickness ``wall``: the outside minus the air, which runs a little past both
ends so the waveguide input and the mouth are open. Beam towards +z; the
TE10 mode polarizes the aperture field along y (parallel to the b walls).

Bodies: ``horn`` (PEC solid).

Anchors: ``feed`` (port in the waveguide input plane z = 0, normal -z, on
``horn``); loose ``aperture`` (mouth centre, +z) and ``throat`` (start of
the flare).

``design(spec)``: optimum-gain horn (Balanis, *Antenna Theory*, 3rd ed.,
section 13.4.3, eqs. 13-56 to 13-58): solve
(sqrt(2 chi) - b/lambda)^2 (2 chi - 1) =
(G0/(2 pi) sqrt(3/(2 pi chi)) - a/lambda)^2 (G0^2/(6 pi^3 chi) - 1)
for chi, then A = sqrt(3 lambda rho_h), B = sqrt(2 lambda rho_e) and the
axial length p_e = (B - b) sqrt((rho_e/B)^2 - 1/4) (= p_h, which makes the
horn realizable). The waveguide is the EIA size whose band holds f0 unless
the spec gives a and b. G0 assumes 51 % aperture efficiency.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, wall).
"""
import math

import witwin.studio as ws
from build123d import Plane, Rectangle, loft

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(10e9, unit="Hz", min=1e8, max=1e12, description="design frequency (grid)"),
    "a": ws.param(22.86, unit="mm", min=0.1, max=2000, description="waveguide broad wall, inside (along x)"),
    "b": ws.param(10.16, unit="mm", min=0.1, max=2000, description="waveguide narrow wall, inside (along y)"),
    "feed_len": ws.param(29.98, unit="mm", min=0.5, max=1e4, description="straight waveguide length"),
    "A": ws.param(134.17, unit="mm", min=0.5, max=1e5, description="aperture width, inside (along x)"),
    "B": ws.param(104.18, unit="mm", min=0.5, max=1e5, description="aperture height, inside (along y)"),
    "horn_len": ws.param(156.45, unit="mm", min=0.5, max=1e5, description="flare length along z"),
    "wall": ws.param(1.0, unit="mm", min=0.05, max=50, description="wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(10e9, unit="Hz", description="design frequency"),
    "gain_dbi": ws.param(20.0, description="target gain (dBi)"),
    "a": ws.param(0.0, unit="mm", description="waveguide broad wall; 0 = EIA size for f0"),
    "b": ws.param(0.0, unit="mm", description="waveguide narrow wall; 0 = EIA size for f0"),
}


def optimum_horn(f, gain_dbi, a, b):
    """(A, B, p_e, p_h, chi) of Balanis' optimum-gain pyramidal horn; lengths in mm."""
    lam = ac.wavelength_mm(f)
    g0 = 10 ** (gain_dbi / 10)
    an, bn = a / lam, b / lam

    def residual(chi):
        lhs = (math.sqrt(2 * chi) - bn) ** 2 * (2 * chi - 1)
        rhs = (g0 / (2 * math.pi) * math.sqrt(3 / (2 * math.pi * chi)) - an) ** 2 * (g0 ** 2 / (6 * math.pi ** 3 * chi) - 1)
        return lhs - rhs

    chi = g0 / (2 * math.pi * math.sqrt(2 * math.pi))  # Balanis' first guess, eq. 13-57
    for _ in range(100):  # secant iteration
        step = 1e-6 * chi
        d = (residual(chi + step) - residual(chi)) / step
        new = chi - residual(chi) / d
        if new <= 0.5:
            new = 0.5 * (chi + 0.5)
        if abs(new - chi) < 1e-12:
            break
        chi = new
    rho_e = chi * lam
    rho_h = g0 ** 2 / (8 * math.pi ** 3 * chi) * lam
    big_a = math.sqrt(3 * lam * rho_h)
    big_b = math.sqrt(2 * lam * rho_e)
    p_e = (big_b - b) * math.sqrt((rho_e / big_b) ** 2 - 0.25)
    p_h = (big_a - a) * math.sqrt((rho_h / big_a) ** 2 - 0.25)
    return big_a, big_b, p_e, p_h, chi


def design(spec=None):
    """PARAMS overrides for an optimum-gain horn at spec f0 and gain."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    a, b = s["a"], s["b"]
    if not (a > 0 and b > 0):
        _, a, b = ac.rect_waveguide_for(f)
    big_a, big_b, p_e, _, _ = optimum_horn(f, s["gain_dbi"], a, b)
    lam = ac.wavelength_mm(f)
    return {"f0": f, "a": a, "b": b, "A": ac.round_to(big_a), "B": ac.round_to(big_b),
            "horn_len": ac.round_to(p_e), "feed_len": ac.round_to(lam), "wall": ac.round_to(min(1.0, lam / 20))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, wall)."""
    return ac.suggested_grid(p["f0"], p["wall"])


def _section(z, x, y):
    return Plane.XY.offset(z) * Rectangle(x, y)


def build(ctx):
    p = ctx.params
    t, lw, lh = p["wall"], p["feed_len"], p["horn_len"]
    top = lw + lh
    outer = loft([_section(0, p["a"] + 2 * t, p["b"] + 2 * t), _section(lw, p["a"] + 2 * t, p["b"] + 2 * t),
                  _section(top, p["A"] + 2 * t, p["B"] + 2 * t)], ruled=True)
    # The air runs one wall past each open end along the same walls, so no cut
    # face coincides with an end face (that would leave an open mesh).
    e = t
    grow_a, grow_b = (p["A"] - p["a"]) / lh, (p["B"] - p["b"]) / lh
    inner = loft([_section(-e, p["a"], p["b"]), _section(lw, p["a"], p["b"]),
                  _section(top + e, p["A"] + grow_a * e, p["B"] + grow_b * e)], ruled=True)
    return [
        ws.Body(outer - inner, name="horn", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, 0), normal=(0, 0, -1), kind="port")]),
        ws.anchor("aperture", point=(0, 0, top), normal=(0, 0, 1)),
        ws.anchor("throat", point=(0, 0, lw), normal=(0, 0, 1)),
        # The mouth is centred on the axis: a wall moves half the aperture change.
        ws.handle("A", point=(p["A"] / 2, 0, top), axis=(1, 0, 0), scale=2),
        ws.handle("B", point=(0, p["B"] / 2, top), axis=(0, 1, 0), scale=2),
        ws.handle("horn_len", point=(0, 0, top), axis=(0, 0, 1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
