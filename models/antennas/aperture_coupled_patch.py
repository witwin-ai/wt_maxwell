"""Aperture-coupled rectangular patch: a microstrip line under the ground couples through a slot.

Geometry (Z-up, mm), bottom to top: the 50 ohm feed line sheet at z = 0 on
the lower face of the feed substrate (0 <= z <= h_feed); the ground sheet
with a rectangular coupling slot (long side along x) in the middle of its
copper; the antenna substrate above it; the patch sheet on top. Patch and
slot are centred on the origin. The feed line runs along +y from the board
edge, crosses under the slot centre and ends in an open stub ``stub`` past
it. Boresight +z (there is a weaker back lobe through the slot);
polarization linear along y.

Bodies: ``feedline``, ``feed_substrate``, ``ground`` (with the slot),
``substrate`` (antenna substrate), ``top`` (patch).

Anchors: ``feed`` (port, on the feed line at the board edge, normal -y) and
``feed_ref`` (on the ground above it); loose ``top`` (patch centre, +z),
``aperture`` (slot centre) and ``ground_bottom`` (origin, -z).

``design(spec)``: patch W and L from the transmission-line model on the
antenna substrate (Balanis eqs. 14-1, 14-2, 14-6, 14-7); feed line width by
Hammerstad (Pozar eq. 3.197). Slot length 0.15 lambda0 (capped at 0.9 W),
slot width a tenth of that, and the open stub 0.22 guided wavelengths: the
starting values of Pozar, "A review of aperture coupled microstrip
antennas" (1996). The coupling is not tuned; adjust slot length and stub in
the solver.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, h_feed/2, h/2).
"""
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e8, max=1e11, description="design frequency (loss conversion, grid)"),
    "W": ws.param(48.37, unit="mm", min=1, max=500, description="patch width (along x)"),
    "L": ws.param(40.47, unit="mm", min=1, max=500, description="patch resonant length (along y)"),
    "slot_l": ws.param(18.35, unit="mm", min=0.5, max=300, description="coupling slot length (along x)"),
    "slot_w": ws.param(1.84, unit="mm", min=0.05, max=50, description="coupling slot width (along y)"),
    "feed_w": ws.param(1.14, unit="mm", min=0.05, max=50, description="feed line width (50 ohm)"),
    "feed_len": ws.param(32.47, unit="mm", min=1, max=500, description="feed line from the board edge to the slot centre"),
    "stub": ws.param(16.14, unit="mm", min=0, max=300, description="open stub past the slot centre"),
    "margin": ws.param(12.24, unit="mm", min=0, max=500, description="board beyond the patch"),
    "h": ws.param(1.575, unit="mm", min=0.05, max=20, description="antenna substrate thickness"),
    "eps_r": ws.param(2.2, min=1, max=100, description="antenna substrate relative permittivity"),
    "tan_delta": ws.param(0.0009, min=0, max=1, description="antenna substrate loss tangent"),
    "h_feed": ws.param(0.508, unit="mm", min=0.05, max=20, description="feed substrate thickness"),
    "eps_r_feed": ws.param(3.55, min=1, max=100, description="feed substrate relative permittivity"),
    "tan_delta_feed": ws.param(0.0027, min=0, max=1, description="feed substrate loss tangent"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="resonant frequency"),
    "eps_r": ws.param(2.2, description="antenna substrate eps_r (RT/duroid 5880)"),
    "h": ws.param(1.575, unit="mm", description="antenna substrate thickness"),
    "tan_delta": ws.param(0.0009, description="antenna substrate loss tangent"),
    "eps_r_feed": ws.param(3.55, description="feed substrate eps_r (RO4003C)"),
    "h_feed": ws.param(0.508, unit="mm", description="feed substrate thickness"),
    "tan_delta_feed": ws.param(0.0027, description="feed substrate loss tangent"),
    "z0": ws.param(50.0, description="feed line impedance (ohm)"),
}

ARRAY_SHARED = ("feed_substrate", "ground", "substrate")


def design(spec=None):
    """PARAMS overrides for an aperture-coupled patch at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    w, length, _ = ac.patch_size(f, s["eps_r"], s["h"])
    lam0 = ac.wavelength_mm(f)
    slot_l = min(0.15 * lam0, 0.9 * w)
    lam_g = ac.microstrip_guided_wavelength(f, s["z0"], s["eps_r_feed"], s["h_feed"])
    out = {k: s[k] for k in ("f0", "eps_r", "h", "tan_delta", "eps_r_feed", "h_feed", "tan_delta_feed")}
    out.update({
        "W": ac.round_to(w), "L": ac.round_to(length),
        "slot_l": ac.round_to(slot_l), "slot_w": ac.round_to(slot_l / 10),
        "feed_w": ac.round_to(ac.microstrip_width(s["z0"], s["eps_r_feed"], s["h_feed"])),
        "stub": ac.round_to(0.22 * lam_g),
        "feed_len": ac.round_to(max(length / 2 + 0.1 * lam0, 0.25 * lam_g)),
        "margin": ac.round_to(max(6 * s["h"], 0.1 * lam0)),
    })
    return out


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, h_feed/2, h/2)."""
    return ac.suggested_grid(p["f0"], p["h_feed"] / 2, p["h"] / 2)


def layout(p):
    """(Layout, LayerStack, extras) of one aperture-coupled patch."""
    t = p["copper"]
    stack = L.LayerStack([
        ("feedline", "conductor", t),
        ("feed_substrate", "dielectric", p["h_feed"], {"eps_r": p["eps_r_feed"], "tan_delta": p["tan_delta_feed"]}),
        ("ground", "ground", t),
        ("substrate", "dielectric", p["h"], {"eps_r": p["eps_r"], "tan_delta": p["tan_delta"]}),
        ("top", "conductor", t),
    ], unit="mm", z0=-t, frequency=p["f0"])
    hw = max(p["W"], p["slot_l"]) / 2 + p["margin"]
    y_top = max(p["L"] / 2, p["stub"]) + p["margin"]
    y_bot = -p["feed_len"]
    lay = L.Layout(unit="mm", outline=L.polygon([(-hw, y_bot), (hw, y_bot), (hw, y_top), (-hw, y_top)]))
    lay.add("top", L.rect(p["W"], p["L"]))
    lay.cut("ground", L.rect(p["slot_l"], p["slot_w"]))
    lay.add("feedline", L.path([(0, y_bot), (0, p["stub"])], width=p["feed_w"]))
    lay.port("feed", "feedline", (0, y_bot), direction=(0, -1), width=p["feed_w"], reference="ground")
    z_ground = p["h_feed"] + t / 2
    z_top = p["h_feed"] + t + p["h"]
    extras = [
        ws.anchor("top", point=(0, 0, z_top), normal=(0, 0, 1)),
        ws.anchor("aperture", point=(0, 0, z_ground), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
