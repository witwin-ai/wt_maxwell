import importlib.util
from pathlib import Path

import witwin.studio as ws

PROJECT = Path(__file__).resolve().parents[1]


def load_script():
    spec = importlib.util.spec_from_file_location("prepare_em", PROJECT / "scripts" / "prepare_em.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_source_frequency_matches_the_solve_frequency():
    scene = ws.open_project(PROJECT).scene()
    script = load_script()
    solver = script.find(scene, "MaxwellSolver").components["MaxwellSolver"]
    dipole = script.find(scene, "PointDipoleSource").components["PointDipoleSource"]
    assert dipole["st_frequency"] in solver["frequencies"]


def test_prepare_script_reports_ready(capsys):
    assert load_script().main([]) == 0
    assert "Ready to solve" in capsys.readouterr().out


def test_scene_opens_on_the_bench_stage():
    # A 1.2 m FDTD domain is device scale; World would show it as a speck.
    header = (PROJECT / "scenes" / "main.wtscene").read_text(encoding="utf-8").split("[[entity]]", 1)[0]
    assert 'stage = "bench"' in header
