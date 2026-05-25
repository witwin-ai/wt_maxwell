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


def _poles_equal(p1: Any, p2: Any, attrs: tuple) -> None:
    p1, p2 = tuple(p1), tuple(p2)
    assert len(p1) == len(p2), f"pole count {len(p1)} != {len(p2)}"
    for a, b in zip(p1, p2):
        for attr in attrs:
            assert approx(getattr(a, attr), getattr(b, attr)), f"pole {attr}"


def _tensor_equal(t1: Any, t2: Any) -> None:
    if t1 is None and t2 is None:
        return
    assert t1 is not None and t2 is not None, "tensor None mismatch"
    assert all(approx(x, y) for x, y in zip(t1.as_tuple(), t2.as_tuple())), "tensor values"


def assert_material_full_equal(m1: Any, m2: Any) -> None:
    """Assert two maxwell materials match across the full superset + capability flags."""
    assert_material_scalar_equal(m1, m2)
    assert bool(m1.is_dispersive) == bool(m2.is_dispersive), "is_dispersive"
    assert bool(m1.is_anisotropic) == bool(m2.is_anisotropic), "is_anisotropic"
    assert bool(m1.is_nonlinear) == bool(m2.is_nonlinear), "is_nonlinear"
    _poles_equal(m1.debye_poles, m2.debye_poles, ("delta_eps", "tau"))
    _poles_equal(m1.drude_poles, m2.drude_poles, ("plasma_frequency", "gamma"))
    _poles_equal(m1.lorentz_poles, m2.lorentz_poles, ("delta_eps", "resonance_frequency", "gamma"))
    _poles_equal(m1.mu_debye_poles, m2.mu_debye_poles, ("delta_eps", "tau"))
    _poles_equal(m1.mu_drude_poles, m2.mu_drude_poles, ("plasma_frequency", "gamma"))
    _poles_equal(m1.mu_lorentz_poles, m2.mu_lorentz_poles, ("delta_eps", "resonance_frequency", "gamma"))
    _tensor_equal(m1.epsilon_tensor, m2.epsilon_tensor)
    _tensor_equal(m1.mu_tensor, m2.mu_tensor)
    _tensor_equal(m1.sigma_e_tensor, m2.sigma_e_tensor)
    assert approx(m1.kerr_chi3 or 0.0, m2.kerr_chi3 or 0.0), "kerr_chi3"


def assert_region_equal(r1: Any, r2: Any) -> None:
    """Assert two MaterialRegions match (name/basis/bounds/filter/projection/shape/geometry)."""
    assert (r1.name or "") == (r2.name or ""), "region name"
    assert str(r1.basis) == str(r2.basis), "basis"
    assert all(approx(a, b) for a, b in zip(r1.bounds, r2.bounds)), "bounds"
    assert all(approx(a, b) for a, b in zip(r1.eps_bounds, r2.eps_bounds)), "eps_bounds"
    assert all(approx(a, b) for a, b in zip(r1.mu_bounds, r2.mu_bounds)), "mu_bounds"
    assert tuple(r1.density.shape) == tuple(r2.density.shape), "density shape"
    f1 = None if r1.filter_radius is None else float(r1.filter_radius)
    f2 = None if r2.filter_radius is None else float(r2.filter_radius)
    assert (f1 is None) == (f2 is None) and (f1 is None or approx(f1, f2)), "filter_radius"
    p1 = None if r1.projection_beta is None else float(r1.projection_beta)
    p2 = None if r2.projection_beta is None else float(r2.projection_beta)
    assert (p1 is None) == (p2 is None) and (p1 is None or approx(p1, p2)), "projection_beta"
    assert (r1.symmetry or None) == (r2.symmetry or None), "region symmetry"
    assert_geometry_equal(r1.geometry, r2.geometry)


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
