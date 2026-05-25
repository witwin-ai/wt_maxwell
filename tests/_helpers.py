"""Shared round-trip assertion helpers for the wt-maxwell test suite."""
from typing import Any

from witwin_server.platform_bridge import GeometryMap

TOL = 1e-6


def approx(a: float, b: float, tol: float = TOL) -> bool:
    """Float closeness within ``tol``."""
    return abs(float(a) - float(b)) <= tol


def _params_equal(a: dict, b: dict) -> bool:
    # Compare two PlatformGeometry param dicts (floats/lists/strings) with tolerance.
    if a.keys() != b.keys():
        return False
    for key, va in a.items():
        vb = b[key]
        if isinstance(va, list):
            if len(va) != len(vb) or not all(approx(x, y) for x, y in zip(va, vb)):
                return False
        elif isinstance(va, (int, float)):
            if not approx(va, vb):
                return False
        elif va != vb:
            return False
    return True


def assert_geometry_equal(g1: Any, g2: Any) -> None:
    """Assert two platform geometries match (kind + params + position + rotation)."""
    a, b = GeometryMap.to_studio(g1), GeometryMap.to_studio(g2)
    assert a.kind == b.kind, f"geometry kind {a.kind} != {b.kind}"
    assert _params_equal(a.params, b.params), f"geometry params {a.params} != {b.params}"
    assert all(approx(x, y) for x, y in zip(a.position, b.position)), "geometry position"
    assert all(approx(x, y) for x, y in zip(a.rotation_quat, b.rotation_quat)), "geometry rotation"


def assert_material_scalar_equal(m1: Any, m2: Any) -> None:
    """Assert the scalar part of two materials matches (eps_r/mu_r/sigma_e/name)."""
    assert approx(complex(m1.eps_r).real, complex(m2.eps_r).real), "eps_r real"
    assert approx(complex(m1.eps_r).imag, complex(m2.eps_r).imag), "eps_r imag"
    assert approx(m1.mu_r, m2.mu_r), "mu_r"
    assert approx(m1.sigma_e, m2.sigma_e), "sigma_e"
    assert (m1.name or None) == (m2.name or None), "material name"


def assert_structures_equal(list1: Any, list2: Any) -> None:
    """Assert two structure lists match element-wise (geometry + material + meta)."""
    s1, s2 = list(list1), list(list2)
    assert len(s1) == len(s2), f"structure count {len(s1)} != {len(s2)}"
    by_name1 = {s.name: s for s in s1}
    by_name2 = {s.name: s for s in s2}
    assert by_name1.keys() == by_name2.keys(), "structure names"
    for name, a in by_name1.items():
        b = by_name2[name]
        assert_geometry_equal(a.geometry, b.geometry)
        assert_material_scalar_equal(a.material, b.material)
        assert int(a.priority) == int(b.priority), f"{name} priority"
        assert bool(a.enabled) == bool(b.enabled), f"{name} enabled"
        assert tuple(a.tags) == tuple(b.tags), f"{name} tags"


def assert_config_equal(s1: Any, s2: Any) -> None:
    """Assert two scenes share domain / grid / boundary / subpixel / symmetry / device."""
    for i in range(3):
        assert approx(s1.domain.bounds[i][0], s2.domain.bounds[i][0]), f"domain min {i}"
        assert approx(s1.domain.bounds[i][1], s2.domain.bounds[i][1]), f"domain max {i}"
    assert all(approx(a, b) for a, b in zip(s1.grid.spacing, s2.grid.spacing)), "grid spacing"
    for axis in ("x", "y", "z"):
        for side in ("low", "high"):
            assert str(s1.boundary.face_kind(axis, side)) == str(s2.boundary.face_kind(axis, side)), \
                f"boundary {axis}_{side}"
    assert int(s1.boundary.num_layers) == int(s2.boundary.num_layers), "pml layers"
    assert approx(s1.boundary.strength, s2.boundary.strength), "pml strength"
    assert all(approx(a, b) for a, b in zip(s1.boundary.bloch_wavevector, s2.boundary.bloch_wavevector)), "bloch"
    assert tuple(s1.subpixel_samples) == tuple(s2.subpixel_samples), "subpixel"
    assert tuple(s1.symmetry or (None, None, None)) == tuple(s2.symmetry or (None, None, None)), "symmetry"
    assert str(s1.device) == str(s2.device), "device"
