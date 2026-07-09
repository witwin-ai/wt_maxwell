"""M4 (live, needs a working solver): solve + field visualization.

Loads a maxwell scene, round-trips it through the adapter, re-runs
``Simulation.fdtd`` via ``SolveRunner``, and asserts a field is produced. Also
checks the 2D slice extraction and the 3D viewport volume registration. The whole
suite skips (needs-user-verification) if the solver can't run in this environment.
"""
import ast
import hashlib
import os
from pathlib import Path

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


def test_solver_host_does_not_probe_mesh_sdf_before_serve():
    source = Path(__file__).resolve().parents[1] / "solver_host.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    module_calls = [
        node.value.func
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    call_names = [
        func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        for func in module_calls
    ]

    assert "_ensure_mesh_sdf_native_ready" not in call_names


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
    import wt_volume.components.volume  # noqa: F401
    from witwin_server import Scene
    from witwin_server.features.platform.bridge import FieldViz

    target = Scene()
    obj = FieldViz.show_3d(np.ones((4, 4, 4), dtype=np.float32), scene=target,
                           bounds=((-0.5, 0.5), (-0.5, 0.5), (-0.5, 0.5)), name="Ez Volume")
    assert obj.get_component("VolumeRenderer") is not None
    assert obj.id in target.objects


def test_maxwell_solver_volume_stays_on_solver(adapter, device, tmp_path, monkeypatch):
    import wt_maxwell.components.solver as solver_mod

    scene = _scene(device)
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver._solver_result_handle = "handle-1"
    solver._solver_run_id = "run-1"
    volume_path = tmp_path / "volume.npy"
    np.save(volume_path, np.ones((4, 4, 4), dtype=np.float32), allow_pickle=False)
    digest = hashlib.sha256(volume_path.read_bytes()).hexdigest()

    class FakeSolvers:
        def read_result_ref(self, solver_id, ref):
            assert solver_id == "witwin.maxwell.fdtd"
            assert ref["path"] == str(volume_path)
            return volume_path.read_bytes()

        def query(self, solver_id, result_handle, op, params, **kwargs):
            assert solver_id == "witwin.maxwell.fdtd"
            assert result_handle == "handle-1"
            assert op == "extract_volume"
            return {
                "data": {
                    "resultRef": {
                        "kind": "npy",
                        "path": str(volume_path),
                        "contentHash": f"sha256:{digest}",
                    },
                    "shape": [4, 4, 4],
                    "dtype": "float32",
                }
            }

    before = set(studio.objects)
    monkeypatch.setattr(solver_mod, "api", type("FakeApi", (), {"solvers": FakeSolvers()})())

    msg = solver.show_volume()

    assert msg == "Volume updated"
    assert set(studio.objects) == before
    assert solver._volume_data is not None
    assert str(solver.render_mode) == "Volume"


def test_maxwell_volume_result_ref_rejects_hash_mismatch(tmp_path):
    import wt_maxwell.components.solver as solver_mod

    volume_path = tmp_path / "volume.npy"
    np.save(volume_path, np.ones((2, 2, 2), dtype=np.float32), allow_pickle=False)

    class FakeSolvers:
        def read_result_ref(self, solver_id, ref):
            assert solver_id == "witwin.maxwell.fdtd"
            raise ValueError("resultRef content hash mismatch")

    old_api = solver_mod.api
    solver_mod.api = type("FakeApi", (), {"solvers": FakeSolvers()})()
    with pytest.raises(ValueError, match="content hash mismatch"):
        try:
            solver_mod.MaxwellSolverComponent._load_volume_payload({
                "resultRef": {
                    "kind": "npy",
                    "path": str(volume_path),
                    "contentHash": f"sha256:{'0' * 64}",
                },
                "shape": [2, 2, 2],
            })
        finally:
            solver_mod.api = old_api


def test_maxwell_volume_result_ref_requires_sha256(tmp_path):
    import wt_maxwell.components.solver as solver_mod

    volume_path = tmp_path / "volume.npy"
    np.save(volume_path, np.ones((2, 2, 2), dtype=np.float32), allow_pickle=False)

    with pytest.raises(ValueError, match="contentHash"):
        solver_mod.MaxwellSolverComponent._load_volume_payload({
            "resultRef": {
                "kind": "npy",
                "path": str(volume_path),
            },
            "shape": [2, 2, 2],
        })


def test_maxwell_volume_result_ref_uses_solver_api_loader_for_path_confinement(tmp_path):
    import wt_maxwell.components.solver as solver_mod

    volume_path = tmp_path / "volume.npy"
    np.save(volume_path, np.ones((2, 2, 2), dtype=np.float32), allow_pickle=False)
    digest = hashlib.sha256(volume_path.read_bytes()).hexdigest()

    class FakeSolvers:
        def read_result_ref(self, solver_id, ref):
            assert solver_id == "witwin.maxwell.fdtd"
            raise ValueError("resultRef path must stay inside solver result directory")

    old_api = solver_mod.api
    solver_mod.api = type("FakeApi", (), {"solvers": FakeSolvers()})()
    with pytest.raises(ValueError, match="resultRef path"):
        try:
            solver_mod.MaxwellSolverComponent._load_volume_payload({
                "resultRef": {
                    "kind": "npy",
                    "path": str(volume_path),
                    "contentHash": f"sha256:{digest}",
                },
                "shape": [2, 2, 2],
            })
        finally:
            solver_mod.api = old_api


