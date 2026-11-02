"""Half-wave dipole in free space, as a flat strip or a round wire, with a gap port at its centre.

Geometry (Z-up, mm): the dipole lies along z, centred on the origin. A strip
(``kind`` 0) is a PEC sheet in the XZ plane (y = 0), ``width`` wide along x;
a wire (``kind`` 1) is two solid cylinders of diameter ``width``. The arms
are separated by ``gap`` at z = 0, where the ``feed`` port bridges them.
Omnidirectional in the XY plane, maximum broadside (in XY); polarization
linear along z.

Bodies: ``dipole`` (both arms).

Anchors: ``feed`` (port, gap centre, normal +z, on ``dipole``); loose
``tip_top`` and ``tip_bottom`` at the two ends.

``design(spec)``: the total tip-to-tip length is the resonant length of a
wire of radius a (a = d/2 for a wire, a = w/4 for a strip, the strip's
equivalent radius) found by setting the induced-EMF reactance to zero
(Balanis, *Antenna Theory*, 3rd ed., eq. 8-60b): about 0.47-0.48 lambda0.
The input resistance there is near 70 ohm. The feed gap is 1 % of lambda0.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, gap, wire radius
or strip width/2).
"""
import witwin.studio as ws

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "length": ws.param(57.32, unit="mm", min=1, max=1e5, description="total tip-to-tip length (along z)"),
    "gap": ws.param(1.22, unit="mm", min=0.01, max=1000, description="feed gap between the arms"),
    "width": ws.param(2.0, unit="mm", min=0.01, max=1000, description="strip width (kind 0) or wire diameter (kind 1)"),
    "kind": ws.param(0, integer=True, min=0, max=1, description="0 = flat strip (sheet), 1 = round wire (solid)"),
    "thickness": ws.param(0.035, unit="mm", min=0.001, max=10, description="strip sheet thickness (kind 0)"),
    "sections": ws.param(16, integer=True, min=6, max=64, description="sides of a wire's cross-section (kind 1)"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "width": ws.param(2.0, unit="mm", description="strip width or wire diameter"),
    "kind": ws.param(0, description="0 = strip, 1 = wire"),
}


def equivalent_radius(width, kind):
    """Wire radius (mm) with the same resonance: d/2 for a wire, w/4 for a strip."""
    return width / 2 if int(kind) == 1 else width / 4


def design(spec=None):
    """PARAMS overrides for a dipole resonant at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    length = ac.dipole_resonant_length(f, equivalent_radius(s["width"], s["kind"]))
    return {"f0": f, "width": s["width"], "kind": int(s["kind"]),
            "length": ac.round_to(length), "gap": ac.round_to(0.01 * ac.wavelength_mm(f))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, gap, wire radius or strip width/2)."""
    return ac.suggested_grid(p["f0"], p["gap"], p["width"] / 2)


def arms(p, axis_offset=(0.0, 0.0, 0.0)):
    """(mesh, fill, surface_thickness_m) of the two arms of a z-directed dipole."""
    x0, y0, z0 = axis_offset
    lo, hi = p["gap"] / 2, p["length"] / 2
    if hi <= lo:
        raise ValueError(f"length {p['length']} must exceed gap {p['gap']}")
    w = p["width"]
    if int(p["kind"]) == 1:
        r = w / 2
        mesh = ac.merge([ac.cylinder((x0, y0, z0 + lo), (x0, y0, z0 + hi), r, int(p["sections"])),
                         ac.cylinder((x0, y0, z0 - hi), (x0, y0, z0 - lo), r, int(p["sections"]))])
        return mesh, "solid", None
    mesh = ac.merge([
        ac.quad((x0 - w / 2, y0, z0 + lo), (x0 + w / 2, y0, z0 + lo), (x0 + w / 2, y0, z0 + hi), (x0 - w / 2, y0, z0 + hi)),
        ac.quad((x0 - w / 2, y0, z0 - hi), (x0 + w / 2, y0, z0 - hi), (x0 + w / 2, y0, z0 - lo), (x0 - w / 2, y0, z0 - lo)),
    ])
    return mesh, "surface", p["thickness"] * 1e-3


def build(ctx):
    p = ctx.params
    mesh, fill, thickness = arms(p)
    half = p["length"] / 2
    return [
        ws.Body(mesh, name="dipole", material="PEC", role="conductor", fill=fill, surface_thickness=thickness,
                anchors=[ws.anchor("feed", point=(0, 0, 0), normal=(0, 0, 1), kind="port")]),
        ws.anchor("tip_top", point=(0, 0, half), normal=(0, 0, 1)),
        ws.anchor("tip_bottom", point=(0, 0, -half), normal=(0, 0, -1)),
        # Both arms grow, so the top tip moves half the length change.
        ws.handle("length", point=(0, 0, half), axis=(0, 0, 1), scale=2),
    ]


if __name__ == "__main__":
    ws.preview(build)
