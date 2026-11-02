"""Quarter-wave monopole: a vertical wire over a circular ground plane, fed across a gap at its base.

Geometry (Z-up, mm): the ground is a PEC disc sheet in the XY plane at
z = 0, centred on the origin. The wire runs along +z from z = gap to
z = height. The ``feed`` port bridges the gap between ground and wire.
Omnidirectional in azimuth; on a finite ground the beam peak tilts up from
the horizon. Polarization linear along z.

Bodies: ``ground`` (disc sheet), ``monopole`` (solid wire).

Anchors: ``feed`` (port at (0, 0, gap/2), normal +z, on ``monopole``);
loose ``tip`` (wire end) and ``ground_bottom`` (origin, -z).

``design(spec)``: by image theory a monopole over a ground plane behaves as
half of a dipole (Balanis, *Antenna Theory*, 3rd ed., section 4.7.4), so
the height is half the induced-EMF resonant length of a dipole with the same
wire radius (eq. 8-60b); input resistance about 36 ohm on an infinite
ground. The default ground radius is lambda0/2; a finite ground shifts the
resonance a little.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, gap, wire radius).
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "height": ws.param(28.18, unit="mm", min=1, max=1e5, description="wire tip height above the ground"),
    "gap": ws.param(0.61, unit="mm", min=0.01, max=1000, description="feed gap between ground and wire base"),
    "wire_d": ws.param(2.0, unit="mm", min=0.01, max=1000, description="wire diameter"),
    "ground_r": ws.param(61.18, unit="mm", min=1, max=1e5, description="ground disc radius"),
    "thickness": ws.param(0.5, unit="mm", min=0.001, max=10, description="ground sheet thickness"),
    "segments": ws.param(64, integer=True, min=8, max=720, description="polygon sides of the ground disc"),
    "sections": ws.param(16, integer=True, min=6, max=64, description="sides of the wire cross-section"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "wire_d": ws.param(2.0, unit="mm", description="wire diameter"),
}

ARRAY_SHARED = ("ground",)


def design(spec=None):
    """PARAMS overrides for a quarter-wave monopole resonant at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    return {"f0": f, "wire_d": s["wire_d"],
            "height": ac.round_to(ac.dipole_resonant_length(f, s["wire_d"] / 2) / 2),
            "gap": ac.round_to(max(0.005 * lam, 0.2)), "ground_r": ac.round_to(lam / 2)}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, gap, wire radius)."""
    return ac.suggested_grid(p["f0"], p["gap"], p["wire_d"] / 2)


def build(ctx):
    p = ctx.params
    if p["height"] <= p["gap"]:
        raise ValueError(f"height {p['height']} must exceed gap {p['gap']}")
    ground = ac.polygon_sheet(L.circle(p["ground_r"], segments=int(p["segments"])), 0.0)
    wire = ac.cylinder((0, 0, p["gap"]), (0, 0, p["height"]), p["wire_d"] / 2, int(p["sections"]))
    return [
        ws.Body(ground, name="ground", material="PEC", role="conductor", fill="surface",
                surface_thickness=p["thickness"] * 1e-3),
        ws.Body(wire, name="monopole", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, p["gap"] / 2), normal=(0, 0, 1), kind="port")]),
        ws.anchor("tip", point=(0, 0, p["height"]), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
