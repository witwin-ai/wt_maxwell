"""Microstrip hairpin band-pass filter with N resonators and tapped feeds.

Each resonator is a half-wave line folded into a U ("hairpin"): two arms
along y joined by a short bend. Neighbouring hairpins alternate orientation,
so the arms of adjacent resonators couple along their whole length. Feeds of
width ``w0`` tap the outer arms of the first and last resonators and run to
the board edges, where ``port1`` (normal -x) and ``port2`` (normal +x) sit.

``build`` derives the layout from the Chebyshev (or maximally flat)
prototype g_k (Hong & Lancaster, Microstrip Filters for RF/Microwave
Applications, 2001, sec. 5.3):

- Arms: the centerline of each hairpin is half a guided wavelength at f0
  (Hammerstad-Jensen eps_eff of ``w``), arms = (lambda_g/2 - bend) / 2.
- Gaps: coupling M(i,i+1) = FBW / sqrt(g_i g_i+1). The gap is the spacing at
  which two coupled strips of width ``w`` have voltage coupling M on the
  Garg-Bahl model, times ``gap_scale``. This is the usual first-cut
  estimate; the true hairpin coupling also depends on the bends, so tune
  ``gap_scale`` (or the gaps) against the solver.
- Taps: external Q = g0 g1 / FBW. For a half-wave resonator of impedance Zr
  tapped by Z0 at angle theta from its voltage null (the bend center), the
  slope-parameter argument (Matthaei, Young & Jones 1964, sec. 5.08) gives
  Qe = (pi/2) (Z0/Zr) / sin^2(theta); the tap sits at theta = beta x.

    python hairpin_bpf.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack, line, width

CONFIG = {"unit": "mm", "up": "z", "grid": 0.05e-3}
PARAMS = {
    "n": ws.param(5, integer=True, min=2, max=12, description="number of resonators (filter order)"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "fbw": ws.param(0.1, min=0.005, max=0.5, description="fractional bandwidth, dimensionless"),
    "ripple_db": ws.param(0.1, min=0, max=3, description="passband ripple, dB (0: maximally flat)"),
    "w": ws.param(1.5104, unit="mm", min=0.01, max=20, description="resonator line width"),
    "w0": ws.param(1.5104, unit="mm", min=0.01, max=20, description="feed line width"),
    "arm_spacing": ws.param(2.0, unit="mm", min=0.01, max=50, description="gap between the two arms of one hairpin"),
    "gap_scale": ws.param(1.0, min=0.1, max=10, description="factor on the computed inter-resonator gaps"),
    "feed_length": ws.param(8, unit="mm", min=0.1, max=500, description="feed line length to the board edge"),
    "margin": ws.param(5, unit="mm", min=0.1, max=500, description="board margin above and below the resonators"),
    "h": ws.param(0.8, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="port impedance, ohm"),
    "z_resonator": ws.param(50, min=10, max=150, description="resonator line impedance, ohm"),
    "f0": ws.param(2.4e9, unit="Hz", min=1e6, max=1e12, description="center frequency"),
    "fbw": ws.param(0.1, min=0.005, max=0.5, description="fractional bandwidth, dimensionless"),
    "n": ws.param(5, integer=True, min=2, max=12, description="filter order, count"),
    "ripple_db": ws.param(0.1, min=0, max=3, description="passband ripple, dB"),
    "h": ws.param(0.8, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """Resonator and feed widths; order, f0, FBW and ripple pass through to the build."""
    v = F.spec_values(DESIGN_SPEC, spec)
    return {"w": width(v["z_resonator"], v["h"], v["eps_r"], v["t"]),
            "w0": width(v["z0"], v["h"], v["eps_r"], v["t"]),
            "n": int(round(v["n"])), "f0": v["f0"], "fbw": v["fbw"], "ripple_db": v["ripple_db"],
            "h": v["h"], "t": v["t"], "eps_r": v["eps_r"]}


def plan(p):
    """Arm length, gaps and tap offsets (mm) for the parameters ``p``."""
    n = int(p.n)
    g = F.lowpass_prototype(n, p.ripple_db)
    zr, eps_r_eff = line(p.w, p.h, p.eps_r, p.t)
    z0, _ = line(p.w0, p.h, p.eps_r, p.t)
    lam_g = F.guided_wavelength(p.f0, eps_r_eff) * 1e3
    bend = p.arm_spacing + p.w                     # centerline length of the bend
    arm = (lam_g / 2.0 - bend) / 2.0               # centerline length of each arm
    if arm <= p.w:
        raise ValueError("arm_spacing is too large for a half-wave hairpin at this f0")
    couplings = [p.fbw / math.sqrt(g[i] * g[i + 1]) for i in range(1, n)]
    gaps = []
    for k in couplings:
        try:
            gaps.append(p.gap_scale * F.coupled_spacing(k, p.w, p.h, p.eps_r))
        except ValueError:
            raise ValueError(f"coupling {k:.4g} is outside the coupled-line model range (S = 0.01h..10h); "
                             "change fbw, n or the substrate") from None
    qe = g[0] * g[1] / p.fbw
    s2 = (math.pi / 2.0) * (z0 / zr) / qe
    if s2 >= 1.0:
        raise ValueError(f"external Q {qe:.3g} is too low for a tapped hairpin; lower the bandwidth")
    theta = math.asin(math.sqrt(s2))
    from_center = theta / (2.0 * math.pi) * lam_g  # distance from the bend center along the line
    tap = min(max(from_center - bend / 2.0, p.w0 / 2.0), arm - p.w0 / 2.0)  # along the arm from the bend
    return {"arm": arm, "bend": bend, "gaps": gaps, "couplings": couplings, "qe": qe, "tap": tap,
            "zr": zr, "lambda_g": lam_g}


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0)
    n = int(p.n)
    d = plan(p)
    arm, pitch = d["arm"], p.arm_spacing + p.w     # pitch: arm centerline distance in one hairpin
    # x of each resonator's left arm centerline.
    xs = [0.0]
    for gap in d["gaps"]:
        xs.append(xs[-1] + pitch + p.w + gap)
    width_total = xs[-1] + pitch
    shift = -width_total / 2.0
    y_low, y_high = -arm / 2.0, arm / 2.0          # arm centerline ends (bend centerline at one of them)
    lay = L.Layout(unit="mm")
    taps = []
    for i, x0 in enumerate(xs):
        x0 += shift
        x1 = x0 + pitch
        bend_y, open_y = (y_low, y_high) if i % 2 == 0 else (y_high, y_low)
        lay.add("top", L.path([(x0, open_y), (x0, bend_y), (x1, bend_y), (x1, open_y)], width=p.w,
                              corner="miter", end="flat"))
        lay.anchor(f"resonator{i + 1}", "top", ((x0 + x1) / 2.0, bend_y))
        step = d["tap"] if bend_y < open_y else -d["tap"]
        taps.append((x0, x1, bend_y + step))
    x_left, _, y_in = taps[0]
    _, x_right, y_out = taps[-1]
    left_edge = x_left - p.w / 2.0 - p.feed_length
    right_edge = x_right + p.w / 2.0 + p.feed_length
    lay.add("top", L.path([(left_edge, y_in), (x_left, y_in)], width=p.w0))
    lay.add("top", L.path([(x_right, y_out), (right_edge, y_out)], width=p.w0))
    top = y_high + p.w / 2.0 + p.margin
    lay.outline = L.rect(right_edge - left_edge, 2.0 * top, center=((left_edge + right_edge) / 2.0, 0.0))
    lay.port("port1", "top", (left_edge, y_in), direction=(-1, 0), width=p.w0, reference="bottom")
    lay.port("port2", "top", (right_edge, y_out), direction=(1, 0), width=p.w0, reference="bottom")
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
