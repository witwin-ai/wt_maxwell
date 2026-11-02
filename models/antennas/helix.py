"""Axial-mode helical antenna over a circular ground plane, fed across a gap at the helix start.

Geometry (Z-up, mm): the ground is a PEC disc sheet in the XY plane at
z = 0. The helix winds around the z axis (right-handed, counter-clockwise
seen from +z) from z = gap to z = gap + turns * S; its wire is a circle of
diameter ``wire_d`` swept along the helix (build123d). The ``feed`` port
bridges the gap between the ground and the start of the wire. Beam
(end-fire) towards +z; polarization circular, right-hand for this winding.

Bodies: ``ground`` (disc sheet), ``helix`` (solid wire).

Anchors: ``feed`` (port under the helix start, normal +z, on ``helix``);
loose ``top`` (axis at the helix end) and ``ground_bottom`` (origin, -z).

``design(spec)``: Kraus' axial-mode conditions (Kraus, *Antennas*, 2nd ed.,
ch. 7; Balanis, *Antenna Theory*, 3rd ed., section 10.3.1): circumference
C = lambda0 (D = lambda0/pi), pitch angle 13 deg (S = C tan 13 deg, about
0.23 lambda0), ground diameter 0.75 lambda0. Input resistance about
140 C/lambda0 ohm.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, wire radius, gap).
"""
import math

import witwin.studio as ws
from build123d import BuildLine, BuildPart, BuildSketch, Circle, Helix, Plane, sweep
from witwin.studio import layout as L

import _antenna_common as ac

# A swept wire is a long B-spline surface; a 0.05 mm chord and 0.3 rad keep
# it to tens of thousands of triangles (see the cad-modeling skill).
CONFIG = {"unit": "mm", "up": "z", "tolerance": 0.05, "angular_tolerance": 0.3}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "D": ws.param(38.95, unit="mm", min=1, max=1e5, description="helix diameter (wire centre line)"),
    "S": ws.param(28.25, unit="mm", min=0.5, max=1e5, description="pitch (axial advance per turn)"),
    "turns": ws.param(6, integer=True, min=1, max=50, description="number of turns"),
    "wire_d": ws.param(1.5, unit="mm", min=0.05, max=100, description="wire diameter"),
    "gap": ws.param(3.06, unit="mm", min=0.1, max=1000, description="height of the helix start above the ground"),
    "ground_d": ws.param(91.77, unit="mm", min=2, max=1e5, description="ground disc diameter"),
    "thickness": ws.param(0.5, unit="mm", min=0.001, max=10, description="ground sheet thickness"),
    "segments": ws.param(64, integer=True, min=8, max=720, description="polygon sides of the ground disc"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="centre frequency"),
    "turns": ws.param(6, description="number of turns (more turns, more gain)"),
    "pitch_deg": ws.param(13.0, description="pitch angle (Kraus: 12-14 deg)"),
    "wire_d": ws.param(1.5, unit="mm", description="wire diameter"),
}


def design(spec=None):
    """PARAMS overrides for an axial-mode helix at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    return {"f0": f, "turns": int(round(s["turns"])), "wire_d": s["wire_d"],
            "D": ac.round_to(lam / math.pi), "S": ac.round_to(lam * math.tan(math.radians(s["pitch_deg"]))),
            "ground_d": ac.round_to(0.75 * lam), "gap": ac.round_to(max(0.025 * lam, s["wire_d"]))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, wire radius, gap)."""
    return ac.suggested_grid(p["f0"], p["wire_d"] / 2, p["gap"])


def build(ctx):
    p = ctx.params
    height = p["S"] * int(p["turns"])
    with BuildPart() as coil:
        with BuildLine():
            path = Helix(pitch=p["S"], height=height, radius=p["D"] / 2, center=(0, 0, p["gap"]))
        with BuildSketch(Plane(origin=path @ 0, z_dir=path % 0)):
            Circle(p["wire_d"] / 2)
        sweep(is_frenet=True)
    start = path @ 0
    ground = ac.polygon_sheet(L.circle(p["ground_d"] / 2, segments=int(p["segments"])), 0.0)
    return [
        ws.Body(ground, name="ground", material="PEC", role="conductor", fill="surface",
                surface_thickness=p["thickness"] * 1e-3),
        ws.Body(coil.part, name="helix", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(start.X, start.Y, p["gap"] / 2), normal=(0, 0, 1), kind="port")]),
        ws.anchor("top", point=(0, 0, p["gap"] + height), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]


if __name__ == "__main__":
    ws.preview(build)
