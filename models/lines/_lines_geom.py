"""Geometry helpers shared by the line generators: board stacks and hollow metal guides.

Every function works in the model unit (mm for these generators). Layer
stacks come from ``witwin.studio.layout``; hollow guides use build123d.
The module name carries the folder prefix so it never collides with a helper
of another generator folder when several models load in one process.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence, Tuple

import _lines_formulas as F

PEC = "PEC"


def substrate_material(eps_r: float, tan_delta: float, f0_ghz: Optional[float] = None,
                       name: str = "substrate") -> Dict[str, object]:
    """Material dict of a board dielectric; ``sigma_e`` from ``tan_delta`` at ``f0_ghz`` (GHz)."""
    return F.dielectric(name, eps_r, tan_delta, None if not f0_ghz else f0_ghz * 1e9)


def board_stack(h: float, t: float, eps_r: float, tan_delta: float, f0_ghz: Optional[float] = None,
                *, ground: bool = True, unit: str = "mm"):
    """Two-layer board: ``bottom`` ground (when ``ground``), ``core`` dielectric, ``top`` copper.

    Copper thinner than 100 um becomes a ``fill="surface"`` sheet carrying
    its real thickness (layout surface-fill rule).
    """
    from witwin.studio import layout as L

    layers = []
    if ground:
        layers.append(("bottom", "ground", t, {"material": PEC}))
    layers.append(("core", "dielectric", h, {"material": substrate_material(eps_r, tan_delta, f0_ghz)}))
    layers.append(("top", "conductor", t, {"material": PEC}))
    return L.LayerStack(layers, unit=unit, z0=-t if ground else 0.0)


# --------------------------------------------------------------------------
# build123d hollow guides. The metal is the outer solid minus the air; the
# air runs one wall thickness past every opening so no cut face coincides
# with an end face (cad-modeling skill, pitfall 3).
# --------------------------------------------------------------------------
def rect_profile(origin: Sequence[float], direction: Sequence[float], across: Sequence[float],
                 width: float, height: float):
    """A ``width`` x ``height`` rectangle face centered on ``origin``, normal ``direction``.

    ``width`` runs along ``across``; ``height`` along ``direction x across``.
    """
    from build123d import Plane, Rectangle

    plane = Plane(origin=tuple(origin), x_dir=tuple(across), z_dir=tuple(direction))
    return plane * Rectangle(width, height)


def swept_box(path, start: Sequence[float], direction: Sequence[float], across: Sequence[float],
              width: float, height: float):
    """Sweep a rectangle along ``path`` (a build123d wire) starting at ``start`` with tangent ``direction``."""
    from build123d import sweep

    return sweep(rect_profile(start, direction, across, width, height), path=path)


def bend_path(radius: float, straight: float, extend: float = 0.0):
    """Wire: +x line into a 90 degree arc turning to +y, then a +y line.

    The arc is centered on (0, radius, 0) and runs from (0, 0, 0) to
    (radius, radius, 0). The input line starts at x = -straight - extend; the
    output line ends at y = radius + straight + extend. Returns
    ``(wire, start point, end point)``.
    """
    from build123d import CenterArc, Line, Wire

    a = (-straight - extend, 0.0, 0.0)
    b = (0.0, 0.0, 0.0)
    c = (radius, radius, 0.0)
    d = (radius, radius + straight + extend, 0.0)
    arc = CenterArc((0.0, radius, 0.0), radius, start_angle=-90.0, arc_size=90.0)
    return Wire([Line(a, b), arc, Line(c, d)]), a, d


def check_volume(shape, expected: float, what: str, rel: float = 0.02) -> None:
    """Refuse a boolean result whose volume is off by more than ``rel`` (OCCT can fail silently)."""
    got = float(shape.volume)
    if not math.isfinite(got) or abs(got - expected) > rel * abs(expected):
        raise RuntimeError(f"{what}: volume {got:.6g} differs from the expected {expected:.6g}; "
                           "the CAD boolean failed")


def axis_rotation(axis: str):
    """build123d rotation that turns the +z axis onto ``axis`` ("x", "y" or "z")."""
    from build123d import Rot

    return {"x": Rot(0, 90, 0), "y": Rot(-90, 0, 0), "z": Rot(0, 0, 0)}[axis]


def cylinder_along(axis: str, radius: float, x0: float, x1: float, center: Tuple[float, float] = (0.0, 0.0)):
    """Solid cylinder of ``radius`` from ``x0`` to ``x1`` along ``axis``; ``center`` is the other two coordinates."""
    from build123d import Align, Cylinder, Pos

    length = x1 - x0
    cyl = axis_rotation(axis) * Cylinder(radius, length, align=(Align.CENTER, Align.CENTER, Align.MIN))
    mid = {"x": (x0, center[0], center[1]), "y": (center[0], x0, center[1]), "z": (center[0], center[1], x0)}[axis]
    return Pos(*mid) * cyl


def waveguide_bend(p, plane: str):
    """Hollow 90 degree rectangular waveguide bend; ``plane`` is ``"E"`` or ``"H"``.

    The centerline runs +x into a circular arc of mean radius ``p.radius``
    and leaves along +y, with ``p.straight`` of straight guide on each side.
    In an H-plane bend the broad wall ``a`` lies in the bend plane (xy) and
    ``b`` is along z; in an E-plane bend the narrow wall ``b`` lies in the
    bend plane and ``a`` is along z (the TE10 E field then points in-plane).
    Returns ``(metal solid, port1, port2)`` with ports as ``(point, normal)``.
    """
    if plane not in ("E", "H"):
        raise ValueError("plane must be 'E' or 'H'")
    across, height = (p.a, p.b) if plane == "H" else (p.b, p.a)
    t = p.wall
    if p.radius <= across / 2.0 + t:
        raise ValueError(f"radius {p.radius:g} must exceed half the in-plane guide width plus the wall "
                         f"({across / 2.0 + t:g})")
    path, start, _ = bend_path(p.radius, p.straight)
    long_path, long_start, _ = bend_path(p.radius, p.straight, extend=t)
    outer = swept_box(path, start, (1, 0, 0), (0, 1, 0), across + 2 * t, height + 2 * t)
    air = swept_box(long_path, long_start, (1, 0, 0), (0, 1, 0), across, height)
    metal = outer - air
    centerline = 2.0 * p.straight + math.pi * p.radius / 2.0
    check_volume(metal, ((across + 2 * t) * (height + 2 * t) - across * height) * centerline, f"{plane}-plane bend")
    port1 = ((-p.straight, 0.0, 0.0), (-1.0, 0.0, 0.0))
    port2 = ((p.radius, p.radius + p.straight, 0.0), (0.0, 1.0, 0.0))
    return metal, port1, port2


# --------------------------------------------------------------------------
# Coplanar waveguide layout (cpw.py and grounded_cpw.py)
# --------------------------------------------------------------------------
def cpw_bodies(p, *, grounded: bool):
    """Bodies of a straight CPW along x; ``p`` holds the cpw / grounded_cpw parameters.

    Center strip ``s``, slots ``gap``, coplanar grounds ``ground_width`` wide
    out to the board edge. ``grounded`` adds the backing ground and, when
    ``p.vias`` is 1, a via fence on each side at ``via_offset`` from the slot
    edge with ``via_pitch`` spacing.
    """
    from witwin.studio import layout as L

    stack = board_stack(p.h, p.t, p.eps_r, p.tan_delta, p.f0, ground=grounded)
    board_width = p.s + 2.0 * p.gap + 2.0 * p.ground_width
    half = p.length / 2.0
    lay = L.Layout(unit="mm", outline=L.rect(p.length, board_width))
    lay.add("top", L.path([(-half, 0.0), (half, 0.0)], width=p.s))
    ground_y = p.s / 2.0 + p.gap + p.ground_width / 2.0
    for side in (-1.0, 1.0):
        lay.add("top", L.rect(p.length, p.ground_width, center=(0.0, side * ground_y)))
    lay.port("port1", "top", (-half, 0.0), direction=(-1, 0), width=p.s)
    lay.port("port2", "top", (half, 0.0), direction=(1, 0), width=p.s)
    for name, x, normal in (("port1_gnd", -half, (-1, 0, 0)), ("port2_gnd", half, (1, 0, 0))):
        lay.anchor(name, "top", (x, ground_y), normal=normal)
    if grounded and int(getattr(p, "vias", 0)):
        edge = p.s / 2.0 + p.gap + p.via_offset
        outer = p.s / 2.0 + p.gap + p.ground_width
        if p.via_drill / 2.0 >= p.via_offset or edge + p.via_drill / 2.0 >= outer:
            raise ValueError("the via fence does not fit inside the coplanar ground: check via_offset, "
                             "via_drill and ground_width")
        count = max(1, int((p.length - p.via_drill) // p.via_pitch) + 1)
        start = -(count - 1) * p.via_pitch / 2.0
        for i in range(count):
            for side in (-1.0, 1.0):
                lay.via((start + i * p.via_pitch, side * edge), drill=p.via_drill, from_layer="bottom",
                        to_layer="top")
    return lay.to_bodies(stack)
