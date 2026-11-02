"""Log-periodic dipole array (LPDA) on a twin boom, Carrel's design, fed at the short end.

Geometry (Z-up, mm): the dipole elements are wires parallel to z, centred on
z = 0, standing along the x axis from the longest (x = 0) to the shortest
(largest x). Two square booms run along x at y = +-(boom_gap + boom_w)/2;
each element has one half on each boom, and the halves swap booms from one
element to the next (the transposed feed line). The ``feed`` port bridges
the boom gap at the shortest element. Beam (end-fire) towards +x, the
apex; polarization linear along z.

Bodies: ``lpda`` (both booms with their element halves; two solids that do
not touch).

Anchors: ``feed`` (port between the booms at the front, normal +y, on
``lpda``); loose ``front`` and ``back`` on the axis.

The element count and dimensions come from (f_low, f_high, tau, sigma) by
Carrel's procedure (Balanis, *Antenna Theory*, 3rd ed., section 11.4.2):
alpha = atan((1 - tau)/(4 sigma)), B_ar = 1.1 + 7.7 (1 - tau)^2 cot(alpha),
B_s = (f_high/f_low) B_ar, N = 1 + ln(B_s)/ln(1/tau), L_1 = lambda_max/2,
L_(n+1) = tau L_n, spacing d_n = 2 sigma L_n. ``design(spec)`` picks the
optimum sigma = 0.243 tau - 0.051 for the given tau. The rear short-circuit
stub and element-diameter scaling are not modelled.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f_high, wire radius,
boom gap).
"""
import math

import witwin.studio as ws

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f_low": ws.param(0.5e9, unit="Hz", min=1e6, max=1e11, description="lowest operating frequency"),
    "f_high": ws.param(2.0e9, unit="Hz", min=1e6, max=1e11, description="highest operating frequency"),
    "tau": ws.param(0.88, min=0.7, max=0.98, description="scale factor between neighbouring elements"),
    "sigma": ws.param(0.1628, min=0.03, max=0.25, description="relative spacing d_n / (2 L_n)"),
    "wire_d": ws.param(1.5, unit="mm", min=0.01, max=1000, description="element wire diameter"),
    "boom_w": ws.param(3, unit="mm", min=0.1, max=1000, description="square boom side"),
    "boom_gap": ws.param(3.0, unit="mm", min=0.05, max=1000, description="clear gap between the two booms"),
    "stub": ws.param(11.99, unit="mm", min=0, max=1e4, description="boom length behind the longest element"),
    "sections": ws.param(12, integer=True, min=6, max=64, description="sides of the wire cross-section"),
}

DESIGN_SPEC = {
    "f_low": ws.param(0.5e9, unit="Hz", description="lowest operating frequency"),
    "f_high": ws.param(2.0e9, unit="Hz", description="highest operating frequency"),
    "tau": ws.param(0.88, description="scale factor (Carrel: 0.88 gives about 9 dBi with optimum sigma)"),
}


def elements(p):
    """[(x, length)] of the elements, longest first, from Carrel's procedure."""
    tau, sigma = p["tau"], p["sigma"]
    if p["f_high"] <= p["f_low"]:
        raise ValueError("f_high must exceed f_low")
    alpha = math.atan((1 - tau) / (4 * sigma))
    b_ar = 1.1 + 7.7 * (1 - tau) ** 2 / math.tan(alpha)
    b_s = p["f_high"] / p["f_low"] * b_ar
    n = int(math.ceil(1 + math.log(b_s) / math.log(1 / tau)))
    length = ac.wavelength_mm(p["f_low"]) / 2
    x, out = 0.0, []
    for _ in range(n):
        out.append((x, length))
        x += 2 * sigma * length
        length *= tau
    return out


def design(spec=None):
    """PARAMS overrides: tau as given, optimum sigma, booms scaled to the shortest element."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    tau = s["tau"]
    sigma = 0.243 * tau - 0.051
    lam_min = ac.wavelength_mm(s["f_high"])
    d = round(max(0.01 * lam_min, 0.2), 2)
    return {"f_low": s["f_low"], "f_high": s["f_high"], "tau": tau, "sigma": round(sigma, 4),
            "wire_d": d, "boom_w": round(2 * d, 2), "boom_gap": round(max(d, 0.02 * lam_min), 2),
            "stub": ac.round_to(0.02 * ac.wavelength_mm(s["f_low"]))}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f_high, wire radius, boom gap)."""
    return ac.suggested_grid(p["f_high"], p["wire_d"] / 2, p["boom_gap"])


def build(ctx):
    p = ctx.params
    elems = elements(p)
    r, bw, sec = p["wire_d"] / 2, p["boom_w"], int(p["sections"])
    yb = (p["boom_gap"] + bw) / 2
    x0, x1 = -p["stub"] - bw / 2, elems[-1][0] + bw / 2
    solids = []
    for side, y in ((0, yb), (1, -yb)):
        parts = [ac.box((x0, y - bw / 2, -bw / 2), (x1, y + bw / 2, bw / 2))]
        for i, (x, length) in enumerate(elems):
            up = (i + side) % 2 == 0  # halves swap booms from one element to the next
            tip = length / 2 if up else -length / 2
            parts.append(ac.cylinder((x, y, 0.0), (x, y, tip), r, sec))
        solids.append(ac.union(parts))
    x_front = elems[-1][0]
    return [
        ws.Body(ac.merge(solids), name="lpda", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(x_front, 0, 0), normal=(0, 1, 0), kind="port")]),
        ws.anchor("front", point=(x1, 0, 0), normal=(1, 0, 0)),
        ws.anchor("back", point=(x0, 0, 0), normal=(-1, 0, 0)),
    ]


if __name__ == "__main__":
    ws.preview(build)
