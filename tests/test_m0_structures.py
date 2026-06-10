"""M0 round-trip: scene config + structures (scalar materials).

Builds a ``maxwell.Scene`` with three primitives + scalar materials + a domain /
grid / PML boundary, runs it through ``to_studio`` then ``to_platform``, and
asserts the rebuilt scene reproduces the config and every structure.
"""
import math

import numpy as np
import witwin.maxwell as mw
from witwin_server.core.components import MaterialComponent, PlatformGeometryComponent, SkinnedMeshComponent
from witwin_server.features.timeline import InterpolationType, TimelineManager
from witwin_server.features.solvers.scene_ref import load_scene_ref, make_scene_ref
from witwin_server import SceneObject

from _helpers import approx, assert_config_equal


def _build_scene() -> "mw.Scene":
    scene = mw.Scene(
        domain=mw.Domain(bounds=((-0.5, 0.6), (-0.4, 0.5), (-0.3, 0.7))),
        grid=mw.GridSpec.uniform(299792458.0 / 1e9 / 6.0),
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


def test_solver_transform_offsets_domain_bounds(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    settings.get_component("Transform").position = [1.0, 2.0, 3.0]

    rebuilt = adapter.to_platform(studio)

    expected = ((0.5, 1.6), (1.6, 2.5), (2.7, 3.7))
    for got_axis, expected_axis in zip(rebuilt.domain.bounds, expected):
        assert approx(got_axis[0], expected_axis[0])
        assert approx(got_axis[1], expected_axis[1])


def test_field_gizmo_bounds_drive_domain_export(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver.bounds_min = [-9.0, -9.0, -9.0]
    solver.bounds_max = [9.0, 9.0, 9.0]
    solver.min_bound = [-0.2, -0.3, -0.4]
    solver.max_bound = [0.5, 0.6, 0.7]

    rebuilt = adapter.to_platform(studio)

    expected = ((-0.2, 0.5), (-0.3, 0.6), (-0.4, 0.7))
    for got_axis, expected_axis in zip(rebuilt.domain.bounds, expected):
        assert approx(got_axis[0], expected_axis[0])
        assert approx(got_axis[1], expected_axis[1])


def test_settings_object_uses_single_maxwell_solver_component(adapter):
    original = _build_scene()
    studio = adapter.to_studio(original)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")

    assert settings.get_component("MaxwellSolver") is not None
    assert settings.get_component("MaxwellDomain") is None
    assert settings.get_component("MaxwellGrid") is None
    assert settings.get_component("MaxwellBoundary") is None
    assert settings.get_component("MaxwellSolveSettings") is None
    assert settings.get_component("MaxwellResult") is None


def test_maxwell_solver_is_fdtd_only_and_renders_last(wtm):
    from wt_maxwell.components.solver import MaxwellSolverComponent

    definition = MaxwellSolverComponent.get_definition()
    method = next(field for field in definition["fields"] if field["name"] == "method")
    full_field_dft = next(field for field in definition["fields"] if field["name"] == "full_field_dft")
    ppw = next(field for field in definition["fields"] if field["name"] == "ppw")
    groups = definition["groups"]

    assert method["widget"]["options"] == ["fdtd"]
    assert method["hidden"] is True
    assert full_field_dft["hidden"] is True
    assert ppw["widget"]["widget_type"] == "stepped-slider"
    assert ppw["widget"]["options"] == [str(i) for i in range(4, 21)]
    assert groups[-1]["name"] == "Renderer"
    assert groups[-1]["display_name"] == "Rendering"


def test_structures_round_trip(adapter):
    original = _build_scene()
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert len(rebuilt.structures) == len(original.structures)
    for structure in rebuilt.structures:
        assert str(structure.geometry.kind) == "mesh"


def test_maxwell_structures_do_not_expose_platform_components_when_mesh_exists(adapter):
    studio = adapter.to_studio(_build_scene())

    structures = [obj for obj in studio.objects.values() if obj.name in {"box", "ball", "rod"}]

    assert len(structures) == 3
    for obj in structures:
        mesh = obj.get_component("Mesh")
        assert mesh is not None and not mesh.is_empty
        assert obj.get_component("PlatformGeometry") is None
        assert obj.get_component("StructureMeta") is None


def test_library_dielectric_box_does_not_expose_platform_components():
    from wt_maxwell.library_items import _box_object

    obj = _box_object()

    mesh = obj.get_component("Mesh")
    assert mesh is not None and not mesh.is_empty
    assert obj.get_component("PlatformGeometry") is None
    assert obj.get_component("StructureMeta") is None
    assert approx(float(obj.get_component("Material").eps_r), 11.7)


def test_plain_studio_mesh_exports_as_maxwell_structure(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    cube = SceneObject(name="Studio Cube", mesh_type="Cube")
    cube.get_component("Transform").position = [0.1, 0.2, 0.3]
    cube.get_component("Transform").scale = [0.2, 0.3, 0.4]
    cube.get_component("Material").eps_r = 4.0
    studio.add_object(cube)

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.structures) == 1
    structure = rebuilt.structures[0]
    assert structure.name == "Studio Cube"
    assert str(structure.geometry.kind) == "mesh"
    for got, expected in zip(structure.geometry.position, [0.1, 0.2, 0.3]):
        assert approx(got, expected)
    for got, expected in zip(structure.geometry.scale, [0.2, 0.3, 0.4]):
        assert approx(got, expected)
    assert float(structure.material.eps_r.real) == 4.0
    expected_bounds = ((0.0, 0.2), (0.05, 0.35), (0.1, 0.5))
    for got_axis, expected_axis in zip(structure.geometry.bounds_world, expected_bounds):
        assert approx(got_axis[0], expected_axis[0])
        assert approx(got_axis[1], expected_axis[1])


def test_skinned_mesh_exports_posed_surface(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    _add_posed_skinned_target(studio)

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.structures) == 1
    bounds = rebuilt.structures[0].geometry.bounds_world
    assert approx(bounds[0][0], 1.0)
    assert approx(bounds[0][1], 1.0)


def test_scene_ref_skinned_mesh_prefers_runtime_skin_over_smpl_geometry(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    body = _add_posed_skinned_target(studio)
    geom = body.add_component(PlatformGeometryComponent())
    geom.kind = "smpl"
    geom.model_root = "E:/missing/smpl/body_models"

    restored = load_scene_ref(make_scene_ref(studio))
    rebuilt = adapter.to_platform(restored)

    assert len(rebuilt.structures) == 1
    bounds = rebuilt.structures[0].geometry.bounds_world
    assert approx(bounds[0][0], 1.0)
    assert approx(bounds[0][1], 1.0)


def test_scene_ref_skinned_mesh_uses_timeline_current_pose_and_material(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    body = _add_posed_skinned_target(studio)
    skinned = body.get_component("SkinnedMesh")
    bone = studio.get_object(skinned.bone_ids[0])
    geom = body.add_component(PlatformGeometryComponent())
    geom.kind = "smpl"
    geom.model_root = "E:/missing/smpl/body_models"

    timeline = TimelineManager(studio)
    timeline.clip.duration = 1.0
    timeline.record_keyframe(
        bone.id, "Transform", "position", [1.0, 0.0, 0.0],
        time=0.0, interpolation=InterpolationType.STEP)
    timeline.record_keyframe(
        bone.id, "Transform", "position", [2.0, 0.0, 0.0],
        time=1.0, interpolation=InterpolationType.STEP)
    timeline.set_time(1.0, apply_to_scene=True)

    restored = load_scene_ref(make_scene_ref(studio))
    rebuilt = adapter.to_platform(restored)

    assert len(rebuilt.structures) == 1
    structure = rebuilt.structures[0]
    bounds = structure.geometry.bounds_world
    assert approx(bounds[0][0], 2.0)
    assert approx(bounds[0][1], 2.0)
    assert approx(float(structure.material.eps_r.real), 6.5)
    assert approx(float(structure.material.sigma_e), 0.25)


def _add_posed_skinned_target(studio):
    body = SceneObject(name="Skinned Target", mesh_type="Empty")
    studio.add_object(body)
    material = body.add_component(MaterialComponent())
    material.eps_r = 6.5
    material.sigma_e = 0.25

    bone = SceneObject(name="Skinned Target Bone", mesh_type="Empty")
    studio.add_object(bone)
    studio.set_parent(bone.id, body.id, keep_local_transform=False)
    bone.get_component("Transform").position = [1.0, 0.0, 0.0]

    skinned = SkinnedMeshComponent()
    body.add_component(skinned)
    skinned.set_mesh_data(
        np.array([[0.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]], dtype=np.float32),
        np.array([[0, 1, 2]], dtype=np.uint32),
        notify=False,
    )
    skinned.set_skinning_data(
        [bone.id],
        np.zeros((3, 4), dtype=np.int64),
        np.array([[1.0, 0.0, 0.0, 0.0]] * 3, dtype=np.float32),
        np.eye(4, dtype=np.float32).reshape(1, 4, 4),
        root_bone_id=bone.id,
    )
    return body


def test_visible_mesh_takes_precedence_over_platform_geometry(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    cube = SceneObject(name="Visual Cube", mesh_type="Cube")
    cube.get_component("Transform").scale = [0.4, 0.2, 0.1]
    cube.get_component("Material").eps_r = 5.0
    geom = cube.add_component(PlatformGeometryComponent())
    geom.kind = "box"
    geom.size = [0.05, 0.05, 0.05]
    studio.add_object(cube)

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.structures) == 1
    structure = rebuilt.structures[0]
    assert str(structure.geometry.kind) == "mesh"
    assert float(structure.material.eps_r.real) == 5.0
    expected_bounds = ((-0.2, 0.2), (-0.1, 0.1), (-0.05, 0.05))
    for got_axis, expected_axis in zip(structure.geometry.bounds_world, expected_bounds):
        assert approx(got_axis[0], expected_axis[0])
        assert approx(got_axis[1], expected_axis[1])


def test_invisible_mesh_is_not_exported_as_structure(adapter):
    original = _build_scene().clone(structures=[])
    studio = adapter.to_studio(original)
    cube = SceneObject(name="Hidden Cube", mesh_type="Cube")
    cube.visible = False
    cube.get_component("Material").eps_r = 4.0
    studio.add_object(cube)

    rebuilt = adapter.to_platform(studio)

    assert rebuilt.structures == []


def test_scaled_imported_structure_exports_visual_world_mesh(adapter):
    original = _build_scene().clone(structures=[
        mw.Structure(
            mw.Box(position=(0.0, 0.0, 0.0), size=(0.2, 0.2, 0.2)),
            mw.Material(eps_r=4.0),
            name="scaled_box",
        )
    ])
    studio = adapter.to_studio(original)
    box = next(obj for obj in studio.objects.values() if obj.name == "scaled_box")
    box.get_component("Transform").scale = [0.4, 0.2, 0.2]

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.structures) == 1
    structure = rebuilt.structures[0]
    assert str(structure.geometry.kind) == "mesh"
    expected_bounds = ((-0.2, 0.2), (-0.1, 0.1), (-0.1, 0.1))
    for got_axis, expected_axis in zip(structure.geometry.bounds_world, expected_bounds):
        assert approx(got_axis[0], expected_axis[0])
        assert approx(got_axis[1], expected_axis[1])


def test_anisotropic_grid_import_quantizes_to_ppw_step(adapter):
    original = _build_scene().clone(grid=mw.GridSpec.anisotropic(0.04, 0.05, 0.06))
    studio = adapter.to_studio(original)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    rebuilt = adapter.to_platform(studio)

    expected_ppw = "7"
    expected_dl = 299792458.0 / 1e9 / float(expected_ppw)

    assert str(solver.ppw) == expected_ppw
    assert rebuilt.grid.is_uniform is True
    assert all(approx(v, expected_dl) for v in rebuilt.grid.spacing)


def test_ppw_grid_uses_shortest_wavelength_and_non_cubic_resolution(adapter):
    original = _build_scene().clone(
        structures=[],
        domain=mw.Domain(bounds=((0.0, 0.3), (0.0, 0.6), (0.0, 0.9))),
    )
    studio = adapter.to_studio(original)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver.frequencies = [1e9, 2e9]
    solver.ppw = "12"

    solver._sync_field_bounds()
    rebuilt = adapter.to_platform(studio)

    expected_dl = 299792458.0 / 2e9 / 12.0
    assert rebuilt.grid.is_uniform is True
    assert all(approx(v, expected_dl) for v in rebuilt.grid.spacing)
    expected_resolution = [
        math.ceil(0.3 / expected_dl),
        math.ceil(0.6 / expected_dl),
        math.ceil(0.9 / expected_dl),
    ]
    resolution = solver.resolution.tolist() if hasattr(solver.resolution, "tolist") else solver.resolution
    assert [int(v) for v in resolution] == expected_resolution


def test_per_face_boundary_round_trip(adapter):
    boundary = mw.BoundarySpec.faces(
        default="pml", num_layers=10, strength=4e5,
        x_low="pml", x_high="pec", y_low="periodic", y_high="periodic",
        z_low="pml", z_high="pmc")
    original = _build_scene().clone(boundary=boundary)
    rebuilt = adapter.to_platform(adapter.to_studio(original))
    assert_config_equal(original, rebuilt)
