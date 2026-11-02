"""Helpers shared by the periodic-structure generators: cell stacks and cell-boundary anchors.

A unit cell is centered on the origin in xy and spans ``period_x`` x
``period_y``. Every generator marks the cell with the same anchors so a
solver setup can find them by name:

- ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax`` (kind
  ``periodic``): the centers of the four side faces of the cell, normals
  pointing out of the cell. Put periodic or Bloch/Floquet boundaries on
  these planes.
- ``port1`` (kind ``port``): the Floquet port above the cell, at the top
  face center, normal +z. ``port2``: the one below, at the bottom face
  center, normal -z; it is left out when a ground plane closes the cell.

The bodies tile without gaps: the dielectric slab and any ground fill the
whole cell outline, and the pattern stays inside it.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

import witwin.studio as ws

C0 = 299_792_458.0
EPS0 = 8.8541878128e-12
PEC = "PEC"


def dielectric(name: str, eps_r: float, tan_delta: float, f0_ghz: Optional[float] = None) -> Dict[str, object]:
    """Material dict of a dielectric; ``sigma_e`` from ``tan_delta`` at ``f0_ghz`` when given."""
    out: Dict[str, object] = {"name": name, "eps_r": float(eps_r), "tan_delta": float(tan_delta)}
    if f0_ghz:
        out["sigma_e"] = 2.0 * math.pi * f0_ghz * 1e9 * EPS0 * eps_r * tan_delta
    return out


def cell_stack(h: float, t: float, eps_r: float, tan_delta: float, f0_ghz: Optional[float], *,
               ground: bool, substrate: bool = True, top_kind: str = "conductor", unit: str = "mm"):
    """Cell layers: optional ``bottom`` ground, optional ``core`` slab, ``top`` pattern layer."""
    from witwin.studio import layout as L

    layers = []
    if ground:
        layers.append(("bottom", "ground", t, {"material": PEC}))
    if substrate:
        layers.append(("core", "dielectric", h, {"material": dielectric("substrate", eps_r, tan_delta, f0_ghz)}))
    layers.append(("top", top_kind, t, {"material": PEC}))
    return L.LayerStack(layers, unit=unit, z0=-t if ground else 0.0)


def boundary_anchors(px: float, py: float, z_mid: float) -> List[ws.Anchor]:
    """The four ``cell_*`` anchors (kind ``periodic``) at height ``z_mid``."""
    return [
        ws.anchor("cell_xmin", point=(-px / 2.0, 0.0, z_mid), normal=(-1, 0, 0), kind="periodic"),
        ws.anchor("cell_xmax", point=(px / 2.0, 0.0, z_mid), normal=(1, 0, 0), kind="periodic"),
        ws.anchor("cell_ymin", point=(0.0, -py / 2.0, z_mid), normal=(0, -1, 0), kind="periodic"),
        ws.anchor("cell_ymax", point=(0.0, py / 2.0, z_mid), normal=(0, 1, 0), kind="periodic"),
    ]


def floquet_ports(z_top: float, z_bottom: Optional[float]) -> List[ws.Anchor]:
    """``port1`` on the top face (normal +z) and, unless ``z_bottom`` is None, ``port2`` below (normal -z)."""
    out = [ws.anchor("port1", point=(0.0, 0.0, z_top), normal=(0, 0, 1), kind="port")]
    if z_bottom is not None:
        out.append(ws.anchor("port2", point=(0.0, 0.0, z_bottom), normal=(0, 0, -1), kind="port"))
    return out


def layout_cell(lay, stack, period_x: float, period_y: float, *, ground: bool, substrate: bool = True,
                h: float = 0.0, t: float = 0.0) -> list:
    """Bodies of a planar cell plus its boundary and Floquet anchors (model unit).

    ``lay`` is a ``Layout`` whose outline is the cell. The top of the cell
    is the pattern sheet's height (``h`` with a substrate, else the sheet
    itself at ``t/2``); its bottom is z = 0, or no bottom port with a ground.
    """
    bodies = lay.to_bodies(stack)
    z_top = h if substrate else t / 2.0
    z_bottom = None if ground else (0.0 if substrate else t / 2.0)
    z_mid = h / 2.0 if substrate else t / 2.0
    return bodies + boundary_anchors(period_x, period_y, z_mid) + floquet_ports(z_top, z_bottom)


def spec_values(defaults, spec) -> Dict[str, float]:
    """Spec values with ``DESIGN_SPEC`` defaults for every missing key; unknown keys are refused."""
    spec = dict(spec or {})
    unknown = sorted(set(spec) - set(defaults))
    if unknown:
        raise KeyError(f"unknown design spec keys {unknown}; known: {sorted(defaults)}")
    return {k: float(spec[k]) if k in spec else float(getattr(p, "value", p)) for k, p in defaults.items()}


def eps_eff_sheet(eps_r: float, substrate: bool = True) -> float:
    """Effective permittivity seen by a pattern on a substrate surface: (eps_r + 1)/2, or 1 free-standing.

    The half-space average. A dielectric on one side of the pattern lowers
    the resonance by sqrt((eps_r + 1)/2) once it is thick enough (Munk,
    Frequency Selective Surfaces, 2000, ch. 4); a thin substrate lowers it
    less, so this first-cut value errs toward too small a pattern.
    """
    return (eps_r + 1.0) / 2.0 if substrate else 1.0
