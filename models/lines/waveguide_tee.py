"""Rectangular waveguide T-junction, E-plane (series) or H-plane (shunt).

The main guide runs along x (broad wall ``a`` along y, narrow wall ``b``
along z, TE10 E field along z). The side arm leaves at x = 0:

- ``plane = 0`` (E-plane tee): the arm stands on the broad wall and runs
  along +z; its broad wall stays along y, so its E field lies in the xz
  plane, the same E plane as the main guide.
- ``plane = 1`` (H-plane tee): the arm leaves the narrow side wall along +y;
  its broad wall runs along x and its E field stays along z.

``branch_length`` is measured from the main guide axis to the arm's opening.
Ports: ``port1`` (x = -length/2, normal -x), ``port2`` (x = +length/2,
normal +x), ``port3`` at the arm opening (normal +z or +y).

``design`` sizes the guide like ``rect_waveguide.py`` (f0 = 1.5 fc(TE10),
b = a/2, Pozar sec. 3.3); the junction itself has no closed-form match.

    python waveguide_tee.py
"""
import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import PEC

CONFIG = {"unit": "mm", "up": "z", "grid": 0.25e-3}
PARAMS = {
    "a": ws.param(22.86, unit="mm", min=0.1, max=2000, description="broad wall inside width"),
    "b": ws.param(10.16, unit="mm", min=0.05, max=2000, description="narrow wall inside height"),
    "length": ws.param(80, unit="mm", min=1, max=10000, description="main guide length along x"),
    "branch_length": ws.param(40, unit="mm", min=0.5, max=10000, description="main guide axis to the arm opening"),
    "wall": ws.param(1.0, unit="mm", min=0.01, max=50, description="metal wall thickness"),
    "plane": ws.param(0, integer=True, min=0, max=1, description="0: E-plane (series) tee, 1: H-plane (shunt) tee"),
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


def _box(x0, x1, y0, y1, z0, z1):
    from build123d import Align, Box, Pos

    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def build(ctx):
    p = ctx.params
    a2, b2, t, half, lb = p.a / 2.0, p.b / 2.0, p.wall, p.length / 2.0, p.branch_length
    if p.plane == 0:
        arm_half_x, reach = b2, b2 + t       # E tee: the arm's narrow wall runs along x
        if lb <= reach or half <= arm_half_x + t:
            raise ValueError("branch_length must exceed b/2 + wall and length/2 must exceed b/2 + wall")
        arm_out = _box(-arm_half_x - t, arm_half_x + t, -a2 - t, a2 + t, 0.0, lb)
        arm_air = _box(-arm_half_x, arm_half_x, -a2, a2, 0.0, lb + t)
        port3 = ((0.0, 0.0, lb), (0.0, 0.0, 1.0))
    else:
        arm_half_x, reach = a2, a2 + t       # H tee: the arm's broad wall runs along x
        if lb <= reach or half <= arm_half_x + t:
            raise ValueError("branch_length must exceed a/2 + wall and length/2 must exceed a/2 + wall")
        arm_out = _box(-arm_half_x - t, arm_half_x + t, 0.0, lb, -b2 - t, b2 + t)
        arm_air = _box(-arm_half_x, arm_half_x, 0.0, lb + t, -b2, b2)
        port3 = ((0.0, lb, 0.0), (0.0, 1.0, 0.0))
    main_out = _box(-half, half, -a2 - t, a2 + t, -b2 - t, b2 + t)
    main_air = _box(-half - t, half + t, -a2, a2, -b2, b2)
    metal = (main_out + arm_out) - (main_air + arm_air)
    if not metal.is_valid or not metal.volume > 0:
        raise RuntimeError("the tee boolean failed")
    return ws.Body(metal, name="tee", material=PEC, role="conductor", anchors=[
        ws.anchor("port1", point=(-half, 0, 0), normal=(-1, 0, 0), kind="port"),
        ws.anchor("port2", point=(half, 0, 0), normal=(1, 0, 0), kind="port"),
        ws.anchor("port3", point=port3[0], normal=port3[1], kind="port"),
        ws.anchor("junction", point=(0, 0, 0)),
    ])


if __name__ == "__main__":
    ws.preview(build)
