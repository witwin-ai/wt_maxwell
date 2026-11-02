"""Planar array in the XY plane, rectangular or triangular lattice, of any single-element generator here.

Geometry (Z-up, mm): ``nx`` x ``ny`` copies of the element chosen by
``element`` (codes as in ``linear_array.py``), translated to a lattice
centred on the origin with the element's own orientation (patches and horns
face +z). Pitch along x is ``spacing_mm`` when above zero, else
``spacing`` wavelengths at f0; along y it is ``spacing_y_mm`` /
``spacing_y`` the same way, and when both are zero it equals the x pitch
(rectangular) or sqrt(3)/2 of it (triangular, equilateral). The triangular
lattice (``lattice`` = 1) shifts every odd row by half the x pitch. With
``use_design`` = 1 each element takes its ``design()`` dimensions for f0.

Planar elements share one board (one substrate, one ground with all the
holes); ground planes of 3D elements merge into one rectangle. Every element
keeps its own port ``feed_<i>`` (i row major, x fastest): there is no feed
network here; drive the ports from the solver with the excitation you want.

Element codes: 0 = patch, 1 = patch_probe, 2 = circular_patch,
3 = aperture_coupled_patch, 4 = dipole, 5 = monopole, 6 = pifa, 7 = ifa,
8 = yagi, 9 = lpda, 10 = helix, 11 = spiral, 12 = pyramidal_horn,
13 = conical_horn, 14 = corrugated_horn, 15 = vivaldi, 16 = slot,
17 = reflector.

Anchors: element anchors with suffix ``_<i>``, loose ``center``.

``design(spec)``: copies f0, element, nx, ny, lattice and spacing (default
lambda0/2; for a triangular lattice the x pitch).

Validation grid: the element's ``suggested_grid``.
"""
import math

import witwin.studio as ws

import _antenna_common as ac
import _array_common as arr

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "element": ws.param(0, integer=True, min=0, max=len(arr.ELEMENTS) - 1, description="element code: " + arr.ELEMENT_HELP),
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e12, description="array design frequency"),
    "nx": ws.param(2, integer=True, min=1, max=128, description="elements along x"),
    "ny": ws.param(2, integer=True, min=1, max=128, description="rows along y"),
    "lattice": ws.param(0, integer=True, min=0, max=1, description="0 = rectangular, 1 = triangular"),
    "spacing": ws.param(0.5, min=0.01, max=100, description="x pitch in free-space wavelengths at f0"),
    "spacing_mm": ws.param(0, unit="mm", min=0, max=1e6, description="x pitch in mm; 0 = use spacing"),
    "spacing_y": ws.param(0, min=0, max=100, description="y pitch in wavelengths; 0 = from the x pitch"),
    "spacing_y_mm": ws.param(0, unit="mm", min=0, max=1e6, description="y pitch in mm; 0 = use spacing_y"),
    "use_design": ws.param(1, integer=True, min=0, max=1, description="1 = element design() at f0, 0 = element defaults"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="array design frequency"),
    "element": ws.param(0, description="element code"),
    "nx": ws.param(2, description="elements along x"),
    "ny": ws.param(2, description="rows along y"),
    "lattice": ws.param(0, description="0 = rectangular, 1 = triangular"),
    "spacing": ws.param(0.5, description="x pitch in wavelengths"),
}


def design(spec=None):
    """PARAMS overrides for the array (the element dimensions come from its own design())."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    return {"f0": s["f0"], "element": int(s["element"]), "nx": int(s["nx"]), "ny": int(s["ny"]),
            "lattice": int(s["lattice"]), "spacing": s["spacing"], "spacing_mm": 0, "spacing_y": 0,
            "spacing_y_mm": 0, "use_design": 1}


def element_values(p):
    """Resolved element parameters (mm) for this array."""
    return arr.element_values(p["element"], p["f0"], bool(p["use_design"]))


def suggested_grid(p):
    """Grid step in mm: the element's suggested grid."""
    return arr.element_namespace(p["element"])["suggested_grid"](element_values(p))


def pitches(p):
    """(dx, dy) in mm."""
    dx = arr.spacing_mm(p["f0"], p["spacing"], p["spacing_mm"])
    if p["spacing_y_mm"] > 0 or p["spacing_y"] > 0:
        dy = arr.spacing_mm(p["f0"], p["spacing_y"], p["spacing_y_mm"])
    else:
        dy = dx * math.sqrt(3) / 2 if int(p["lattice"]) == 1 else dx
    return dx, dy


def positions(p):
    """Element centres (mm), row major."""
    dx, dy = pitches(p)
    return arr.lattice(int(p["nx"]), int(p["ny"]), dx, dy, triangular=int(p["lattice"]) == 1)


def build(ctx):
    p = ctx.params
    out = arr.tile(p["element"], element_values(p), positions(p))
    return out + [ws.anchor("center", point=(0, 0, 0), normal=(0, 0, 1))]


if __name__ == "__main__":
    ws.preview(build)
