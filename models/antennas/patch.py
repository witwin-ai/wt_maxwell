"""Rectangular microstrip patch antenna with an inset 50 ohm microstrip feed.

Geometry (Z-up, mm): the ground sheet lies in the XY plane at z = 0, the
substrate fills 0 <= z <= h, and the patch and its feed line are a sheet at
z = h. The patch is centred on the origin; the feed line runs along -y from
the bottom radiating edge to the board edge. Boresight is +z; the main
polarization is linear along y (the resonant length L is along y).

Bodies: ``ground`` (PEC sheet), ``substrate`` (lossy dielectric slab), ``top``
(PEC sheet: patch, inset notches and feed line). Copper is 35 um, drawn as
``fill="surface"`` sheets that carry their real thickness.

Anchors: ``feed`` (port, on ``top`` at the board edge, normal -y) and
``feed_ref`` (on the ground below it); loose anchors ``top`` (patch centre,
+z) and ``ground_bottom`` (origin, -z).

``design(spec)`` uses the transmission-line model (Balanis, *Antenna
Theory*, 3rd ed., eqs. 14-1, 14-2, 14-6, 14-7) for W and L, the two-slot
conductance (eqs. 14-12, 14-18a) for the edge resistance, eq. 14-20a for the
inset, and Hammerstad's synthesis (Pozar eq. 3.197) for the 50 ohm line. The
model is good to a few percent: tune L in the solver.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, h/2): two cells
across the substrate.
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e8, max=1e11, description="design frequency (loss conversion, grid)"),
    "W": ws.param(37.23, unit="mm", min=1, max=500, description="patch width (along x)"),
    "L": ws.param(28.81, unit="mm", min=1, max=500, description="patch resonant length (along y)"),
    "inset": ws.param(10.69, unit="mm", min=0, max=250, description="feed inset depth from the radiating edge"),
    "notch_gap": ws.param(1.02, unit="mm", min=0.05, max=20, description="gap each side of the feed line in the inset notch"),
    "feed_w": ws.param(3.06, unit="mm", min=0.05, max=50, description="feed line width (50 ohm)"),
    "feed_len": ws.param(16.76, unit="mm", min=0.5, max=500, description="feed line length from the patch edge to the board edge"),
    "margin": ws.param(9.6, unit="mm", min=0, max=500, description="ground/substrate beyond the patch on the other three sides"),
    "h": ws.param(1.6, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent at f0"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness (sheet thickness)"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(1.6, unit="mm", description="substrate thickness"),
    "tan_delta": ws.param(0.02, description="substrate loss tangent"),
    "z0": ws.param(50.0, description="feed line impedance (ohm)"),
}

# Bodies a planar array merges into one board instead of tiling.
ARRAY_SHARED = ("ground", "substrate")


def design(spec=None):
    """PARAMS overrides (mm) for a patch resonant at spec f0 on the given substrate."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f, er, h = s["f0"], s["eps_r"], s["h"]
    w, length, _ = ac.patch_size(f, er, h)
    feed_w = ac.microstrip_width(s["z0"], er, h)
    lam_g = ac.microstrip_guided_wavelength(f, s["z0"], er, h)
    return {
        "f0": f, "eps_r": er, "h": h, "tan_delta": s["tan_delta"],
        "W": ac.round_to(w), "L": ac.round_to(length),
        "inset": ac.round_to(ac.patch_inset(f, w, length, s["z0"])),
        "feed_w": ac.round_to(feed_w), "feed_len": ac.round_to(lam_g / 4),
        "notch_gap": ac.round_to(max(0.5, feed_w / 3)), "margin": ac.round_to(6 * h),
    }


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, h/2)."""
    return ac.suggested_grid(p["f0"], p["h"] / 2)


def draw_patch(lay, p, center=(0.0, 0.0)):
    """Inset patch with its feed line on ``top``; returns the port point at the line end."""
    cx, cy = center
    bottom = cy - p["L"] / 2
    patch = L.rect(p["W"], p["L"], center=(cx, cy))
    if p["inset"] > 0:
        notch = L.rect(p["feed_w"] + 2 * p["notch_gap"], p["inset"], center=(cx, bottom + p["inset"] / 2))
        patch = L.boolean(patch, notch, "difference")
    lay.add("top", patch)
    end = (cx, bottom - p["feed_len"])
    lay.add("top", L.path([(cx, bottom + p["inset"]), end], width=p["feed_w"]))
    return end


def layout(p):
    """(Layout, LayerStack, extras) of one patch; ``extras`` are bodies/anchors beyond the layers."""
    stack = ac.board_stack(h=p["h"], eps_r=p["eps_r"], tan_delta=p["tan_delta"], f=p["f0"], copper=p["copper"])
    m = p["margin"]
    x0, x1 = -p["W"] / 2 - m, p["W"] / 2 + m
    y0, y1 = -p["L"] / 2 - p["feed_len"], p["L"] / 2 + m
    lay = L.Layout(unit="mm", outline=L.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    end = draw_patch(lay, p)
    lay.port("feed", "top", end, direction=(0, -1), width=p["feed_w"], reference="ground")
    extras = [ws.anchor("top", point=(0, 0, p["h"]), normal=(0, 0, 1)),
              ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1))]
    return lay, stack, extras


def build(ctx):
    p = ctx.params
    lay, stack, extras = layout(p)
    # The patch is centred on the origin, so an edge moves half the size change.
    handles = [ws.handle("W", point=(p["W"] / 2, 0, p["h"]), axis=(1, 0, 0), scale=2),
               ws.handle("L", point=(0, p["L"] / 2, p["h"]), axis=(0, 1, 0), scale=2)]
    return ac.layout_output(lay, stack, extras) + handles


if __name__ == "__main__":
    ws.preview(build)
