"""Uniform linear array along x of any single-element antenna generator in this folder.

Geometry (Z-up, mm): ``n`` copies of the element chosen by ``element`` (code
table below), translated to x_i = (i - (n-1)/2) d, y = 0, with the element's
own orientation (patches face +z, dipoles stand along z, horns open
towards +z, and so on). The pitch d is ``spacing_mm`` when it is above
zero, else ``spacing`` free-space wavelengths at f0. With ``use_design``
= 1 each element takes its ``design()`` dimensions for f0 (band elements:
their default band ratio centred on f0); with 0, its PARAMS defaults.

Planar elements (patches, IFA, spiral, Vivaldi) share one board: one
substrate slab and one ground with every element's holes. Ground planes of
3D elements (monopole, PIFA, helix) merge into one rectangle.

Feed: by default every element keeps its own port ``feed_<i>``. With
``feed_network`` = 1 (inset patch, ``element`` 0, n a power of two) a
corporate microstrip tree joins the patches into one ``feed`` port at the
board edge: pairs of 50 ohm lines meet in 25 ohm T-junctions, each followed
by a quarter-wave 35.4 ohm transformer back to 50 ohm (widths by Hammerstad,
Pozar eq. 3.197; lambda_g/4 at f0). The tree is symmetric, so the
elements are fed in phase with equal amplitude. It is computed, not
EM-tuned: T-junction and bend parasitics and mutual coupling are not
compensated.

Element codes: 0 = patch, 1 = patch_probe, 2 = circular_patch,
3 = aperture_coupled_patch, 4 = dipole, 5 = monopole, 6 = pifa, 7 = ifa,
8 = yagi, 9 = lpda, 10 = helix, 11 = spiral, 12 = pyramidal_horn,
13 = conical_horn, 14 = corrugated_horn, 15 = vivaldi, 16 = slot,
17 = reflector.

Bodies: the element's bodies with suffix ``_<i>`` (shared board layers keep
their names). Anchors: element anchors with suffix ``_<i>``, ports
``feed_<i>`` (or ``feed`` with the network), loose ``center``.

``design(spec)``: copies f0, element, n and spacing (default lambda0/2).

Validation grid: the element's ``suggested_grid``.
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac
import _array_common as arr

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "element": ws.param(0, integer=True, min=0, max=len(arr.ELEMENTS) - 1, description="element code: " + arr.ELEMENT_HELP),
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e12, description="array design frequency"),
    "n": ws.param(4, integer=True, min=1, max=256, description="number of elements"),
    "spacing": ws.param(0.5, min=0.01, max=100, description="element pitch in free-space wavelengths at f0"),
    "spacing_mm": ws.param(0, unit="mm", min=0, max=1e6, description="element pitch in mm; 0 = use spacing"),
    "use_design": ws.param(1, integer=True, min=0, max=1, description="1 = element design() at f0, 0 = element defaults"),
    "feed_network": ws.param(0, integer=True, min=0, max=1, description="1 = corporate microstrip feed (patch, n = 2^k)"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="array design frequency"),
    "element": ws.param(0, description="element code"),
    "n": ws.param(4, description="number of elements"),
    "spacing": ws.param(0.5, description="pitch in wavelengths"),
}


def design(spec=None):
    """PARAMS overrides for the array (the element dimensions come from its own design())."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    return {"f0": s["f0"], "element": int(s["element"]), "n": int(s["n"]), "spacing": s["spacing"],
            "spacing_mm": 0, "use_design": 1}


def _element_overrides(p):
    if int(p["feed_network"]) and int(p["element"]) == arr.element_code("patch"):
        base = arr.element_values(p["element"], p["f0"], bool(p["use_design"]))
        lam_g = ac.microstrip_guided_wavelength(p["f0"], 50.0, base["eps_r"], base["h"])
        return {"feed_len": ac.round_to(0.1 * lam_g)}
    return {}


def element_values(p):
    """Resolved element parameters (mm) for this array."""
    return arr.element_values(p["element"], p["f0"], bool(p["use_design"]), _element_overrides(p))


def suggested_grid(p):
    """Grid step in mm: the element's suggested grid."""
    ns = arr.element_namespace(p["element"])
    return ns["suggested_grid"](element_values(p))


def positions(p):
    """Element centres (mm) along x."""
    d = arr.spacing_mm(p["f0"], p["spacing"], p["spacing_mm"])
    return arr.lattice(int(p["n"]), 1, d, d)


def _corporate(p, values, pos):
    """Board with all patches and the corporate tree; one ``feed`` port."""
    ns = arr.element_namespace(p["element"])
    el_lay, _, _ = ns["layout"](values)
    px, py = el_lay.ports["feed"].point
    er, h, f = values["eps_r"], values["h"], p["f0"]
    w50 = values["feed_w"]
    w35 = ac.microstrip_width(50 / 2 ** 0.5, er, h)
    quarter = ac.microstrip_guided_wavelength(f, 50 / 2 ** 0.5, er, h) / 4
    lam_g = ac.microstrip_guided_wavelength(f, 50.0, er, h)
    drop, tail = max(3 * w35, 0.05 * lam_g), 0.1 * lam_g
    levels = int(p["n"]).bit_length() - 1
    ends = [(x + px, y + py) for x, y in pos]
    y_end = py - levels * (drop + quarter) - tail
    xs = [x for x, _ in ends]
    margin = values["margin"]
    extra = L.polygon([(min(xs) - margin, y_end), (max(xs) + margin, y_end), (max(xs) + margin, py),
                       (min(xs) - margin, py)])
    lay, stack, extras = arr.tile_layout(ns, values, pos, ports=False, extra_outline=extra)
    root = arr.corporate_feed(lay, ends, w50=w50, w35=w35, quarter35=quarter, drop=drop, tail=tail)
    lay.port("feed", "top", root, direction=(0, -1), width=w50, reference="ground")
    return ac.layout_output(lay, stack, extras)


def build(ctx):
    p = ctx.params
    values = element_values(p)
    pos = positions(p)
    if int(p["feed_network"]):
        if int(p["element"]) != arr.element_code("patch"):
            raise ValueError("feed_network = 1 needs element 0 (inset-fed patch)")
        out = _corporate(p, values, pos)
    else:
        out = arr.tile(p["element"], values, pos)
    return out + [ws.anchor("center", point=(0, 0, 0), normal=(0, 0, 1))]


if __name__ == "__main__":
    ws.preview(build)
