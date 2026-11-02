"""Straight rectangular waveguide section along x (WR-90 by default).

A PEC tube: broad wall ``a`` along y, narrow wall ``b`` along z, metal
``wall`` thick, open at both ends. The TE10 electric field points along z.
Ports sit at the centers of the two openings (x = -length/2 and +length/2),
normals pointing out along x.

``design`` picks ``a`` so that ``f0`` is 1.5 times the TE10 cutoff, inside
the usual 1.25..1.9 fc band and below the TE20 cutoff, with ``b = a/2``
(Pozar sec. 3.3). 10 GHz gives a = 22.48 mm, close to WR-90 (22.86 mm).

    python rect_waveguide.py
"""
import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import PEC, check_volume

CONFIG = {"unit": "mm", "up": "z", "grid": 0.25e-3}
PARAMS = {
    "a": ws.param(22.86, unit="mm", min=0.1, max=2000, description="broad wall inside width (along y)"),
    "b": ws.param(10.16, unit="mm", min=0.05, max=2000, description="narrow wall inside height (along z)"),
    "length": ws.param(50, unit="mm", min=0.5, max=10000, description="section length along x"),
    "wall": ws.param(1.0, unit="mm", min=0.01, max=50, description="metal wall thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(1e10, unit="Hz", min=1e7, max=1e12, description="operating frequency"),
    "ratio": ws.param(1.5, min=1.05, max=1.95, description="f0 / fc(TE10), dimensionless"),
}


def design(spec=None):
    """``a`` and ``b = a/2`` with ``f0 = ratio * fc(TE10)``."""
    v = F.spec_values(DESIGN_SPEC, spec)
    a, b = F.rect_waveguide_size(v["f0"], v["ratio"])
    return {"a": round(a * 1e3, 4), "b": round(b * 1e3, 4)}


def build(ctx):
    from build123d import Box

    p = ctx.params
    t, half = p.wall, p.length / 2.0
    outer = Box(p.length, p.a + 2 * t, p.b + 2 * t)
    metal = outer - Box(p.length + 2 * t, p.a, p.b)  # the air runs past both openings
    check_volume(metal, p.length * ((p.a + 2 * t) * (p.b + 2 * t) - p.a * p.b), "waveguide wall")
    return ws.Body(metal, name="waveguide", material=PEC, role="conductor", anchors=[
        ws.anchor("port1", point=(-half, 0, 0), normal=(-1, 0, 0), kind="port"),
        ws.anchor("port2", point=(half, 0, 0), normal=(1, 0, 0), kind="port"),
    ])


if __name__ == "__main__":
    ws.preview(build)
