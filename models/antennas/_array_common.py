"""Tiling of single-element antenna generators into arrays (shared by the array model files).

Not a model file. An element is any generator in this folder, chosen by an
integer code (``ELEMENTS``). Two tiling paths:

- Layout elements (a module-level ``layout(p)``: patches, IFA, spiral,
  Vivaldi) are re-drawn as one ``witwin.studio.layout`` board: each copper
  layer gets the translated copies, ground layers keep every element's
  holes, vias and ports are copied, and the substrate becomes one slab over
  the whole array. Extra bodies (coax feeds) are translated.
- Other elements are built once and their bodies translated. Bodies the
  element names in ``ARRAY_SHARED`` (a ground plane) are merged into one
  rectangle (sheet or box) covering all copies.

Copies are translated only, never rotated, and the array lies in the XY
plane. Body and anchor names get the suffix ``_<i>`` (element index, row
major); ports become ``feed_<i>``.
"""
from __future__ import annotations

import math
import runpy
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

import _antenna_common as ac

# Element code -> model file stem. Codes are part of the PARAMS contract: append only.
ELEMENTS = (
    "patch", "patch_probe", "circular_patch", "aperture_coupled_patch", "dipole", "monopole", "pifa", "ifa",
    "yagi", "lpda", "helix", "spiral", "pyramidal_horn", "conical_horn", "corrugated_horn", "vivaldi", "slot",
    "reflector",
)
ELEMENT_HELP = ", ".join(f"{i} = {name}" for i, name in enumerate(ELEMENTS))

_NAMESPACES: Dict[str, Dict[str, Any]] = {}


def element_code(name: str) -> int:
    """Integer code of an element name (``"patch"`` -> 0)."""
    return ELEMENTS.index(name)


def element_namespace(code: int) -> Dict[str, Any]:
    """The element model file's globals (loaded once per process)."""
    code = int(code)
    if not 0 <= code < len(ELEMENTS):
        raise ValueError(f"element must be 0..{len(ELEMENTS) - 1} ({ELEMENT_HELP}); got {code}")
    name = ELEMENTS[code]
    if name not in _NAMESPACES:
        _NAMESPACES[name] = runpy.run_path(str(ac.MODELS_DIR / f"{name}.py"), run_name="__witwin_element__")
    return _NAMESPACES[name]


def element_spec(ns: Mapping[str, Any], f0: float) -> Dict[str, float]:
    """The element's design spec for an array centred on ``f0``.

    Elements specified by a band (``f_low``/``f_high``) keep their default
    band ratio around ``f0`` (geometric centre).
    """
    spec = ns.get("DESIGN_SPEC") or {}
    if "f0" in spec:
        return {"f0": f0}
    if "f_low" in spec and "f_high" in spec:
        ratio = spec["f_high"].value / spec["f_low"].value
        return {"f_low": f0 / math.sqrt(ratio), "f_high": f0 * math.sqrt(ratio)}
    return {}


def element_values(code: int, f0: float, use_design: bool, overrides: Mapping[str, Any] = ()) -> Dict[str, Any]:
    """Resolved element parameters (model units, mm) for one array element."""
    from witwin.studio.geometry._model import model_from_namespace

    ns = element_namespace(code)
    model = model_from_namespace(ns)
    params = dict(ns["design"](element_spec(ns, f0))) if use_design else {}
    params.update(dict(overrides or {}))
    values, _ = model.resolve(params)
    return values


def lattice(nx: int, ny: int, dx: float, dy: float, triangular: bool = False) -> List[Tuple[float, float]]:
    """Element centres, row major, centred on the origin; triangular shifts odd rows by dx/2."""
    pts = []
    shift = dx / 4 if (triangular and ny > 1) else 0.0
    for iy in range(ny):
        offset = (dx / 2 if (triangular and iy % 2) else 0.0) - shift
        for ix in range(nx):
            pts.append(((ix - (nx - 1) / 2) * dx + offset, (iy - (ny - 1) / 2) * dy))
    return pts


