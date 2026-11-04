"""M2 round-trip: sources + temporal profiles.

Per-source round-trip reproduces constructor args including ``source_time``; TFSF
bounds are preserved; ModeSource ``size`` (one-zero) and polarization round-trip.
"""
import pytest
import witwin.maxwell as mw
from witwin_server.api import SceneObject

from _helpers import assert_source_equal, assert_sources_equal, assert_source_time_equal


def _scene() -> "mw.Scene":
    return mw.Scene(
        domain=mw.Domain(bounds=((-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0))),
        grid=mw.GridSpec.uniform(0.1),
        boundary=mw.BoundarySpec.pml(),
        device="cpu",
    )


def _roundtrip_source(adapter, source):
    scene = _scene()
    scene.add_source(source)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    return rebuilt.sources[0]


# --- temporal profiles -------------------------------------------------------

def test_point_dipole_cw(adapter):
    src = mw.PointDipole(position=(0.1, 0.2, 0.3), polarization="Ez", width=0.03,
                         source_time=mw.CW(frequency=2e9, amplitude=1.5, phase=0.5), name="d_cw")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_point_dipole_uses_world_position_when_parented(adapter):
    from wt_maxwell.adapter.source_map import SourceMap

    scene = _scene()
    studio = adapter.to_studio(scene)
    parent = SceneObject(name="Field Parent", mesh_type="Empty")
    parent.get_component("Transform").position = [1.0, 2.0, 3.0]
    source = SourceMap.to_studio(mw.PointDipole(
        position=(0.1, 0.2, 0.3), polarization="Ez",
        source_time=mw.CW(frequency=1e9), name="parented"))
    studio.add_object(parent)
    studio.add_object(source)
    studio.set_parent(source.id, parent.id, keep_local_transform=True)

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.sources) == 1
    assert tuple(float(v) for v in rebuilt.sources[0].position) == pytest.approx((1.1, 2.2, 3.3))


def test_point_dipole_gaussian_pulse(adapter):
    src = mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ex",
                         source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8, amplitude=2.0,
                                                      phase=0.1, delay=5e-9), name="d_gp")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_point_dipole_gaussian_pulse_auto_delay(adapter):
    # delay=None -> auto-computed; round-trip preserves the concrete computed delay.
    src = mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ey",
                         source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8), name="d_gp_auto")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_point_dipole_ricker(adapter):
    src = mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez",
                         source_time=mw.RickerWavelet(frequency=1e9, amplitude=1.0), name="d_ricker")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_point_dipole_vector_polarization(adapter):
    src = mw.PointDipole(position=(0.0, 0.0, 0.0), polarization=(0.6, 0.0, 0.8),
                         source_time=mw.CW(frequency=1e9), name="d_vec")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_point_dipole_no_source_time(adapter):
    src = mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez", name="d_none")
    rebuilt = _roundtrip_source(adapter, src)
    assert rebuilt.source_time is None
    assert_source_equal(src, rebuilt)


# --- plane wave (soft + TFSF) ------------------------------------------------

def test_plane_wave_soft(adapter):
    src = mw.PlaneWave(direction=(0.0, 0.0, 1.0), polarization=(1.0, 0.0, 0.0),
                       source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8), name="pw_soft")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_plane_wave_tfsf(adapter):
    src = mw.PlaneWave(direction=(0.0, 0.0, 1.0), polarization=(1.0, 0.0, 0.0),
                       source_time=mw.CW(frequency=1e9),
                       injection=mw.TFSF(bounds=((-0.5, 0.5), (-0.5, 0.5), (-0.4, 0.6))),
                       injection_axis="z", name="pw_tfsf")
    assert_source_equal(src, _roundtrip_source(adapter, src))


# --- gaussian beam -----------------------------------------------------------

def test_gaussian_beam(adapter):
    src = mw.GaussianBeam(direction=(0.0, 0.0, 1.0), polarization=(1.0, 0.0, 0.0),
                          beam_waist=0.3, focus=(0.0, 0.0, 0.1),
                          source_time=mw.CW(frequency=2e9), name="beam")
    assert_source_equal(src, _roundtrip_source(adapter, src))


# --- mode source -------------------------------------------------------------

def test_mode_source(adapter):
    src = mw.ModeSource(position=(0.0, 0.0, 0.2), size=(1.0, 1.0, 0.0), mode_index=1,
                        direction="-", polarization="Ex",
                        source_time=mw.CW(frequency=1e9), name="mode")
    assert_source_equal(src, _roundtrip_source(adapter, src))


def test_mode_source_uses_world_position_when_parented(adapter):
    from wt_maxwell.adapter.source_map import SourceMap

    scene = _scene()
    studio = adapter.to_studio(scene)
    parent = SceneObject(name="Field Parent", mesh_type="Empty")
    parent.get_component("Transform").position = [0.0, 0.0, 0.5]
    source = SourceMap.to_studio(mw.ModeSource(
        position=(0.0, 0.0, 0.2), size=(1.0, 1.0, 0.0),
        source_time=mw.CW(frequency=1e9), name="mode_parented"))
    studio.add_object(parent)
    studio.add_object(source)
    studio.set_parent(source.id, parent.id, keep_local_transform=True)

    rebuilt = adapter.to_platform(studio)

    assert len(rebuilt.sources) == 1
    assert tuple(float(v) for v in rebuilt.sources[0].position) == pytest.approx((0.0, 0.0, 0.7))


def test_mode_source_auto_polarization(adapter):
    # polarization="auto" resolves to a concrete axis; round-trip preserves that axis.
    src = mw.ModeSource(position=(0.0, 0.0, 0.0), size=(1.0, 0.0, 1.0), mode_index=0,
                        source_time=mw.CW(frequency=1e9), name="mode_auto")
    rebuilt = _roundtrip_source(adapter, src)
    assert str(rebuilt.polarization_axis) == str(src.polarization_axis)


# --- multiple sources --------------------------------------------------------

def test_multiple_sources(adapter):
    scene = _scene()
    scene.add_source(mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez",
                                    source_time=mw.CW(frequency=1e9), name="a"))
    scene.add_source(mw.PlaneWave(source_time=mw.GaussianPulse(frequency=1e9, fwidth=1e8), name="b"))
    scene.add_source(mw.ModeSource(position=(0.0, 0.0, 0.3), size=(1.0, 1.0, 0.0),
                                   source_time=mw.CW(frequency=1e9), name="c"))
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    assert_sources_equal(scene.sources, rebuilt.sources)


def test_solver_creates_default_fdtd_source_when_scene_has_none(adapter):
    scene = _scene()
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver.frequencies = [1e9]

    created = solver._ensure_default_source()
    rebuilt = adapter.to_platform(studio)

    assert created is True
    assert len(rebuilt.sources) == 1
    assert str(rebuilt.sources[0].kind) == "point_dipole"
    assert str(rebuilt.sources[0].source_time.kind) == "gaussian_pulse"


def test_solver_default_source_is_not_duplicated(adapter):
    scene = _scene()
    scene.add_source(mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez",
                                    source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8),
                                    name="existing"))
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")

    created = solver._ensure_default_source()
    rebuilt = adapter.to_platform(studio)

    assert created is False
    assert len(rebuilt.sources) == 1
    assert rebuilt.sources[0].name == "existing"
