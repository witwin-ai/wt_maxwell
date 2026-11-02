"""Straight circular waveguide section along x.

A PEC tube of inside ``radius`` and ``wall`` thickness, open at both ends.
Ports sit at the centers of the openings (x = -length/2 and +length/2),
normals pointing out along x.

``design`` puts f0 midway between the TE11 and TM01 cutoffs, the center of
the single-mode band: radius = c (p'11 + p01) / (4 pi f0) with p'11 = 1.8412
and p01 = 2.4049 (Pozar sec. 3.4). 10 GHz gives 10.13 mm (TE11 cutoff
8.67 GHz, TM01 11.33 GHz).

    python circular_waveguide.py
"""
import math

import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import PEC, check_volume, cylinder_along

CONFIG = {"unit": "mm", "up": "z", "grid": 0.25e-3, "tolerance": 0.02, "angular_tolerance": 0.15}
PARAMS = {
    "radius": ws.param(10.13, unit="mm", min=0.05, max=2000, description="inside radius"),
    "length": ws.param(50, unit="mm", min=0.5, max=10000, description="section length along x"),
    "wall": ws.param(1.0, unit="mm", min=0.01, max=50, description="metal wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(10, unit="GHz", min=0.01, max=1000, description="operating frequency"),
}


def design(spec=None):
    """Radius that centers f0 in the TE11..TM01 single-mode band."""
    v = F.spec_values(DESIGN_SPEC, spec)
    return {"radius": round(F.circular_waveguide_radius(v["f0"] * 1e9) * 1e3, 4)}


def build(ctx):
    p = ctx.params
    half, r, t = p.length / 2.0, p.radius, p.wall
    metal = cylinder_along("x", r + t, -half, half) - cylinder_along("x", r, -half - t, half + t)
    check_volume(metal, math.pi * ((r + t) ** 2 - r * r) * p.length, "circular waveguide wall")
    return ws.Body(metal, name="waveguide", material=PEC, role="conductor", anchors=[
        ws.anchor("port1", point=(-half, 0, 0), normal=(-1, 0, 0), kind="port"),
        ws.anchor("port2", point=(half, 0, 0), normal=(1, 0, 0), kind="port"),
    ])


if __name__ == "__main__":
    ws.preview(build)