def spacing_mm(f0: float, spacing_lambda: float, spacing_abs: float) -> float:
    """Pitch in mm: the absolute value when given (> 0), else spacing in free-space wavelengths at f0."""
    return spacing_abs if spacing_abs > 0 else spacing_lambda * ac.wavelength_mm(f0)


# ------------------------------------------------------------------ tiling
def _move_body(body: Any, dx: float, dy: float, suffix: str) -> Any:
    import witwin.studio as ws

    v = np.asarray(body.mesh.vertices) + np.array([dx, dy, 0.0])
    anchors = [ws.anchor(f"{a.name}{suffix}", point=(a.point[0] + dx, a.point[1] + dy, a.point[2]),
                         normal=a.normal, kind=a.kind) for a in body.anchors]
    return ws.Body((v, np.asarray(body.mesh.faces)), name=f"{body.name}{suffix}", material=body.material,
                   fill=body.fill, role=body.role, anchors=anchors, surface_thickness=body.surface_thickness)


def _move_anchor(a: Any, dx: float, dy: float, suffix: str) -> Any:
    import witwin.studio as ws

    return ws.anchor(f"{a.name}{suffix}", point=(a.point[0] + dx, a.point[1] + dy, a.point[2]),
                     normal=a.normal, kind=a.kind)


def _translate_extras(extras: Sequence[Any], dx: float, dy: float, suffix: str) -> List[Any]:
    from witwin.studio.geometry import Anchor

    return [_move_anchor(e, dx, dy, suffix) if isinstance(e, Anchor) else _move_body(e, dx, dy, suffix)
            for e in extras]


def _drop_slivers(geom: Any, min_area: float = 1e-6) -> Any:
    """Polygon parts of ``geom`` above ``min_area`` (mm^2).

    outline - ground leaves zero-area slivers along the board edge from float
    noise; ``layout.clean`` can turn such a sliver into a large wrong polygon,
    so drop them first.
    """
    import shapely
    from shapely.geometry import Polygon

    parts = [g for g in getattr(geom, "geoms", [geom]) if g.geom_type == "Polygon" and g.area > min_area]
    return shapely.union_all(parts) if parts else Polygon()


def tile_layout(ns: Mapping[str, Any], values: Mapping[str, Any], positions: Sequence[Tuple[float, float]],
                *, ports: bool = True, extra_outline: Any = None):
    """(Layout, LayerStack, extras) of a layout element tiled at ``positions``.

    ``ports=False`` drops the element ports (a feed network supplies its
    own). ``extra_outline`` (shapely) is added to the board outline.
    """
    import shapely
    from shapely import affinity
    from witwin.studio import layout as L

    el_lay, stack, extras = ns["layout"](values)
    resolved = el_lay.resolve(stack)
    el_outline = el_lay.outline
    outlines = [affinity.translate(el_outline, dx, dy) for dx, dy in positions]
    if extra_outline is not None:
        outlines.append(extra_outline)
    x0, y0, x1, y1 = shapely.union_all(outlines).bounds
    lay = L.Layout(unit="mm", outline=L.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)]))
    out_extras: List[Any] = []
    for i, (dx, dy) in enumerate(positions):
        for layer in stack:
            geom = resolved[layer.name]
            if layer.kind == "dielectric":
                continue
            if layer.kind == "ground":
                holes = _drop_slivers(el_outline.difference(geom))
                if not holes.is_empty:
                    lay.cut(layer.name, affinity.translate(holes, dx, dy))
            elif not geom.is_empty:
                lay.add(layer.name, affinity.translate(geom, dx, dy))
        for via in el_lay.vias:
            lay.via((via.position[0] + dx, via.position[1] + dy), drill=via.drill, pad=via.pad,
                    from_layer=via.from_layer, to_layer=via.to_layer)
        if ports:
            for port in el_lay.ports.values():
                lay.port(f"{port.name}_{i}", port.layer, (port.point[0] + dx, port.point[1] + dy),
                         direction=port.direction, width=port.width, reference=port.reference)
        out_extras += _translate_extras(extras, dx, dy, f"_{i}")
    return lay, stack, out_extras


