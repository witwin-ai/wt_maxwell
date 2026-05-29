"""M4 (live, needs a working solver): solve + field visualization.

Loads a maxwell scene, round-trips it through the adapter, re-runs
``Simulation.fdtd`` via ``SolveRunner``, and asserts a field is produced. Also
checks the 2D slice extraction and the 3D viewport volume registration. The whole
suite skips (needs-user-verification) if the solver can't run in this environment.
"""
import witwin.maxwell as mw
import numpy as np
import pytest


def _scene(device, source_time=None):
    source_time = source_time or mw.CW(frequency=1e9)
    scene = mw.Scene(
        domain=mw.Domain(bounds=((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5))),
        grid=mw.GridSpec.uniform(0.1), boundary=mw.BoundarySpec.pml(num_layers=8), device=device)
    scene.add_structure(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.2, 0.2, 0.2)), mw.Material(eps_r=4.0), name="b"))
    scene.add_source(mw.PointDipole(position=(-0.2, 0.0, 0.0), polarization="Ez",
                                    source_time=source_time))
    scene.add_monitor(mw.PlaneMonitor("slice", axis="z", position=0.0))
    return scene


def test_solve_runner_rejects_fdfd(solve_mod):
    with pytest.raises(ValueError, match="only supports FDTD"):
        solve_mod.SolveRunner.build(object(), solve_mod.SolveConfig(method="fdfd", frequencies=(1e9,)))


def test_solver_requests_full_field_dft_by_default(adapter):
    scene = _scene("cuda")
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver.frequencies = [1e9]

    config = solver._solve_config()

    assert config.full_field_dft is True


def test_fdtd_roundtrip_runs(adapter, solve_mod, device, solver_ready):
    scene = _scene(device, source_time=mw.GaussianPulse(frequency=1e9, fwidth=3e8))
    studio = adapter.to_studio(scene)
    config = solve_mod.SolveConfig(method="fdtd", frequencies=(1e9,), time_steps=300)
    rebuilt = solve_mod.SolveRunner.run(studio, config)
    assert rebuilt.E.z is not None


def test_fdtd_multifreq_runs(adapter, solve_mod, device, solver_ready):
    scene = _scene(device, source_time=mw.GaussianPulse(frequency=1e9, fwidth=3e8))
    studio = adapter.to_studio(scene)
    config = solve_mod.SolveConfig(method="fdtd", frequencies=(1e9, 1.5e9), time_steps=300)
    result = solve_mod.SolveRunner.run(studio, config)
    assert result.E.z is not None
    assert tuple(result.frequencies) == (1e9, 1.5e9)


def test_slice_extraction(adapter, solve_mod, device, solver_ready):
    scene = _scene(device, source_time=mw.GaussianPulse(frequency=1e9, fwidth=3e8))
    studio = adapter.to_studio(scene)
    result = solve_mod.SolveRunner.run(studio, solve_mod.SolveConfig(method="fdtd", frequencies=(1e9,), time_steps=300))
    sl = solve_mod.SliceExtractor.extract(result, axis="z", position=0.0, component="Ez")
    import numpy as np
    assert sl.data.ndim == 2
    assert len(sl.extent) == 4
    assert sl.extent[1] > sl.extent[0] and sl.extent[3] > sl.extent[2]  # ordered axes
    assert np.isfinite(sl.data).all()
    assert sl.xlabel and sl.ylabel


def test_slice_log_scale(adapter, solve_mod, device, solver_ready):
    scene = _scene(device, source_time=mw.GaussianPulse(frequency=1e9, fwidth=3e8))
    studio = adapter.to_studio(scene)
    result = solve_mod.SolveRunner.run(studio, solve_mod.SolveConfig(method="fdtd", frequencies=(1e9,), time_steps=300))
    sl = solve_mod.SliceExtractor.extract(result, axis="z", position=0.0, component="Ez", log_scale=True)
    assert sl.data.ndim == 2


def test_show_3d_volume_registers_object():
    from witwin_server import Scene
    from witwin_server.features.platform.bridge import FieldViz

    target = Scene()
    obj = FieldViz.show_3d(np.ones((4, 4, 4), dtype=np.float32), scene=target,
                           bounds=((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5)), name="Ez Volume")
    assert obj.get_component("VolumeRenderer") is not None
    assert obj.id in target.objects


def test_maxwell_solver_volume_stays_on_solver(adapter, solve_mod, device, monkeypatch):
    scene = _scene(device)
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")

    before = set(studio.objects)
    solver._result = object()
    monkeypatch.setattr(
        solve_mod.SliceExtractor,
        "volume",
        staticmethod(lambda result, **kwargs: np.ones((4, 4, 4), dtype=np.float32)),
    )
    msg = solver.show_volume()

    assert msg == "Volume updated"
    assert set(studio.objects) == before
    assert solver._volume_data is not None
    assert str(solver.render_mode) == "Volume"
