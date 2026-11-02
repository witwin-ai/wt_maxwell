"""Stepped-impedance microstrip low-pass filter with N sections.

Alternating low-impedance (wide, ``w_low``) and high-impedance (narrow,
``w_high``) sections between two ``w0`` feed lines, all along x. The first
section is a shunt capacitor (low impedance), as in Pozar's Example 8.6.
Ports sit on the feeds at the board edges, normals out along x.

The section lengths are not parameters: ``build`` derives them from the
low-pass prototype (Pozar sec. 8.6, eqs. 8.82): at the cutoff ``fc`` an
inductor section is ``beta*l = g_k Z0 / Zh`` long and a capacitor section
``beta*l = g_k Zl / Z0``, where Z0, Zl and Zh are the Hammerstad-Jensen
impedances of ``w0``, ``w_low`` and ``w_high`` and beta uses each section's
own effective permittivity. ``g_k`` is maximally flat for ``ripple_db = 0``
and Chebyshev otherwise (Matthaei, Young & Jones 1964, sec. 4.05).
Junction discontinuities are ignored, as in Pozar's design.

The defaults reproduce Pozar's Example 8.6 (fc 2.5 GHz, N = 6, maximally
flat, Z0 = 50, Zl = 20, Zh = 120 ohm, eps_r 4.2, h = 1.58 mm): electrical
lengths 11.8, 33.8, 44.3, 46.1, 32.4, 12.3 degrees.

    python stepped_impedance_lpf.py
"""
import math

import witwin.studio as ws
from witwin.studio import layout as L

from _passives_layout import F, board_stack, line, width

CONFIG = {"unit": "mm", "up": "z", "grid": 0.1e-3}
PARAMS = {
    "n": ws.param(6, integer=True, min=1, max=15, description="number of sections (filter order)"),
    "fc": ws.param(2.5e9, unit="Hz", min=1e6, max=1e12, description="cutoff frequency"),
    "ripple_db": ws.param(0, min=0, max=3, description="passband ripple, dB (0: maximally flat)"),
    "w0": ws.param(3.1061, unit="mm", min=0.01, max=50, description="feed line width (Z0)"),
    "w_low": ws.param(11.2417, unit="mm", min=0.01, max=100, description="low-impedance (capacitor) section width"),
    "w_high": ws.param(0.4045, unit="mm", min=0.01, max=50, description="high-impedance (inductor) section width"),
    "feed_length": ws.param(10, unit="mm", min=0.1, max=500, description="feed line length on each side"),
    "margin": ws.param(5, unit="mm", min=0.1, max=500, description="board margin beside the widest section"),
    "h": ws.param(1.58, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.2, min=1, max=100, description="substrate relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent"),
}

DESIGN_SPEC = {
    "z0": ws.param(50, min=10, max=150, description="system impedance, ohm"),
    "z_low": ws.param(20, min=5, max=100, description="lowest practical line impedance, ohm"),
    "z_high": ws.param(120, min=30, max=200, description="highest practical line impedance, ohm"),
    "fc": ws.param(2.5e9, unit="Hz", min=1e6, max=1e12, description="cutoff frequency"),
    "n": ws.param(6, integer=True, min=1, max=15, description="filter order, count"),
    "ripple_db": ws.param(0, min=0, max=3, description="passband ripple, dB (0: maximally flat)"),
    "h": ws.param(1.58, unit="mm", min=0.01, max=20, description="substrate height"),
    "t": ws.param(0.035, unit="mm", min=0.001, max=0.5, description="copper thickness"),
    "eps_r": ws.param(4.2, min=1, max=100, description="substrate relative permittivity, dimensionless"),
}


def design(spec=None):
    """Widths for Z0, Zl and Zh; order, cutoff and ripple pass through to the build."""
    v = F.spec_values(DESIGN_SPEC, spec)
    out = {name: width(v[z], v["h"], v["eps_r"], v["t"])
           for name, z in (("w0", "z0"), ("w_low", "z_low"), ("w_high", "z_high"))}
    out.update(n=int(round(v["n"])), fc=v["fc"], ripple_db=v["ripple_db"], h=v["h"], t=v["t"], eps_r=v["eps_r"])
    return out


def sections(p):
    """The filter sections: ``[{"kind", "g", "z", "width", "deg", "length"}]`` (length in mm)."""
    n = int(p.n)
    g = F.lowpass_prototype(n, p.ripple_db)
    z0, _ = line(p.w0, p.h, p.eps_r, p.t)
    out = []
    for k in range(1, n + 1):
        capacitor = k % 2 == 1
        w = p.w_low if capacitor else p.w_high
        z, eps_eff = line(w, p.h, p.eps_r, p.t)
        beta_l = g[k] * z / z0 if capacitor else g[k] * z0 / z
        wavelength = F.guided_wavelength(p.fc, eps_eff) * 1e3  # mm
        out.append({"kind": "C" if capacitor else "L", "g": g[k], "z": z, "width": w,
                    "deg": math.degrees(beta_l), "length": beta_l / (2.0 * math.pi) * wavelength})
    return out


def build(ctx):
    p = ctx.params
    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.fc)
    parts = sections(p)
    body = sum(s["length"] for s in parts)
    half = body / 2.0 + p.feed_length
    board_w = max(p.w0, p.w_low, p.w_high) + 2.0 * p.margin
    lay = L.Layout(unit="mm", outline=L.rect(2.0 * half, board_w))
    x = -body / 2.0
    lay.add("top", L.path([(-half, 0.0), (x, 0.0)], width=p.w0))
    for i, s in enumerate(parts, start=1):
        lay.add("top", L.rect(s["length"], s["width"], center=(x + s["length"] / 2.0, 0.0)))
        lay.anchor(f"section{i}", "top", (x + s["length"] / 2.0, 0.0))
        x += s["length"]
    lay.add("top", L.path([(x, 0.0), (half, 0.0)], width=p.w0))
    lay.port("port1", "top", (-half, 0.0), direction=(-1, 0), width=p.w0, reference="bottom")
    lay.port("port2", "top", (half, 0.0), direction=(1, 0), width=p.w0, reference="bottom")
    return lay.to_bodies(stack)


if __name__ == "__main__":
    ws.preview(build)