def tile_bodies(ns: Mapping[str, Any], values: Mapping[str, Any], positions: Sequence[Tuple[float, float]]) -> List[Any]:
    """Bodies and anchors of a non-layout element tiled at ``positions`` (shared bodies merged)."""
    import witwin.studio as ws
    from witwin.studio.geometry._model import model_from_namespace

    model = model_from_namespace(ns)
    output = model.run(values)
    shared = set(ns.get("ARRAY_SHARED") or ())
    out: List[Any] = []
    for name, body in zip(output.names, output.bodies):
        body.name = name
        if name in shared:
            out.append(_merged(body, positions))
            continue
        for i, (dx, dy) in enumerate(positions):
            out.append(_move_body(body, dx, dy, f"_{i}"))
    for i, (dx, dy) in enumerate(positions):
        out += [_move_anchor(a, dx, dy, f"_{i}") for a in output.anchors]
    return out


def _merged(body: Any, positions: Sequence[Tuple[float, float]]) -> Any:
    """One rectangle (sheet or box) covering every translated copy of ``body``."""
    import witwin.studio as ws

    v = np.asarray(body.mesh.vertices)
    lo, hi = v.min(axis=0), v.max(axis=0)
    xs = [p[0] for p in positions]
    ys = [p[1] for p in positions]
    x0, x1 = lo[0] + min(xs), hi[0] + max(xs)
    y0, y1 = lo[1] + min(ys), hi[1] + max(ys)
    if body.fill == "surface":
        z = float(v[:, 2].mean())
        mesh = ac.quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z))
    else:
        mesh = ac.box((x0, y0, lo[2]), (x1, y1, hi[2]))
    return ws.Body(mesh, name=body.name, material=body.material, fill=body.fill, role=body.role,
                   surface_thickness=body.surface_thickness)


def tile(code: int, values: Mapping[str, Any], positions: Sequence[Tuple[float, float]]) -> List[Any]:
    """``build`` output of ``positions`` copies of element ``code``."""
    ns = element_namespace(code)
    if "layout" in ns:
        lay, stack, extras = tile_layout(ns, values, positions)
        return ac.layout_output(lay, stack, extras)
    return tile_bodies(ns, values, positions)


# ---------------------------------------------------------- corporate feed
def corporate_feed(lay: Any, ends: Sequence[Tuple[float, float]], *, w50: float, w35: float, quarter35: float,
                   drop: float, tail: float, layer: str = "top") -> Tuple[float, float]:
    """Draw a binary corporate microstrip tree below ``ends`` (line ends pointing -y); returns the root end.

    Each level joins neighbouring nodes pairwise: both 50 ohm lines drop by
    ``drop`` and meet at the midpoint (two 50 ohm lines in parallel make
    25 ohm), then a quarter-wave 35.36 ohm section (``w35`` wide,
    ``quarter35`` long) transforms the junction back to 50 ohm. The tree is
    symmetric, so every element sees the same path length (equal phase).
    Junction and bend discontinuities are not compensated.
    """
    from witwin.studio import layout as L

    nodes = list(ends)
    if len(nodes) & (len(nodes) - 1):
        raise ValueError(f"a corporate feed needs a power-of-two element count, got {len(nodes)}")
    while len(nodes) > 1:
        y_j = min(y for _, y in nodes) - drop
        nxt = []
        for (xa, ya), (xb, yb) in zip(nodes[0::2], nodes[1::2]):
            xm = (xa + xb) / 2
            lay.add(layer, L.path([(xa, ya), (xa, y_j), (xm, y_j)], width=w50, end="square"))
            lay.add(layer, L.path([(xb, yb), (xb, y_j), (xm, y_j)], width=w50, end="square"))
            lay.add(layer, L.path([(xm, y_j), (xm, y_j - quarter35)], width=w35))
            nxt.append((xm, y_j - quarter35))
        nodes = nxt
    (xr, yr), = nodes
    end = (xr, yr - tail)
    lay.add(layer, L.path([(xr, yr), end], width=w50))
    return end