def test_maxwell_component_uses_solver_api_for_solve(adapter, device, monkeypatch):
    import wt_maxwell.components.solver as solver_mod

    scene = _scene(device)
    studio = adapter.to_studio(scene)
    settings = next(obj for obj in studio.objects.values() if obj.name == "Maxwell Settings")
    solver = settings.get_component("MaxwellSolver")
    solver.frequencies = [1e9]
    solver.show_3d_field = False
    timeline_calls = []

    class FakeTimelineManager:
        def apply_to_scene(self):
            timeline_calls.append("apply")

    studio.timeline_manager = FakeTimelineManager()

    class FakeRun:
        status = "succeeded"
        outputs = {"resultHandle": "handle-1"}
        run_id = "run-1"
        error = None

    class FakeSolvers:
        def __init__(self):
            self.solve_kwargs = None
            self.queries = []

        def solve(self, solver_id, **kwargs):
            self.solve_kwargs = {"solver_id": solver_id, "timeline_calls": list(timeline_calls), **kwargs}
            return FakeRun()

        def query(self, solver_id, result_handle, op, params, **kwargs):
            self.queries.append((solver_id, result_handle, op, params, kwargs))
            return {
                "data": {
                    "data": [[1.0, 2.0], [3.0, 4.0]],
                    "extent": [-1.0, 1.0, -1.0, 1.0],
                    "xlabel": "x",
                    "ylabel": "y",
                }
            }

    fake = FakeSolvers()
    notifications = {"success": [], "error": []}

    class FakeNotifications:
        @staticmethod
        def success(title, message):
            notifications["success"].append((title, message))

        @staticmethod
        def error(title, message):
            notifications["error"].append((title, message))

    monkeypatch.setattr(solver_mod, "api", type("FakeApi", (), {"solvers": fake})())
    monkeypatch.setattr(solver_mod, "Notifications", FakeNotifications)

    msg = solver.solve()

    assert msg == "Solve complete"
    assert solver._solver_result_handle == "handle-1"
    assert fake.solve_kwargs["solver_id"] == "witwin.maxwell.fdtd"
    assert fake.solve_kwargs["timeline_calls"] == ["apply"]
    assert fake.solve_kwargs["scene"] is studio
    assert "surface_progress" not in fake.solve_kwargs
    assert fake.queries[0][2] == "extract_slice"
    assert notifications["success"] == [("Maxwell", "FDTD solve complete")]
    assert notifications["error"] == []


def test_mesh_sdf_runtime_env_adds_conda_and_cuda_paths(solve_mod, monkeypatch, tmp_path):
    conda = tmp_path / "conda"
    cuda = tmp_path / "cuda"
    for path in (
        conda / "Library" / "bin",
        conda / "Library" / "lib",
        conda / "Library" / "include",
        conda / "Scripts",
        cuda / "bin",
        cuda / "lib" / "x64",
        cuda / "include",
    ):
        path.mkdir(parents=True)
    (conda / "python.exe").write_text("", encoding="utf-8")

    monkeypatch.setattr(solve_mod.sys, "executable", str(conda / "python.exe"))
    monkeypatch.setenv("CUDA_PATH", str(cuda))
    monkeypatch.setenv("PATH", "old-path")
    monkeypatch.setenv("LIB", "old-lib")
    monkeypatch.setenv("INCLUDE", "old-include")

    solve_mod._ensure_mesh_sdf_runtime_env()

    assert str(conda / "Library" / "bin") in os.environ["PATH"]
    assert str(conda / "Library" / "lib") in os.environ["LIB"]
    assert str(cuda / "lib" / "x64") in os.environ["LIB"]
    assert str(cuda / "include") in os.environ["INCLUDE"]


def test_mesh_sdf_native_ready_adds_env_and_requires_available_module(solve_mod, monkeypatch):
    from witwin.core.geometry import mesh_sdf

    calls = []

    def native_available():
        calls.append("probe")
        return True

    monkeypatch.setattr(solve_mod, "_ensure_mesh_sdf_runtime_env", lambda: calls.append("env"))
    monkeypatch.setattr(mesh_sdf, "_mesh_sdf_available", native_available)

    solve_mod._ensure_mesh_sdf_native_ready()

    assert calls == ["env", "probe"]


def test_mesh_sdf_native_ready_raises_when_module_unavailable(solve_mod, monkeypatch):
    from witwin.core.geometry import mesh_sdf

    calls = []

    def native_unavailable():
        calls.append("probe")
        return False

    monkeypatch.setattr(solve_mod, "_ensure_mesh_sdf_runtime_env", lambda: calls.append("env"))
    monkeypatch.setattr(mesh_sdf, "_mesh_sdf_available", native_unavailable)

    with pytest.raises(RuntimeError, match="Native CUDA mesh SDF module is not available"):
        solve_mod._ensure_mesh_sdf_native_ready()

    assert calls == ["env", "probe"]
