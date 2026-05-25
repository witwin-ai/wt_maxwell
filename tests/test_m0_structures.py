"""M0 round-trip: scene config + structures (scalar materials).

Builds a ``maxwell.Scene`` with three primitives + scalar materials + a domain /
grid / PML boundary, runs it through ``to_studio`` then ``to_platform``, and
asserts the rebuilt scene reproduces the config and every structure.
"""
import witwin.maxwell as mw

from _helpers import assert_config_equal, assert_structures_equal


def _build_scene() -> "mw.Scene":
    scene = mw.Scene(
        domain=mw.Domain(bounds=((-0.5, 0.6), (-0.4, 0.5), (-0.3, 0.7))),
        grid=mw.GridSpec.uniform(0.05),
        boundary=mw.BoundarySpec.pml(num_layers=12, strength=5e5),
        subpixel_samples=2,
        symmetry=("PEC", None, None),
        device="cpu",
    )
    scene.add_structure(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.2, 0.3, 0.4)),
        mw.Material(eps_r=3.0, name="diel"), name="box"))
    scene.add_structure(mw.Structure(
        mw.Sphere(position=(0.1, 0.0, 0.0), radius=0.15),
        mw.Material(eps_r=2.0, sigma_e=0.01, name="lossy"), name="ball",
        priority=2, tags=("a", "b")))
    scene.add_structure(mw.Structure(
        mw.Cylinder(position=(0.0, 0.1, 0.0), radius=0.05, height=0.3, axis="z"),
        mw.Material(mu_r=1.5, name="mag"), name="rod"))
    return scene


def test_detect_claims_maxwell_scene(adapter):
    assert adapter.detect(_build_scene()) is True
    assert adapter.detect(object()) is False


def test_config_round_trip(adapter):
    original = _build_scene()
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert_config_equal(original, rebuilt)


def test_structures_round_trip(adapter):
    original = _build_scene()
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert_structures_equal(original.structures, rebuilt.structures)


def test_anisotropic_grid_round_trip(adapter):
    original = _build_scene().clone(grid=mw.GridSpec.anisotropic(0.04, 0.05, 0.06))
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert_config_equal(original, rebuilt)


def test_per_face_boundary_round_trip(adapter):
    boundary = mw.BoundarySpec.faces(
        default="pml", num_layers=10, strength=4e5,
        x_low="pml", x_high="pec", y_low="periodic", y_high="periodic",
        z_low="pml", z_high="pmc")
    original = _build_scene().clone(boundary=boundary)
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert_config_equal(original, rebuilt)
