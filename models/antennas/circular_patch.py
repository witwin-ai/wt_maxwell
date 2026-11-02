"""Circular microstrip patch antenna (TM11 mode) fed by a 50 ohm coaxial probe.

Geometry (Z-up, mm): ground sheet at z = 0 in the XY plane, substrate
0 <= z <= h (square board), circular patch sheet of radius ``a`` at z = h
centred on the origin. The probe sits at (0, -rho0) and continues below the
ground as a short coax ending in the ``feed`` port at z = -coax_len.
Boresight +z; polarization linear along y (the probe's radial direction).

Bodies: ``ground``, ``substrate``, ``top`` (disc), ``vias`` (probe),
``coax_pin``, ``coax_dielectric``, ``coax_shield``.

Anchors: ``feed`` (port, coax pin end, -z); loose ``top`` (+z) and
``ground_bottom`` (-z).

``design(spec)``: physical radius from Balanis eq. 14-67 (with the fringing
correction of eq. 14-68 for a_e). The probe radius rho0 solves
R(rho0) = R(a_e) J1^2(k rho0) / J1^2(k a_e) = z0 with k = k0 sqrt(eps_r)
(eq. 14-73) and R(a_e) = 1/G_rad from eq. 14-70 (radiation conductance
only; conductor and dielectric losses are left out, so the probe lands a
little too far out on a lossy board).

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, h/2, pin radius,
shield wall).
"""
import math

import numpy as np
import witwin.studio as ws
from witwin.studio import layout as L

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e8, max=1e11, description="design frequency (loss conversion, grid)"),
    "a": ws.param(16.6, unit="mm", min=0.5, max=500, description="patch radius"),
    "rho0": ws.param(3.08, unit="mm", min=0.2, max=500, description="probe distance from the patch centre"),
    "margin": ws.param(9.6, unit="mm", min=0, max=500, description="ground/substrate beyond the patch"),
    "h": ws.param(1.6, unit="mm", min=0.05, max=20, description="substrate thickness"),
    "eps_r": ws.param(4.4, min=1, max=100, description="substrate relative permittivity"),
    "tan_delta": ws.param(0.02, min=0, max=1, description="substrate loss tangent at f0"),
    "copper": ws.param(0.035, unit="mm", min=0.001, max=1, description="copper thickness"),
    "pin_d": ws.param(1.27, unit="mm", min=0.1, max=10, description="probe pin diameter"),
    "coax_d": ws.param(4.25, unit="mm", min=0.3, max=40, description="coax shield inner diameter (ground hole)"),
    "coax_eps_r": ws.param(2.1, min=1, max=20, description="coax fill relative permittivity (PTFE)"),
    "coax_len": ws.param(5.0, unit="mm", min=0.5, max=200, description="coax length below the ground"),
    "shield_wall": ws.param(1.0, unit="mm", min=0.05, max=5, description="coax shield wall thickness"),
    "segments": ws.param(96, integer=True, min=16, max=720, description="polygon sides of the disc"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="TM11 resonant frequency"),
    "eps_r": ws.param(4.4, description="substrate relative permittivity"),
    "h": ws.param(1.6, unit="mm", description="substrate thickness"),
    "tan_delta": ws.param(0.02, description="substrate loss tangent"),
    "z0": ws.param(50.0, description="feed impedance (ohm)"),
}

ARRAY_SHARED = ("ground", "substrate")


def physical_radius(f, eps_r, h):
    """Patch radius (mm), Balanis eq. 14-67 (h and F in cm there; the ratio is unit-free)."""
    big_f = 8.791e9 / (f * math.sqrt(eps_r)) * 10.0  # cm -> mm
    return big_f / math.sqrt(1 + 2 * h / (math.pi * eps_r * big_f) * (math.log(math.pi * big_f / (2 * h)) + 1.7726))


def effective_radius(a, eps_r, h):
    """Fringing-corrected radius a_e (Balanis eq. 14-68)."""
    return a * math.sqrt(1 + 2 * h / (math.pi * a * eps_r) * (math.log(math.pi * a / (2 * h)) + 1.7726))


def edge_resistance(f, a_e):
    """1 / G_rad of the TM11 disc (Balanis eq. 14-70)."""
    k0 = 2 * math.pi / ac.wavelength_mm(f)
    theta = np.linspace(1e-6, math.pi / 2, 801)
    x = k0 * a_e * np.sin(theta)
    j0, j2 = ac.bessel_j(0, x), ac.bessel_j(2, x)
    integrand = ((j0 - j2) ** 2 + np.cos(theta) ** 2 * (j0 + j2) ** 2) * np.sin(theta)
    g_rad = (k0 * a_e) ** 2 / 480.0 * ac._simpson(integrand, theta)
    return 1.0 / g_rad


def probe_radius(f, eps_r, a_e, z0):
    """rho0 where the cavity-model input resistance equals ``z0`` (Balanis eq. 14-73)."""
    k = 2 * math.pi / ac.wavelength_mm(f) * math.sqrt(eps_r)
    r_edge = edge_resistance(f, a_e)
    j1_edge = float(ac.bessel_j(1, k * a_e)) ** 2
    lo, hi = 1e-3 * a_e, a_e  # R rises monotonically from 0 at the centre to r_edge at a_e
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        r = r_edge * float(ac.bessel_j(1, k * mid)) ** 2 / j1_edge
        lo, hi = (mid, hi) if r < z0 else (lo, mid)
    return 0.5 * (lo + hi)


def design(spec=None):
    """PARAMS overrides for a TM11 circular patch resonant at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f, er, h = s["f0"], s["eps_r"], s["h"]
    a = physical_radius(f, er, h)
    a_e = effective_radius(a, er, h)
    return {
        "f0": f, "eps_r": er, "h": h, "tan_delta": s["tan_delta"],
        "a": ac.round_to(a), "rho0": ac.round_to(probe_radius(f, er, a_e, s["z0"])),
        "margin": ac.round_to(6 * h),
        "coax_d": ac.round_to(ac.coax_outer_diameter(s["z0"], 1.27, 2.1)), "pin_d": 1.27, "coax_eps_r": 2.1,
    }


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, h/2, pin radius, shield wall)."""
    return ac.suggested_grid(p["f0"], p["h"] / 2, p["pin_d"] / 2, p["shield_wall"])


def layout(p):
    """(Layout, LayerStack, extras) of one probe-fed circular patch."""
    stack = ac.board_stack(h=p["h"], eps_r=p["eps_r"], tan_delta=p["tan_delta"], f=p["f0"], copper=p["copper"])
    side = 2 * (p["a"] + p["margin"])
    lay = L.Layout(unit="mm", outline=L.rect(side, side))
    lay.add("top", L.circle(p["a"], segments=int(p["segments"])))
    yf = -p["rho0"]
    lay.cut("ground", L.circle(p["coax_d"] / 2, center=(0, yf), segments=32))
    lay.via((0, yf), drill=p["pin_d"], from_layer="ground", to_layer="top")
    extras = ac.coax_feed(p, 0.0, yf) + [
        ws.anchor("top", point=(0, 0, p["h"]), normal=(0, 0, 1)),
        ws.anchor("ground_bottom", point=(0, 0, 0), normal=(0, 0, -1)),
    ]
    return lay, stack, extras


def build(ctx):
    lay, stack, extras = layout(ctx.params)
    return ac.layout_output(lay, stack, extras)


if __name__ == "__main__":
    ws.preview(build)
