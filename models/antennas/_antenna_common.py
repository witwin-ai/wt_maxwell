"""Shared formulas and mesh helpers for the antenna model files in this folder.

Not a model file (no ``build``): the generators import it as a sibling module.
All lengths are millimetres unless a name says otherwise; frequencies are Hz.

Formula sources (cited again where each is used):

- Microstrip synthesis and effective permittivity: Hammerstad's equations as
  given in Pozar, *Microwave Engineering*, 4th ed., eqs. 3.195-3.197.
- Rectangular patch: transmission-line model, Balanis, *Antenna Theory*,
  3rd ed., eqs. 14-1, 14-2, 14-6, 14-7 (size), 14-12, 14-18a, 14-20a (input
  resistance and inset).
- Dipole reactance: induced-EMF method, Balanis eq. 8-60b (``X_m``), used to
  find the resonant length of a finite-radius dipole.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np

C0 = 299_792_458.0          # m/s
EPS0 = 8.8541878128e-12     # F/m
ETA0 = 376.730313668        # ohm
EULER_GAMMA = 0.5772156649015329

MODELS_DIR = Path(__file__).resolve().parent


# --------------------------------------------------------------------- basics
def wavelength_mm(f: float, eps: float = 1.0) -> float:
    """Wavelength in mm at ``f`` Hz in a medium of relative permittivity ``eps``."""
    return C0 / f * 1e3 / math.sqrt(eps)


def spec_values(defaults: Mapping[str, Any], spec: Optional[Mapping[str, Any]]) -> Dict[str, float]:
    """``DESIGN_SPEC`` defaults (``ws.param`` values) overridden by ``spec``.

    Unknown keys are refused so a typo ("fo") does not silently fall back to
    the default.
    """
    spec = dict(spec or {})
    unknown = set(spec) - set(defaults)
    if unknown:
        raise ValueError(f"unknown design spec keys {sorted(unknown)}; known: {sorted(defaults)}")
    out = {}
    for key, value in defaults.items():
        raw = spec.get(key, getattr(value, "value", value))
        out[key] = float(raw)
    return out


def suggested_grid(f: float, *features: float) -> float:
    """Solver grid step in mm: lambda0/20 at ``f``, or the smallest feature if that is finer.

    Features are lengths the solver must resolve with at least one cell
    (substrate thickness, wire radius, slot width). The geometry validator
    flags a solid thinner than half a cell as an error, so a step no larger
    than the thinnest solid always passes it.
    """
    values = [wavelength_mm(f) / 20.0] + [float(v) for v in features if v and v > 0]
    return min(values)


def round_to(value: float, step: float = 0.01) -> float:
    """``value`` rounded to ``step`` (dimensions to 10 um keep the PARAMS readable)."""
    return round(round(value / step) * step, 6)


def sigma_from_tan_delta(eps_r: float, tan_delta: float, f: float) -> float:
    """Conductivity (S/m) that gives loss tangent ``tan_delta`` at ``f`` Hz: sigma = 2 pi f eps0 eps_r tan_delta."""
    return 2.0 * math.pi * f * EPS0 * eps_r * tan_delta


def dielectric(eps_r: float, tan_delta: float = 0.0, f: Optional[float] = None) -> Dict[str, Any]:
    """Material dict for a lossy dielectric, the form ``witwin.studio.layout`` writes.

    The loss tangent becomes a conductivity at ``f`` (not an imaginary
    permittivity, whose sign convention differs between solvers).
    """
    sigma = sigma_from_tan_delta(eps_r, tan_delta, f) if (f and tan_delta) else 0.0
    return {"eps_r": float(eps_r), "sigma_e": float(sigma)}


# ------------------------------------------------------------ special functions
def _simpson(y: np.ndarray, x: np.ndarray) -> float:
    """Composite Simpson rule on an odd number of equally spaced samples."""
    h = (x[-1] - x[0]) / (len(x) - 1)
    return float(h / 3.0 * (y[0] + y[-1] + 4.0 * y[1:-1:2].sum() + 2.0 * y[2:-1:2].sum()))


def bessel_j(n: int, x: Any) -> np.ndarray:
    """Bessel J_n(x) from its integral form (1/pi) int_0^pi cos(n t - x sin t) dt.

    Accurate to ~1e-10 for |x| < 50 with 401 samples; enough for the antenna
    formulas here (scipy is not a dependency of the model files).
    """
    x = np.asarray(x, dtype=float)
    t = np.linspace(0.0, math.pi, 401)
    vals = np.cos(n * t[None, :] - x.reshape(-1, 1) * np.sin(t)[None, :])
    h = math.pi / 400
    w = np.ones_like(t)
    w[1:-1:2], w[2:-1:2] = 4.0, 2.0
    out = (vals * w).sum(axis=1) * h / 3.0 / math.pi
    return out.reshape(x.shape)


def sine_integral(x: float) -> float:
    """Si(x) = int_0^x sin(t)/t dt."""
    if x == 0:
        return 0.0
    t = np.linspace(0.0, x, 4001)
    y = np.sinc(t / math.pi)
    return _simpson(y, t)


def cosine_integral(x: float) -> float:
    """Ci(x) = gamma + ln x + int_0^x (cos t - 1)/t dt, x > 0."""
    t = np.linspace(0.0, x, 4001)
    y = np.empty_like(t)
    y[0] = 0.0
    y[1:] = (np.cos(t[1:]) - 1.0) / t[1:]
    return EULER_GAMMA + math.log(x) + _simpson(y, t)


# ------------------------------------------------------------------ microstrip
def microstrip_eps_eff(w: float, h: float, eps_r: float) -> float:
    """Effective permittivity of a microstrip line (Pozar eq. 3.195)."""
    return (eps_r + 1) / 2 + (eps_r - 1) / 2 / math.sqrt(1 + 12 * h / w)


def microstrip_width(z0: float, eps_r: float, h: float) -> float:
    """Width (unit of ``h``) of a microstrip line of impedance ``z0`` (Pozar eq. 3.197)."""
    a = z0 / 60.0 * math.sqrt((eps_r + 1) / 2) + (eps_r - 1) / (eps_r + 1) * (0.23 + 0.11 / eps_r)
    ratio = 8 * math.exp(a) / (math.exp(2 * a) - 2)
    if ratio > 2:
        b = 377 * math.pi / (2 * z0 * math.sqrt(eps_r))
        ratio = 2 / math.pi * (b - 1 - math.log(2 * b - 1)
                               + (eps_r - 1) / (2 * eps_r) * (math.log(b - 1) + 0.39 - 0.61 / eps_r))
    return ratio * h


def microstrip_guided_wavelength(f: float, z0: float, eps_r: float, h: float) -> float:
    """Guided wavelength (mm) of a ``z0`` microstrip line at ``f``."""
    w = microstrip_width(z0, eps_r, h)
    return wavelength_mm(f, microstrip_eps_eff(w, h, eps_r))


def coax_outer_diameter(z0: float, inner_d: float, eps_r: float) -> float:
    """Inner diameter of a coax shield for impedance ``z0``: Z0 = 60/sqrt(eps_r) ln(D/d)."""
    return inner_d * math.exp(z0 * math.sqrt(eps_r) / 60.0)


# ----------------------------------------------------------------- patch (TLM)
def patch_size(f: float, eps_r: float, h: float) -> Tuple[float, float, float]:
    """(W, L, eps_eff) in mm of a rectangular patch resonant at ``f`` (Balanis 14-6, 14-1, 14-2, 14-7)."""
    lam0 = wavelength_mm(f)
    w = lam0 / 2 * math.sqrt(2 / (eps_r + 1))
    eps_eff = (eps_r + 1) / 2 + (eps_r - 1) / 2 / math.sqrt(1 + 12 * h / w)
    dl = 0.412 * h * ((eps_eff + 0.3) * (w / h + 0.264)) / ((eps_eff - 0.258) * (w / h + 0.8))
    length = lam0 / (2 * math.sqrt(eps_eff)) - 2 * dl
    return w, length, eps_eff


def patch_edge_resistance(f: float, w: float, length: float) -> float:
    """Resonant input resistance (ohm) at the radiating edge, 1 / (2 (G1 + G12)).

    G1 from Balanis eq. 14-12 (slot conductance, integral form), G12 from
    eq. 14-18a (mutual conductance of the two slots).
    """
    k0 = 2 * math.pi / wavelength_mm(f)
    theta = np.linspace(1e-6, math.pi - 1e-6, 2001)
    c, s = np.cos(theta), np.sin(theta)
    core = np.sin(k0 * w / 2 * c) ** 2 / c ** 2 * s ** 3
    g1 = _simpson(core, theta) / (120 * math.pi ** 2)
    g12 = _simpson(core * bessel_j(0, k0 * length * s), theta) / (120 * math.pi ** 2)
    return 1.0 / (2.0 * (g1 + g12))


def patch_inset(f: float, w: float, length: float, z0: float = 50.0) -> float:
    """Inset depth y0 (mm, from the radiating edge) for ``z0``: R(y0) = R_edge cos^2(pi y0 / L) (Balanis 14-20a)."""
    r_edge = patch_edge_resistance(f, w, length)
    return length / math.pi * math.acos(math.sqrt(min(1.0, z0 / r_edge)))


# --------------------------------------------------------------- dipole (EMF)
def dipole_reactance(length: float, radius: float, lam: float) -> float:
    """Reactance X_m (ohm, referred to the current maximum) of a dipole: Balanis eq. 8-60b."""
    k = 2 * math.pi / lam
    kl = k * length
    return ETA0 / (4 * math.pi) * (
        2 * sine_integral(kl)
        + math.cos(kl) * (2 * sine_integral(kl) - sine_integral(2 * kl))
        - math.sin(kl) * (2 * cosine_integral(kl) - cosine_integral(2 * kl)
                          - cosine_integral(2 * k * radius ** 2 / length)))


def dipole_resonant_length(f: float, radius: float) -> float:
    """Total length (mm) of a dipole of wire ``radius`` (mm) whose reactance is zero near lambda/2.

    Induced-EMF method (Balanis eq. 8-60b); about 0.47-0.49 lambda for the
    radii used here. A flat strip of width w acts like a wire of radius w/4
    (equivalent radius of a thin strip, Balanis ch. 9).
    """
    lam = wavelength_mm(f)
    lo, hi = 0.40 * lam, 0.50 * lam
    x_lo = dipole_reactance(lo, radius, lam)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        x_mid = dipole_reactance(mid, radius, lam)
        if (x_mid < 0) == (x_lo < 0):
            lo, x_lo = mid, x_mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------- waveguides
# EIA rectangular waveguides: (name, a mm, b mm, recommended band low, high in Hz).
RECT_WAVEGUIDES = (
    ("WR-430", 109.22, 54.61, 1.70e9, 2.60e9),
    ("WR-284", 72.14, 34.04, 2.60e9, 3.95e9),
    ("WR-187", 47.55, 22.15, 3.95e9, 5.85e9),
    ("WR-137", 34.85, 15.80, 5.85e9, 8.20e9),
    ("WR-90", 22.86, 10.16, 8.20e9, 12.40e9),
    ("WR-62", 15.80, 7.90, 12.40e9, 18.00e9),
    ("WR-42", 10.67, 4.32, 18.00e9, 26.50e9),
    ("WR-28", 7.11, 3.56, 26.50e9, 40.00e9),
    ("WR-19", 4.78, 2.39, 40.00e9, 60.00e9),
    ("WR-12", 3.10, 1.55, 60.00e9, 90.00e9),
)


def rect_waveguide_for(f: float) -> Tuple[str, float, float]:
    """The EIA waveguide whose recommended band contains ``f``, else one sized as a = 0.7 lambda0."""
    for name, a, b, low, high in RECT_WAVEGUIDES:
        if low <= f <= high:
            return name, a, b
    a = 0.7 * wavelength_mm(f)
    return "custom", a, a / 2


# TE11 and TM01 cutoffs of a circular guide: x'11 = 1.8412, x01 = 2.4048.
def circular_waveguide_radius(f: float, ratio: float = 1.2) -> float:
    """Radius (mm) of a circular guide whose TE11 cutoff is f / ``ratio``.

    ``ratio`` 1.2 keeps f between TE11 (1.0) and TM01 (1.306) cutoff, so
    only TE11 propagates.
    """
    return 1.8412 * wavelength_mm(f) * ratio / (2 * math.pi)


# ----------------------------------------------------------------- meshes
Mesh = Tuple[np.ndarray, np.ndarray]


def merge(meshes: Iterable[Mesh]) -> Mesh:
    """Concatenate meshes into one (vertices, faces); shells stay separate."""
    verts, faces, offset = [], [], 0
    for v, f in meshes:
        v = np.asarray(v, dtype=float)
        verts.append(v)
        faces.append(np.asarray(f, dtype=np.int64) + offset)
        offset += len(v)
    return np.vstack(verts), np.vstack(faces)


def translate(mesh: Mesh, offset: Sequence[float]) -> Mesh:
    v, f = mesh
    return np.asarray(v, dtype=float) + np.asarray(offset, dtype=float), f


def cylinder(p0: Sequence[float], p1: Sequence[float], radius: float, sections: int = 16) -> Mesh:
    """Closed cylinder between two points (trimesh)."""
    import trimesh

    m = trimesh.creation.cylinder(radius=radius, segment=np.array([p0, p1], dtype=float), sections=sections)
    return np.asarray(m.vertices), np.asarray(m.faces)


def box(lo: Sequence[float], hi: Sequence[float]) -> Mesh:
    """Closed axis-aligned box from its two corners."""
    import trimesh

    lo, hi = np.asarray(lo, dtype=float), np.asarray(hi, dtype=float)
    m = trimesh.creation.box(extents=hi - lo)
    return np.asarray(m.vertices) + (lo + hi) / 2, np.asarray(m.faces)


def union(meshes: Sequence[Mesh]) -> Mesh:
    """Boolean union of closed meshes (manifold3d through trimesh); one watertight solid."""
    import trimesh

    parts = [trimesh.Trimesh(vertices=v, faces=f, process=True) for v, f in meshes]
    out = trimesh.boolean.union(parts, engine="manifold")
    return np.asarray(out.vertices), np.asarray(out.faces)


def quad(p0: Sequence[float], p1: Sequence[float], p2: Sequence[float], p3: Sequence[float]) -> Mesh:
    """One planar quad sheet (two triangles), corners in order."""
    v = np.array([p0, p1, p2, p3], dtype=float)
    return v, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)


def polygon_sheet(shape: Any, z: float) -> Mesh:
    """A flat sheet at height ``z`` from a shapely (Multi)Polygon, triangulated with holes.

    Uses the same constrained triangulation the layout library uses (via a
    one-layer stack), so holes and islands stay exact.
    """
    from witwin.studio import layout as L

    # A lone conductor layer has no dielectric neighbour, so its sheet sits at
    # mid-thickness: put the layer around z.
    t = 1e-3
    stack = L.LayerStack([("sheet", "conductor", t)], unit="mm", z0=z - t / 2)
    lay = L.Layout(unit="mm")
    lay.add("sheet", shape)
    (body,) = lay.to_bodies(stack, surface_below=1.0)
    return np.asarray(body.mesh.vertices) * 1e3, np.asarray(body.mesh.faces)


def rotate_mesh(mesh: Mesh, matrix: Sequence[Sequence[float]]) -> Mesh:
    v, f = mesh
    return np.asarray(v, dtype=float) @ np.asarray(matrix, dtype=float).T, f


# Rotation that maps the layout XY plane onto the XZ plane (y -> z).
XY_TO_XZ = ((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0))


def board_stack(*, h: float, eps_r: float, tan_delta: float, f: float, copper: float = 0.035,
                ground: bool = True):
    """Two-layer board: ``ground`` (bottom), ``substrate``, ``top``; the ground sheet sits at z = 0.

    ``z0 = -copper`` puts the bottom copper's sheet (on the substrate's lower
    face) at z = 0, so the substrate spans 0..h and the top sheet is at z = h.
    """
    from witwin.studio import layout as L

    layers = []
    if ground:
        layers.append(("ground", "ground", copper))
    layers += [
        ("substrate", "dielectric", h, {"eps_r": eps_r, "tan_delta": tan_delta}),
        ("top", "conductor", copper),
    ]
    return L.LayerStack(layers, unit="mm", z0=-copper if ground else 0.0, frequency=f)


def coax_feed(p: Mapping[str, float], x: float, y: float) -> List[Any]:
    """Coax below the ground at (x, y): ``coax_pin``, ``coax_dielectric``, ``coax_shield``.

    Reads ``pin_d``, ``coax_d`` (shield inner diameter), ``coax_eps_r``,
    ``coax_len`` and ``shield_wall`` from ``p``. The line runs from
    z = -coax_len up to the ground at z = 0; the ``feed`` port anchor sits on
    the pin's lower end, normal -z.
    """
    import trimesh
    import witwin.studio as ws

    z0 = -p["coax_len"]
    seg = [[x, y, z0], [x, y, 0.0]]
    r_pin, r_sh = p["pin_d"] / 2, p["coax_d"] / 2
    fill = trimesh.creation.annulus(r_min=r_pin, r_max=r_sh, segment=seg, sections=32)
    shield = trimesh.creation.annulus(r_min=r_sh, r_max=r_sh + p["shield_wall"], segment=seg, sections=32)
    return [
        ws.Body(cylinder(seg[0], seg[1], r_pin, sections=16), name="coax_pin", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(x, y, z0), normal=(0, 0, -1), kind="port")]),
        ws.Body(fill, name="coax_dielectric", material=dielectric(p["coax_eps_r"]), role="dielectric"),
        ws.Body(shield, name="coax_shield", material="PEC", role="conductor"),
    ]


def layout_output(lay: Any, stack: Any, extras: Sequence[Any] = ()) -> List[Any]:
    """``build`` output for a layout-based generator: the layer bodies plus extra bodies/anchors."""
    return list(lay.to_bodies(stack)) + list(extras)
