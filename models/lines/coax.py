"""Coaxial line along x: inner conductor, dielectric sleeve, outer conductor tube.

Three solids that touch on their cylindrical faces: the inner conductor
(PEC), the dielectric between the conductors and a PEC outer tube of
``wall`` thickness. Ports sit on the axis at both ends (x = -length/2 and
+length/2), normals pointing out along x.

``design`` uses the exact TEM impedance Z0 = eta0 / (2 pi sqrt(eps_r))
ln(D/d) (Pozar, Table 2.1): 50 ohm in PTFE (eps_r 2.1) with D = 4.1 mm gives
d = 1.22 mm.

    python coax.py
"""
import witwin.studio as ws

import _lines_formulas as F
from _lines_geom import PEC, check_volume, cylinder_along

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3, "tolerance": 0.005, "angular_tolerance": 0.2}
PARAMS = {
    "d_inner": ws.param(1.2245, unit="mm", min=0.01, max=100, description="inner conductor diameter"),
    "d_outer": ws.param(4.1, unit="mm", min=0.02, max=300, description="dielectric (outer conductor inside) diameter"),
    "wall": ws.param(0.5, unit="mm", min=0.01, max=20, description="outer conductor wall thickness"),
    "length": ws.param(30, unit="mm", min=0.1, max=2000, description="line length along x"),
    "eps_r": ws.param(2.1, min=1, max=100, description="dielectric relative permittivity (PTFE 2.1), dimensionless"),
    "tan_delta": ws.param(0.0002, min=0, max=1, description="dielectric loss tangent"),
    "f0": ws.param(1e10, unit="Hz", min=1e6, max=1e12, description="frequency for the loss conductivity"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=5, max=200, description="characteristic impedance, ohm"),
    "d_outer": ws.param(4.1, unit="mm", min=0.02, max=300, description="dielectric diameter (kept)"),
    "eps_r": ws.param(2.1, min=1, max=100, description="dielectric relative permittivity, dimensionless"),
}


def design(spec=None):
    """Inner diameter for ``z0`` in the given dielectric diameter (exact TEM formula)."""
    v = F.spec_values(DESIGN_SPEC, spec)
    return {"d_inner": round(F.coax_inner(v["z0"], v["d_outer"], v["eps_r"]), 4),
            "d_outer": v["d_outer"], "eps_r": v["eps_r"]}


def build(ctx):
    import math

    p = ctx.params
    if p.d_inner >= p.d_outer:
        raise ValueError("d_inner must be smaller than d_outer")
    half = p.length / 2.0
    ri, ro, rw = p.d_inner / 2.0, p.d_outer / 2.0, p.d_outer / 2.0 + p.wall
    e = max(p.wall, 0.1 * p.length)  # cut tools run past both ends
    inner = cylinder_along("x", ri, -half, half)
    sleeve = cylinder_along("x", ro, -half, half) - cylinder_along("x", ri, -half - e, half + e)
    shield = cylinder_along("x", rw, -half, half) - cylinder_along("x", ro, -half - e, half + e)
    check_volume(sleeve, math.pi * (ro * ro - ri * ri) * p.length, "dielectric sleeve")
    check_volume(shield, math.pi * (rw * rw - ro * ro) * p.length, "outer conductor")
    dielectric = F.dielectric("PTFE" if abs(p.eps_r - 2.1) < 1e-9 else "dielectric", p.eps_r, p.tan_delta,
                              p.f0)
    return [
        ws.Body(inner, name="inner", material=PEC, role="conductor", anchors=[
            ws.anchor("port1", point=(-half, 0, 0), normal=(-1, 0, 0), kind="port"),
            ws.anchor("port2", point=(half, 0, 0), normal=(1, 0, 0), kind="port")]),
        ws.Body(sleeve, name="dielectric", material=dielectric, role="dielectric"),
        ws.Body(shield, name="outer", material=PEC, role="conductor", anchors=[
            ws.anchor("port1_shield", point=(-half, 0, (ro + rw) / 2.0), normal=(-1, 0, 0)),
            ws.anchor("port2_shield", point=(half, 0, (ro + rw) / 2.0), normal=(1, 0, 0))]),
    ]


if __name__ == "__main__":
    ws.preview(build)
