"""Closed-form transmission-line formulas shared by the line and passive generators.

Pure Python (``math`` only), SI-free: every length is normalized or in the
caller's unit, impedances in ohms, frequencies in Hz. Each function cites its
source. Accuracy is that of the cited closed form; the generators that use
them say so in their own docstrings.

The passive generators (``models/passives``) load this file by path, so keep
it importable on its own: no Studio, numpy or build123d imports here.
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Mapping, Tuple

C0 = 299_792_458.0          # speed of light in vacuum, m/s
ETA0 = 376.730313668        # free-space wave impedance, ohm
EPS0 = 8.8541878128e-12     # vacuum permittivity, F/m


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def spec_values(defaults: Mapping[str, object], spec: Mapping[str, float] | None) -> Dict[str, float]:
    """Spec values with ``DESIGN_SPEC`` defaults for every missing key.

    ``defaults`` maps names to ``ws.param`` objects (anything with ``.value``)
    or plain numbers. Unknown keys in ``spec`` are refused so a typo does not
    silently fall back to a default.
    """
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(defaults))
    if unknown:
        raise KeyError(f"unknown design spec keys {unknown}; known: {sorted(defaults)}")
    out: Dict[str, float] = {}
    for name, default in defaults.items():
        out[name] = float(spec[name]) if name in spec else float(getattr(default, "value", default))
    return out


def bisect(f: Callable[[float], float], lo: float, hi: float, *, tol: float = 1e-12, iters: int = 200) -> float:
    """Root of a monotonic ``f`` on ``[lo, hi]`` (``f(lo)`` and ``f(hi)`` differ in sign)."""
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if (flo > 0) == (fhi > 0):
        raise ValueError(f"no sign change on [{lo:g}, {hi:g}]: f = {flo:g}, {fhi:g}; the target is out of range")
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
        if hi - lo <= tol * max(1.0, abs(mid)):
            break
    return 0.5 * (lo + hi)


def guided_wavelength(f: float, eps_eff: float) -> float:
    """Guided wavelength in meters for frequency ``f`` (Hz) and effective permittivity."""
    return C0 / (f * math.sqrt(eps_eff))


def loss_conductivity(f: float, eps_r: float, tan_delta: float) -> float:
    """Conductivity (S/m) equivalent to ``tan_delta`` at ``f``: sigma = 2*pi*f*eps0*eps_r*tan_delta."""
    return 2.0 * math.pi * f * EPS0 * eps_r * tan_delta


def dielectric(name: str, eps_r: float, tan_delta: float = 0.0, f: float | None = None) -> Dict[str, object]:
    """Material dict for a dielectric body.

    ``eps_r`` and ``sigma_e`` are Material component fields; ``tan_delta`` is
    kept for readers. ``sigma_e`` is the loss conductivity at ``f`` when ``f``
    is given; a loss tangent alone has no frequency-independent form.
    """
    out: Dict[str, object] = {"name": name, "eps_r": float(eps_r), "tan_delta": float(tan_delta)}
    if f:
        out["sigma_e"] = loss_conductivity(f, eps_r, tan_delta)
    return out


# --------------------------------------------------------------------------
# Microstrip: Hammerstad & Jensen (1980)
# E. Hammerstad, O. Jensen, "Accurate models for microstrip computer-aided
# design", IEEE MTT-S Int. Microwave Symp. Digest, 1980, pp. 407-409.
# Static (quasi-TEM) model, < 0.2 % error in Z0 for 0.01 <= u <= 100,
# eps_r <= 128. Thickness correction from the same paper (as written in the
# Qucs technical documentation, section "Microstrip line").
# --------------------------------------------------------------------------
def _ms_z01(u: float) -> float:
    """Impedance of a microstrip in air, ohm (u = W/h)."""
    f = 6.0 + (2.0 * math.pi - 6.0) * math.exp(-((30.666 / u) ** 0.7528))
    return ETA0 / (2.0 * math.pi) * math.log(f / u + math.sqrt(1.0 + (2.0 / u) ** 2))


def _ms_eps_eff0(u: float, eps_r: float) -> float:
    """Zero-thickness effective permittivity (u = W/h)."""
    a = (1.0 + math.log((u ** 4 + (u / 52.0) ** 2) / (u ** 4 + 0.432)) / 49.0
         + math.log(1.0 + (u / 18.1) ** 3) / 18.7)
    b = 0.564 * ((eps_r - 0.9) / (eps_r + 3.0)) ** 0.053
    return (eps_r + 1.0) / 2.0 + (eps_r - 1.0) / 2.0 * (1.0 + 10.0 / u) ** (-a * b)


def microstrip(w: float, h: float, eps_r: float, t: float = 0.0) -> Tuple[float, float]:
    """``(Z0 ohm, eps_eff)`` of a microstrip of width ``w`` on height ``h``, strip thickness ``t``.

    ``w``, ``h`` and ``t`` share one unit. ``t = 0`` is the zero-thickness model.
    """
    u = w / h
    if t <= 0:
        e = _ms_eps_eff0(u, eps_r)
        return _ms_z01(u) / math.sqrt(e), e
    tn = t / h
    coth2 = 1.0 / math.tanh(math.sqrt(6.517 * u)) ** 2
    du1 = tn / math.pi * math.log(1.0 + 4.0 * math.e / (tn * coth2))
    dur = 0.5 * (1.0 + 1.0 / math.cosh(math.sqrt(max(eps_r - 1.0, 0.0)))) * du1
    u1, ur = u + du1, u + dur
    eps_eff = _ms_eps_eff0(ur, eps_r) * (_ms_z01(u1) / _ms_z01(ur)) ** 2
    return _ms_z01(ur) / math.sqrt(eps_eff), eps_eff


def microstrip_width(z0: float, h: float, eps_r: float, t: float = 0.0) -> float:
    """Strip width for impedance ``z0`` (inverse of ``microstrip`` by bisection, same unit as ``h``).

    The starting bracket u = 0.01..100 covers about 6..230 ohm on FR4.
    """
    return h * bisect(lambda u: microstrip(u * h, h, eps_r, t)[0] - z0, 1e-3, 200.0)


# --------------------------------------------------------------------------
# Stripline (centered strip, zero thickness)
# D. M. Pozar, Microwave Engineering, 4th ed., Wiley 2012, eqs. (3.179)-(3.182)
# (fit to the exact conformal-mapping solution, about 1 % accuracy).
# --------------------------------------------------------------------------
def stripline(w: float, b: float, eps_r: float) -> float:
    """Z0 (ohm) of a zero-thickness strip of width ``w`` centered between grounds ``b`` apart."""
    x = w / b
    we = x if x > 0.35 else x - (0.35 - x) ** 2
    return 30.0 * math.pi / math.sqrt(eps_r) * 1.0 / (we + 0.441)


def stripline_width(z0: float, b: float, eps_r: float) -> float:
    """Strip width for ``z0`` between grounds ``b`` apart (Pozar eq. 3.181)."""
    x = 30.0 * math.pi / (math.sqrt(eps_r) * z0) - 0.441
    wb = x if math.sqrt(eps_r) * z0 < 120.0 else 0.85 - math.sqrt(0.6 - x)
    return wb * b


# --------------------------------------------------------------------------
# Coplanar waveguide: quasi-static conformal mapping
# R. N. Simons, Coplanar Waveguide Circuits, Components, and Systems, Wiley
# 2001: CPW on a substrate of finite height, sec. 2.2.2 (eqs. 2.21-2.25), and
# conductor-backed CPW, sec. 2.4.1 (eqs. 2.40-2.42). Infinite lateral grounds,
# zero metal thickness.
# --------------------------------------------------------------------------
def ellipk(k: float) -> float:
    """Complete elliptic integral of the first kind K(k) (modulus k) by the AGM."""
    if not 0.0 <= k < 1.0:
        raise ValueError(f"modulus must be in [0, 1), got {k}")
    a, b = 1.0, math.sqrt(1.0 - k * k)
    for _ in range(60):
        a, b = 0.5 * (a + b), math.sqrt(a * b)
        if abs(a - b) < 1e-15 * a:
            break
    return math.pi / (2.0 * a)


def _k_ratio(k: float) -> float:
    """K(k) / K(k'), k' = sqrt(1 - k^2).

    For k < 1e-7, k' rounds to 1.0 in floating point; K(k') then uses the
    asymptote ln(4/k) (error below 1e-14 there).
    """
    if k < 1e-7:
        return (math.pi / 2.0) / math.log(4.0 / k)
    return ellipk(k) / ellipk(math.sqrt((1.0 - k) * (1.0 + k)))


def cpw(s: float, gap: float, h: float, eps_r: float, grounded: bool = False) -> Tuple[float, float]:
    """``(Z0 ohm, eps_eff)`` of a CPW: center strip ``s``, slots ``gap``, substrate ``h``.

    ``grounded`` adds a ground plane under the substrate (conductor-backed
    CPW). Without it the substrate's far side is air.

    Capacitances per unit length (Simons): the upper air half
    ``2*eps0*K(k0)/K(k0')``, the substrate side ``2*eps0*(eps_r-1)*K(k1)/K(k1')``
    over the air value (CPW), or ``2*eps0*eps_r*K(k3)/K(k3')`` to the backing
    ground (CBCPW). ``Z0 = 1/(c*sqrt(C*C_air))``.
    """
    k0 = s / (s + 2.0 * gap)
    q0 = _k_ratio(k0)
    if not grounded:
        k1 = math.sinh(math.pi * s / (4.0 * h)) / math.sinh(math.pi * (s + 2.0 * gap) / (4.0 * h))
        eps_eff = 1.0 + (eps_r - 1.0) / 2.0 * _k_ratio(k1) / q0
        return 30.0 * math.pi / math.sqrt(eps_eff) / q0, eps_eff
    k3 = math.tanh(math.pi * s / (4.0 * h)) / math.tanh(math.pi * (s + 2.0 * gap) / (4.0 * h))
    q3 = _k_ratio(k3)
    eps_eff = (q0 + eps_r * q3) / (q0 + q3)
    return 60.0 * math.pi / math.sqrt(eps_eff) / (q0 + q3), eps_eff


def cpw_gap(z0: float, s: float, h: float, eps_r: float, grounded: bool = False) -> float:
    """Slot width that gives ``z0`` for a fixed center strip ``s`` (bisection on the gap)."""
    return bisect(lambda g: cpw(s, g, h, eps_r, grounded)[0] - z0, 1e-4 * s, 50.0 * s)


# --------------------------------------------------------------------------
# Coaxial line (TEM, exact): Z0 = eta0 / (2 pi sqrt(eps_r)) ln(D/d)
# Pozar, Microwave Engineering, 4th ed., Table 2.1 / eq. (2.32).
# --------------------------------------------------------------------------
def coax(d_inner: float, d_outer: float, eps_r: float) -> float:
    """Z0 (ohm) of a coaxial line: inner conductor diameter ``d_inner``, dielectric diameter ``d_outer``."""
    return ETA0 / (2.0 * math.pi * math.sqrt(eps_r)) * math.log(d_outer / d_inner)


def coax_inner(z0: float, d_outer: float, eps_r: float) -> float:
    """Inner conductor diameter for ``z0`` inside a dielectric of diameter ``d_outer``."""
    return d_outer * math.exp(-z0 * 2.0 * math.pi * math.sqrt(eps_r) / ETA0)


# --------------------------------------------------------------------------
# Hollow waveguides
# Pozar, sec. 3.3 (rectangular: fc_mn = c/(2 pi) sqrt((m pi/a)^2 + (n pi/b)^2))
# and sec. 3.4 (circular: fc = p'_11 c / (2 pi a), p'_11 = 1.8412 for TE11,
# p_01 = 2.4049 for TM01, the next mode).
# --------------------------------------------------------------------------
P11_PRIME = 1.841184   # first zero of J1': TE11 of a circular guide
P01 = 2.404826         # first zero of J0: TM01 of a circular guide


def rect_waveguide_cutoff(a: float, b: float, m: int = 1, n: int = 0, eps_r: float = 1.0) -> float:
    """Cutoff frequency (Hz) of the TE/TM_mn mode of an ``a`` x ``b`` guide in meters."""
    return C0 / (2.0 * math.pi * math.sqrt(eps_r)) * math.hypot(m * math.pi / a, n * math.pi / b)


def rect_waveguide_size(f0: float, ratio: float = 1.5) -> Tuple[float, float]:
    """``(a, b)`` in meters with ``f0 = ratio * fc(TE10)`` and ``b = a / 2``.

    ``ratio`` 1.5 sits in the recommended band 1.25..1.9 fc(TE10), below the
    TE20 cutoff (2 fc); WR-90 (22.86 x 10.16 mm) has its 10 GHz center at 1.53.
    """
    a = ratio * C0 / (2.0 * f0)
    return a, a / 2.0


def circular_waveguide_radius(f0: float) -> float:
    """Radius (m) that puts ``f0`` midway between the TE11 and TM01 cutoffs (single-mode band center)."""
    return C0 * 0.5 * (P11_PRIME + P01) / (2.0 * math.pi * f0)


def circular_waveguide_cutoffs(radius: float) -> Tuple[float, float]:
    """``(fc TE11, fc TM01)`` in Hz for a circular guide of ``radius`` meters."""
    return P11_PRIME * C0 / (2.0 * math.pi * radius), P01 * C0 / (2.0 * math.pi * radius)


# --------------------------------------------------------------------------
# Coupled microstrip lines
# Even/odd impedances of a coupled-line section with voltage coupling C:
# Pozar eq. (7.79a, b). Width and spacing: the synthesis of S. Akhtarzad,
# T. R. Rowbotham, P. B. Johns, "The design of coupled microstrip lines",
# IEEE Trans. MTT-23(6), pp. 486-492, 1975 (also T. C. Edwards and M. B.
# Steer, Foundations for Microstrip Circuit Design, 4th ed., 2016). It maps
# the even and odd modes onto single lines of Z0e/2 and Z0o/2. Checked
# against the Garg-Bahl analysis below it misses the odd mode by up to 25 %
# on FR4, so the generators use it only as the starting point of
# ``coupled_microstrip_design``.
# --------------------------------------------------------------------------
def coupled_impedances(z0: float, coupling: float) -> Tuple[float, float]:
    """``(Z0e, Z0o)`` for voltage coupling ``coupling`` (0..1) and system impedance ``z0``."""
    if not 0.0 < coupling < 1.0:
        raise ValueError(f"coupling must be in (0, 1), got {coupling}")
    return (z0 * math.sqrt((1.0 + coupling) / (1.0 - coupling)),
            z0 * math.sqrt((1.0 - coupling) / (1.0 + coupling)))


def coupled_microstrip_synthesis(z0e: float, z0o: float, h: float, eps_r: float) -> Tuple[float, float]:
    """``(W, S)`` of edge-coupled microstrip lines for ``Z0e`` / ``Z0o`` (Akhtarzad et al. 1975)."""
    wse = microstrip_width(z0e / 2.0, 1.0, eps_r)
    wso = microstrip_width(z0o / 2.0, 1.0, eps_r)
    ce, co = math.cosh(math.pi / 2.0 * wse), math.cosh(math.pi / 2.0 * wso)
    s = 2.0 / math.pi * math.acosh((ce + co - 2.0) / (co - ce))
    g = math.cosh(math.pi * s / 2.0)
    d = 0.5 * ((ce - 1.0) + (ce + 1.0) * g)
    w = math.acosh(d) / math.pi - s / 2.0
    if not (w > 0 and s > 0):
        raise ValueError(f"no coupled-line geometry for Z0e={z0e:g}, Z0o={z0o:g} on eps_r={eps_r:g}")
    return w * h, s * h


def coupled_microstrip(w: float, s: float, h: float, eps_r: float) -> Tuple[float, float]:
    """``(Z0e, Z0o)`` of edge-coupled microstrip lines (strip ``w``, spacing ``s``, height ``h``).

    Quasi-static capacitance model of R. Garg and I. J. Bahl, "Characteristics
    of coupled microstriplines", IEEE Trans. MTT-27(7), pp. 700-705, 1979
    (corrections in MTT-28(3), 1980), as given in K. C. Gupta et al.,
    Microstrip Lines and Slotlines, 2nd ed., 1996, sec. 8.3. About 3 %
    accuracy for 0.2 <= W/h <= 2, 0.05 <= S/h <= 2, eps_r >= 1. Zero metal
    thickness. Capacitances are per unit length, divided by eps0.
    """
    def caps(er: float) -> Tuple[float, float]:
        z0, ee = microstrip(w, h, er)
        cp = er * w / h
        # Fringe capacitance of the single line: C = sqrt(eps_eff)/(c Z0), here / eps0.
        cf = 0.5 * (math.sqrt(ee) / (C0 * z0 * EPS0) - cp)
        a = math.exp(-0.1 * math.exp(2.33 - 2.53 * w / h))
        cf2 = cf / (1.0 + a * (h / s) * math.tanh(8.0 * s / h)) * math.sqrt(er / ee)
        k = (s / h) / (s / h + 2.0 * w / h)
        cga = 1.0 / _k_ratio(k)  # K(k')/K(k)
        cgd = (er / math.pi) * math.log(1.0 / math.tanh(math.pi * s / (4.0 * h))) \
            + 0.65 * cf * (0.02 * math.sqrt(er) / (s / h) + 1.0 - er ** -2)
        return cp + cf + cf2, cp + cf + cga + cgd

    ce, co = caps(eps_r)
    ce_air, co_air = caps(1.0)
    z0e = 1.0 / (C0 * EPS0 * math.sqrt(ce * ce_air))
    z0o = 1.0 / (C0 * EPS0 * math.sqrt(co * co_air))
    return z0e, z0o


def coupled_microstrip_design(z0e: float, z0o: float, h: float, eps_r: float) -> Tuple[float, float]:
    """``(W, S)`` for ``Z0e`` / ``Z0o``: Akhtarzad's synthesis refined on the Garg-Bahl model.

    Newton steps in ``(ln W, ln S)`` with a finite-difference Jacobian; falls
    back to the Akhtarzad values if the refinement leaves the model's range.
    """
    w, s = coupled_microstrip_synthesis(z0e, z0o, h, eps_r)
    x = [math.log(w), math.log(s)]
    target = (math.log(z0e), math.log(z0o))

    def resid(v: List[float]) -> Tuple[float, float]:
        ze, zo = coupled_microstrip(math.exp(v[0]), math.exp(v[1]), h, eps_r)
        return math.log(ze) - target[0], math.log(zo) - target[1]

    for _ in range(40):
        r = resid(x)
        if max(abs(r[0]), abs(r[1])) < 1e-9:
            break
        eps = 1e-6
        j = [[0.0, 0.0], [0.0, 0.0]]
        for col in range(2):
            xp = list(x)
            xp[col] += eps
            rp = resid(xp)
            j[0][col] = (rp[0] - r[0]) / eps
            j[1][col] = (rp[1] - r[1]) / eps
        det = j[0][0] * j[1][1] - j[0][1] * j[1][0]
        if det == 0:
            return w, s
        dx0 = (r[0] * j[1][1] - r[1] * j[0][1]) / det
        dx1 = (j[0][0] * r[1] - j[1][0] * r[0]) / det
        step = max(abs(dx0), abs(dx1))
        scale = 1.0 if step < 0.5 else 0.5 / step
        x = [x[0] - scale * dx0, x[1] - scale * dx1]
    r = resid(x)
    if max(abs(r[0]), abs(r[1])) > 1e-6:
        return w, s
    return math.exp(x[0]), math.exp(x[1])


def coupled_spacing(coupling: float, w: float, h: float, eps_r: float) -> float:
    """Spacing that gives voltage coupling ``(Z0e - Z0o)/(Z0e + Z0o)`` for strips of fixed width ``w``.

    Garg-Bahl model, bisection on S in 0.01h..10h.
    """
    def k(s: float) -> float:
        ze, zo = coupled_microstrip(w, s, h, eps_r)
        return (ze - zo) / (ze + zo)

    return bisect(lambda s: k(s) - coupling, 0.01 * h, 10.0 * h, tol=1e-9)


def db_to_voltage_coupling(c_db: float) -> float:
    """Coupling in dB (positive, e.g. 10) to the voltage coupling factor 10^(-C/20)."""
    return 10.0 ** (-abs(c_db) / 20.0)


# --------------------------------------------------------------------------
# Low-pass prototype element values g_0..g_{N+1}
# Butterworth: g_k = 2 sin((2k-1) pi / 2N). Chebyshev: G. Matthaei, L. Young,
# E. M. T. Jones, Microwave Filters, Impedance-Matching Networks, and Coupling
# Structures, 1964, sec. 4.05; the same values as Pozar Tables 8.3 and 8.4.
# --------------------------------------------------------------------------
def lowpass_prototype(n: int, ripple_db: float = 0.0) -> List[float]:
    """``[g0, g1, ..., gN, gN+1]``; ``ripple_db = 0`` gives maximally flat (Butterworth)."""
    if n < 1:
        raise ValueError("filter order must be >= 1")
    g = [1.0]
    if ripple_db <= 0:
        g += [2.0 * math.sin((2 * k - 1) * math.pi / (2 * n)) for k in range(1, n + 1)]
        return g + [1.0]
    beta = math.log(1.0 / math.tanh(ripple_db / 17.37))
    gamma = math.sinh(beta / (2 * n))
    a = [math.sin((2 * k - 1) * math.pi / (2 * n)) for k in range(1, n + 1)]
    b = [gamma ** 2 + math.sin(k * math.pi / n) ** 2 for k in range(1, n + 1)]
    g.append(2.0 * a[0] / gamma)
    for k in range(2, n + 1):
        g.append(4.0 * a[k - 2] * a[k - 1] / (b[k - 2] * g[k - 1]))
    g.append(1.0 if n % 2 else 1.0 / math.tanh(beta / 4.0) ** 2)
    return g
