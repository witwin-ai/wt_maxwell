"""M1 round-trip: full materials (dispersion / anisotropy / Kerr) + MaterialRegion.

Round-trips materials covering each pole type (electric and magnetic), a diagonal
anisotropic material, and a Kerr material, asserting the reconstructed
``maxwell.Material`` capability flags + pole/tensor values match. Also asserts each
forbidden combination raises an adapter-side guard, and that a ``MaterialRegion``
round-trips its shape/bounds (density values not serialized).
"""
import pytest
import torch
import witwin.maxwell as mw

from _helpers import assert_material_full_equal, assert_region_equal


def _scene() -> "mw.Scene":
    return mw.Scene(
        domain=mw.Domain(bounds=((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5))),
        grid=mw.GridSpec.uniform(0.1),
        boundary=mw.BoundarySpec.pml(),
        device="cpu",
    )


def _roundtrip_material(adapter, material):
    scene = _scene().add_structure(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.3, 0.3, 0.3)), material, name="m"))
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    return rebuilt.structures[0].material


# --- electric dispersion -----------------------------------------------------

def test_debye_round_trip(adapter):
    mat = mw.Material(eps_r=2.0, debye_poles=(mw.DebyePole(2.5, 1e-12),), name="debye")
    assert_material_full_equal(mat, _roundtrip_material(adapter, mat))


def test_drude_round_trip(adapter):
    mat = mw.Material(eps_r=1.0, drude_poles=(mw.DrudePole(2e15, 1e13),), name="drude")
    assert_material_full_equal(mat, _roundtrip_material(adapter, mat))


def test_lorentz_round_trip(adapter):
    mat = mw.Material(eps_r=1.5, lorentz_poles=(mw.LorentzPole(1.5, 5e14, 1e13),), name="lorentz")
    assert_material_full_equal(mat, _roundtrip_material(adapter, mat))


def test_multiple_poles_round_trip(adapter):
    mat = mw.Material(eps_r=2.0,
                      debye_poles=(mw.DebyePole(1.0, 2e-12), mw.DebyePole(0.5, 4e-12)),
                      lorentz_poles=(mw.LorentzPole(0.8, 3e14, 2e13),), name="multi")
    assert_material_full_equal(mat, _roundtrip_material(adapter, mat))


# --- magnetic dispersion -----------------------------------------------------

def test_magnetic_poles_round_trip(adapter):
    mat = mw.Material(mu_r=1.0,
                      mu_debye_poles=(mw.DebyePole(0.5, 2e-12),),
                      mu_lorentz_poles=(mw.LorentzPole(0.3, 4e14, 1e13),), name="mag")
    rebuilt = _roundtrip_material(adapter, mat)
    assert rebuilt.is_magnetic_dispersive
    assert_material_full_equal(mat, rebuilt)


# --- anisotropy --------------------------------------------------------------

def test_diagonal_anisotropy_round_trip(adapter):
    mat = mw.Material(eps_r=1.0, epsilon_tensor=mw.DiagonalTensor3(2.0, 3.0, 4.0), name="aniso")
    rebuilt = _roundtrip_material(adapter, mat)
    assert rebuilt.is_anisotropic
    assert_material_full_equal(mat, rebuilt)


def test_anisotropic_eps_mu_sigma_round_trip(adapter):
    mat = mw.Material(
        eps_r=1.0, mu_r=1.0, sigma_e=0.0,
        epsilon_tensor=mw.DiagonalTensor3(2.0, 2.5, 3.0),
        mu_tensor=mw.DiagonalTensor3(1.0, 1.2, 1.4),
        sigma_e_tensor=mw.DiagonalTensor3(0.0, 0.01, 0.02),
        name="aniso3")
    assert_material_full_equal(mat, _roundtrip_material(adapter, mat))


# --- nonlinearity ------------------------------------------------------------

def test_kerr_round_trip(adapter):
    mat = mw.Material(eps_r=1.5, kerr_chi3=1e-20, name="kerr")
    rebuilt = _roundtrip_material(adapter, mat)
    assert rebuilt.is_nonlinear
    assert_material_full_equal(mat, rebuilt)


# --- guards (forbidden combinations) -----------------------------------------

def _em(model="scalar", **fields):
    from witwin_server.core.components import MaterialComponent
    em = MaterialComponent()
    em.model = model
    for key, value in fields.items():
        setattr(em, key, value)
    return em


def test_guard_anisotropic_plus_dispersive(mat_adapter):
    em = _em(model="anisotropic", epsilon_tensor=[2.0, 3.0, 4.0], debye_poles=[[1.0, 1e-12]])
    with pytest.raises(ValueError):
        mat_adapter.to_platform(em)


def test_guard_kerr_plus_dispersive(mat_adapter):
    em = _em(model="dispersive", debye_poles=[[1.0, 1e-12]], kerr_chi3=1e-20)
    with pytest.raises(ValueError):
        mat_adapter.to_platform(em)


def test_guard_kerr_plus_anisotropic(mat_adapter):
    em = _em(model="anisotropic", epsilon_tensor=[2.0, 3.0, 4.0], kerr_chi3=1e-20)
    with pytest.raises(ValueError):
        mat_adapter.to_platform(em)


# --- MaterialRegion ----------------------------------------------------------

def test_material_region_round_trip(adapter):
    region = mw.MaterialRegion(
        name="opt", geometry=mw.Box(position=(0.0, 0.0, 0.0), size=(0.4, 0.4, 0.4)),
        density=torch.zeros(6, 8, 10), bounds=(0.0, 1.0),
        eps_bounds=(1.0, 12.0), mu_bounds=(1.0, 1.0),
        filter_radius=0.05, projection_beta=8.0, symmetry="density")
    scene = _scene()
    scene.add_material_region(region)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    assert len(rebuilt.material_regions) == 1
    assert_region_equal(region, rebuilt.material_regions[0])
