"""Rectangular waveguide E-plane 90 degree bend (smooth circular arc).

The guide comes in along +x, turns through a circular arc of mean radius
``radius`` in the xy plane and leaves along +y. The narrow wall ``b`` lies in
the bend plane, so the TE10 electric field turns with the bend; the broad
wall ``a`` stands along z. ``port1`` is the center of the input opening
(normal -x), ``port2`` the center of the output opening (normal +y).

``design`` sizes the guide like ``rect_waveguide.py`` (f0 = 1.5 fc(TE10),
b = a/2) and sets the mean radius to one guided wavelength at f0 (Marcuvitz,
Waveguide Handbook, 1951, sec. 5.27).

    python waveguide_bend_e.py
"""
import math

import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import PEC, waveguide_bend

CONFIG = {"unit": "mm", "up": "z", "grid": 0.25e-3, "tolerance": 0.02, "angular_tolerance": 0.15}
PARAMS = {
    "a": ws.param(22.86, unit="mm", min=0.1, max=2000, description="broad wall inside width (along z)"),
    "b": ws.param(10.16, unit="mm", min=0.05, max=2000, description="narrow wall inside width (in the bend plane)"),
    "radius": ws.param(40, unit="mm", min=0.1, max=10000, description="mean bend radius (centerline)"),
    "straight": ws.param(20, unit="mm", min=0.1, max=10000, description="straight guide before and after the arc"),
    "wall": ws.param(1.0, unit="mm", min=0.01, max=50, description="metal wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(10, unit="GHz", min=0.01, max=1000, description="operating frequency"),
    "ratio": ws.param(1.5, min=1.05, max=1.95, description="f0 / fc(TE10)"),
    "radius_wavelengths": ws.param(1.0, min=0.3, max=10, description="mean radius in guided wavelengths"),
}


def design(spec=None):
    """Guide size from f0 and a mean radius of ``radius_wavelengths`` guided wavelengths."""
    v = F.spec_values(DESIGN_SPEC, spec)
    f0 = v["f0"] * 1e9
    a, b = F.rect_waveguide_size(f0, v["ratio"])
    lam0 = F.C0 / f0
    lam_g = lam0 / math.sqrt(1.0 - (lam0 / (2.0 * a)) ** 2)
    return {"a": round(a * 1e3, 4), "b": round(b * 1e3, 4), "radius": round(v["radius_wavelengths"] * lam_g * 1e3, 4)}


def build(ctx):
    metal, (p1, n1), (p2, n2) = waveguide_bend(ctx.params, "E")
    return ws.Body(metal, name="bend", material=PEC, role="conductor", anchors=[
        ws.anchor("port1", point=p1, normal=n1, kind="port"),
        ws.anchor("port2", point=p2, normal=n2, kind="port"),
    ])


if __name__ == "__main__":
    ws.preview(build)
