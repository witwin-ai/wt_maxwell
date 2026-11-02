"""Half-wave rectangular slot antenna cut in a finite conducting plane, gap-fed off centre.

Geometry (Z-up, mm): the plane is a PEC sheet in the XY plane at z = 0,
centred on the origin, with a slot ``slot_l`` long along x and ``slot_w``
wide along y. The ``feed`` port bridges the slot at x = feed_offset.
Bidirectional broadside beams along +z and -z; the field across the slot
makes the polarization linear along y (the slot's complementary dipole is
along x).

Bodies: ``plane`` (PEC sheet with the slot).

Anchors: ``feed`` (port across the slot, normal +y, on ``plane``); loose
``slot_center`` (+z).

``design(spec)``: Babinet's principle (Balanis, *Antenna Theory*, 3rd ed.,
section 12.8): the slot resonates like its complementary strip dipole, so
its length is the induced-EMF resonant length for a strip of the slot's
width (equivalent radius w/4, eq. 8-60b), and its centre resistance is
Z_slot = eta^2 / (4 Z_dipole) = about 485 ohm. The slot voltage falls as
cos(k x) from the centre, so R(x) = R_c cos^2(k x); the feed offset is
where that equals the line impedance. The plane is 1 x 0.75 lambda0; a
finite plane shifts the resonance a little.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, slot_w/2).
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "slot_l": ws.param(57.09, unit="mm", min=0.5, max=1e5, description="slot length (along x)"),
    "slot_w": ws.param(2.45, unit="mm", min=0.01, max=1e4, description="slot width (along y)"),
    "feed_offset": ws.param(22.61, unit="mm", min=0, max=1e5, description="feed position from the slot centre (along x)"),
    "plane_x": ws.param(122.36, unit="mm", min=1, max=1e6, description="plane size along x"),
    "plane_y": ws.param(91.77, unit="mm", min=1, max=1e6, description="plane size along y"),
    "thickness": ws.param(0.035, unit="mm", min=0.001, max=10, description="sheet thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "slot_w_lambda": ws.param(0.02, description="slot width in wavelengths"),
    "z0": ws.param(50.0, description="feed impedance (ohm)"),
}

DIPOLE_RESISTANCE = 73.1  # ohm, half-wave dipole (Balanis eq. 4-93)


def feed_offset_for(z0, length_mm):
    """Offset (mm) from the slot centre where R_c cos^2(pi x / slot_l) = z0."""
    r_center = ac.ETA0 ** 2 / (4 * DIPOLE_RESISTANCE)
    if z0 >= r_center:
        return 0.0
    k = math.pi / length_mm  # the half-wave standing wave fits the slot length
    return math.acos(math.sqrt(z0 / r_center)) / k


def design(spec=None):
    """PARAMS overrides for a half-wave slot at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    w = s["slot_w_lambda"] * lam
    length = ac.dipole_resonant_length(f, w / 4)
    return {"f0": f, "slot_l": ac.round_to(length), "slot_w": ac.round_to(w),
            "feed_offset": ac.round_to(feed_offset_for(s["z0"], length)),
            "plane_x": ac.round_to(lam), "plane_y": ac.round_to(0.75 * lam)}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, slot_w/2)."""
    return ac.suggested_grid(p["f0"], p["slot_w"] / 2)


def build(ctx):
    p = ctx.params
    if p["slot_l"] >= p["plane_x"] or p["slot_w"] >= p["plane_y"] or p["feed_offset"] >= p["slot_l"] / 2:
        raise ValueError("the slot must fit inside the plane and the feed inside the slot")
    shape = L.boolean(L.rect(p["plane_x"], p["plane_y"]), L.rect(p["slot_l"], p["slot_w"]), "difference")
    return [
        ws.Body(ac.polygon_sheet(shape, 0.0), name="plane", material="PEC", role="conductor", fill="surface",
                surface_thickness=p["thickness"] * 1e-3,
                anchors=[ws.anchor("feed", point=(p["feed_offset"], 0, 0), normal=(0, 1, 0), kind="port")]),
        ws.anchor("slot_center", point=(0, 0, 0), normal=(0, 0, 1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
