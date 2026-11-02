"""Model-generator tests: transmission lines, passives, connectors, packages and periodic structures.

Every generator under ``models/{lines,passives,connectors,packages,periodic}``
is run through the SDK model runner (a child process, as Studio runs it)
with its defaults and, where it has one, with its ``design()`` output. Each
run must succeed, validate with no ERROR and carry its port anchors. The
design formulas are checked against published values (Pozar, Microwave
Engineering, 4th ed.; standard waveguide tables), and the manifest is
checked against the files on disk.

Needs the witwin-studio SDK (``witwin.studio``) with its CAD, layout and
geometry extras (build123d, shapely, manifold3d); the module is skipped
without them. The maxwell solver is not needed.
"""
from __future__ import annotations

import math
import runpy
import sys
from pathlib import Path

import pytest

pytest.importorskip("witwin.studio")
pytest.importorskip("build123d")
pytest.importorskip("shapely")
pytest.importorskip("manifold3d")
tomllib = pytest.importorskip("tomllib")

from witwin.studio.geometry import run_model  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("lines", "passives", "connectors", "packages", "periodic")
ID_PREFIX = {"lines": "line", "passives": "passive", "connectors": "connector", "packages": "package",
             "periodic": "periodic"}
MODEL_FILES = sorted(p for folder in FOLDERS for p in (ROOT / "models" / folder).glob("*.py")
                     if not p.name.startswith("_"))
# Models whose only ports are Floquet ports or pins still mark them with kind "port".
MIN_PORTS = {"waveguide_tee": 3, "coupled_microstrip": 4, "branch_line": 4, "wilkinson": 3}


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _namespace(path: Path) -> dict:
    """Execute a model file in-process (its folder importable), as the SDK's ``load_model`` does."""
    folder = str(path.parent)
    sys.path.insert(0, folder)
    try:
        return runpy.run_path(str(path), run_name="__witwin_model__")
    finally:
        sys.path.remove(folder)


def _formulas():
    return _namespace(ROOT / "models" / "lines" / "_lines_formulas.py")


def _anchors(run) -> list:
    out = list(run.manifest.get("anchors") or [])
    for body in run.bodies:
        out += body.get("anchors") or []
    return out


def _check_run(run, path: Path, label: str):
    assert run.ok, f"{label}: run failed: {run.manifest.get('error') or run.manifest}"
    validation = run.validation
    assert validation["error_count"] == 0, f"{label}: validation errors {validation['issues']}"
    ports = [a for a in _anchors(run) if a.get("kind") == "port"]
    assert len(ports) >= MIN_PORTS.get(path.stem, 1), f"{label}: port anchors {[a['name'] for a in ports]}"
    names = [a["name"] for a in ports]
    assert len(names) == len(set(names)), f"{label}: duplicate port names {names}"
    for anchor in ports:
        normal = anchor.get("normal")
        assert normal is not None and abs(math.hypot(*normal) - 1.0) < 1e-6, f"{label}: {anchor}"


# ---------------------------------------------------------------- manifest
def _manifest_models() -> list:
    with open(ROOT / "witwin.toml", "rb") as f:
        models = tomllib.load(f)["contributes"]["models"]
    return [m for m in models if any(m["path"].startswith(f"models/{folder}/") for folder in FOLDERS)]


def test_every_model_file_has_one_manifest_entry():
    entries = _manifest_models()
    paths = [m["path"] for m in entries]
    assert sorted(paths) == sorted(_rel(p) for p in MODEL_FILES)
    assert len(paths) == len(set(paths))


def test_manifest_entries_resolve_and_follow_the_id_scheme():
    entries = _manifest_models()
    ids = [m["id"] for m in entries]
    assert len(ids) == len(set(ids))
    for m in entries:
        path = ROOT / m["path"]
        assert path.is_file(), m
        folder = Path(m["path"]).parent.name
        assert m["id"] == f"witwin.maxwell.{ID_PREFIX[folder]}.{path.stem}", m
        assert m["title"] and m["category"] and m["tags"], m


# ------------------------------------------------------------- generators
@pytest.mark.parametrize("path", MODEL_FILES, ids=_rel)
def test_generator_contract(path):
    ns = _namespace(path)
    doc = (ns.get("__doc__") or "").strip()
    assert doc and doc.splitlines()[0].endswith("."), "first docstring line must be a one-sentence summary"
    assert ns["CONFIG"]["up"] == "z" and ns["CONFIG"]["unit"] in ("mm", "um")
    assert ns["CONFIG"].get("grid"), "CONFIG['grid'] states the grid the model validates at"
    if "design" in ns:
        assert "DESIGN_SPEC" in ns
        out = ns["design"]()
        assert set(out) <= set(ns["PARAMS"]), f"design() returns keys that are not parameters: {set(out) - set(ns['PARAMS'])}"
        assert ns["design"]({}) == out, "missing spec keys must take the defaults"
        with pytest.raises(KeyError):
            ns["design"]({"no_such_key": 1.0})
        for key, spec in ns["DESIGN_SPEC"].items():
            assert spec.unit or any(word in spec.description for word in UNITLESS_WORDS),                 f"DESIGN_SPEC[{key!r}] must state its unit (SDK unit, or one of {UNITLESS_WORDS} in the description)"


# Units the SDK has no key for are named in the description instead.
UNITLESS_WORDS = ("ohm", "dB", "dimensionless", "count", "flag", "guided wavelengths")
FREQUENCY_UNITS = ("Hz", "kHz", "MHz", "GHz", "THz")
FREQUENCY_NAMES = ("f0", "fc", "f_low", "f_high")
ALL_MODEL_FILES = sorted(p for p in (ROOT / "models").glob("*/*.py") if not p.name.startswith("_"))


@pytest.mark.parametrize("path", ALL_MODEL_FILES, ids=_rel)
def test_frequencies_are_si_hz(path):
    # One frequency unit across every generator (antennas included), so an
    # agent can pass f0=5e9 to any of them, to PARAMS and DESIGN_SPEC alike.
    ns = _namespace(path)
    for table in ("PARAMS", "DESIGN_SPEC"):
        for key, spec in (ns.get(table) or {}).items():
            if key in FREQUENCY_NAMES or spec.unit in FREQUENCY_UNITS:
                assert spec.unit == "Hz", f"{table}[{key!r}] has unit {spec.unit!r}, expected 'Hz'"


@pytest.mark.parametrize("path", MODEL_FILES, ids=_rel)
def test_generator_defaults_build_cleanly(path, tmp_path):
    run = run_model(path, out_dir=tmp_path, brep=False)
    _check_run(run, path, "defaults")


DESIGNED = [p for p in MODEL_FILES if "def design(" in p.read_text(encoding="utf-8")]


@pytest.mark.parametrize("path", DESIGNED, ids=_rel)
def test_generator_design_builds_cleanly(path, tmp_path):
    params = _namespace(path)["design"]()
    run = run_model(path, params=params, out_dir=tmp_path, brep=False)
    _check_run(run, path, f"design {params}")


# --------------------------------------------------------- design formulas
def test_microstrip_50_ohm_on_fr4():
    f = _formulas()
    w = f["microstrip_width"](50.0, 1.6, 4.4, 0.035)
    assert w == pytest.approx(3.0, rel=0.03)
    z0, eps_eff = f["microstrip"](w, 1.6, 4.4, 0.035)
    assert z0 == pytest.approx(50.0, rel=1e-4)
    assert 3.0 < eps_eff < 3.6
    ns = _namespace(ROOT / "models" / "lines" / "microstrip.py")
    assert ns["design"]({"z0": 50, "h": 1.6, "eps_r": 4.4, "t": 0.035})["w"] == pytest.approx(3.0, rel=0.03)


def test_microstrip_matches_pozar_example_3_7():
    # Pozar Ex. 3.7: 50 ohm on h = 0.127 cm, eps_r = 2.20 -> W = 0.391 cm (t = 0).
    assert _formulas()["microstrip_width"](50.0, 1.27, 2.2) == pytest.approx(3.91, rel=0.01)


def test_stripline_matches_pozar_example_3_5():
    # Pozar Ex. 3.5: 50 ohm, b = 0.32 cm, eps_r = 2.20 -> W = 0.266 cm.
    f = _formulas()
    w = f["stripline_width"](50.0, 3.2, 2.2)
    assert w == pytest.approx(2.66, rel=0.01)
    assert f["stripline"](w, 3.2, 2.2) == pytest.approx(50.0, rel=1e-4)


@pytest.mark.parametrize("grounded", [False, True])
def test_cpw_gap_round_trips(grounded):
    f = _formulas()
    gap = f["cpw_gap"](50.0, 1.0, 1.6, 4.4, grounded)
    z0, eps_eff = f["cpw"](1.0, gap, 1.6, 4.4, grounded)
    assert z0 == pytest.approx(50.0, rel=1e-4)
    assert 1.0 < eps_eff < 4.4


def test_cpw_infinite_substrate_limit():
    # Thick substrate: eps_eff -> (eps_r + 1)/2 for the ungrounded CPW (Simons 2001, eq. 2.29).
    _, eps_eff = _formulas()["cpw"](0.1, 0.05, 100.0, 9.8)
    assert eps_eff == pytest.approx((9.8 + 1) / 2, rel=0.01)


def test_coax_50_ohm_ptfe():
    f = _formulas()
    d = f["coax_inner"](50.0, 4.1, 2.1)
    assert d == pytest.approx(1.2245, abs=1e-3)      # Z0 = (eta0 / 2 pi sqrt(eps_r)) ln(D/d)
    assert f["coax"](d, 4.1, 2.1) == pytest.approx(50.0, rel=1e-9)


def test_rect_waveguide_cutoff_wr90():
    # WR-90: a = 22.86 mm, TE10 cutoff 6.557 GHz.
    assert _formulas()["rect_waveguide_cutoff"](22.86e-3, 10.16e-3) / 1e9 == pytest.approx(6.557, rel=1e-3)


def test_circular_waveguide_radius_sits_between_te11_and_tm01():
    f = _formulas()
    r = f["circular_waveguide_radius"](10e9)
    te11, tm01 = f["circular_waveguide_cutoffs"](r)
    assert te11 < 10e9 < tm01


def test_coupled_line_impedances_10_db():
    # Pozar eq. 7.79 at C = 10 dB, Z0 = 50 ohm: Z0e = 69.37, Z0o = 36.04.
    f = _formulas()
    z0e, z0o = f["coupled_impedances"](50.0, f["db_to_voltage_coupling"](10.0))
    assert (z0e, z0o) == (pytest.approx(69.37, abs=0.02), pytest.approx(36.04, abs=0.02))
    w, s = f["coupled_microstrip_design"](z0e, z0o, 1.6, 4.4)
    ze, zo = f["coupled_microstrip"](w, s, 1.6, 4.4)
    assert (ze, zo) == (pytest.approx(z0e, rel=1e-3), pytest.approx(z0o, rel=1e-3))


# g0 .. g(n+1), g0 = 1 (Matthaei, Young & Jones 1964; Pozar sec. 8.3).
@pytest.mark.parametrize("n, ripple, expected", [
    (3, 0.0, [1.0, 1.0, 2.0, 1.0, 1.0]),                       # Butterworth (Pozar, maximally flat table)
    (3, 0.5, [1.0, 1.5963, 1.0967, 1.5963, 1.0]),              # 0.5 dB equal ripple (Pozar table)
    (6, 0.0, [1.0, 0.5176, 1.4142, 1.9318, 1.9318, 1.4142, 0.5176, 1.0]),
])
def test_lowpass_prototype(n, ripple, expected):
    g = _formulas()["lowpass_prototype"](n, ripple)
    assert g == pytest.approx(expected, abs=2e-4)


def test_stepped_impedance_lpf_matches_pozar_example_8_6():
    ns = _namespace(ROOT / "models" / "passives" / "stepped_impedance_lpf.py")
    from types import SimpleNamespace

    p = SimpleNamespace(**{k: v.value for k, v in ns["PARAMS"].items()})
    degrees = [s["deg"] for s in ns["sections"](p)]
    assert degrees == pytest.approx([11.86, 33.76, 44.28, 46.12, 32.41, 12.36], abs=0.02)


def test_wilkinson_and_branch_line_quarter_waves():
    from types import SimpleNamespace

    wilk = _namespace(ROOT / "models" / "passives" / "wilkinson.py")
    d = wilk["design"]()
    p = SimpleNamespace(**{**{k: v.value for k, v in wilk["PARAMS"].items()}, **d})
    z_arm, _ = _formulas()["microstrip"](p.w_arm, p.h, p.eps_r, p.t)
    assert z_arm == pytest.approx(50.0 * math.sqrt(2.0), rel=0.01)
    branch = _namespace(ROOT / "models" / "passives" / "branch_line.py")
    p = SimpleNamespace(**{**{k: v.value for k, v in branch["PARAMS"].items()}, **branch["design"]()})
    z_series, _ = _formulas()["microstrip"](p.w_series, p.h, p.eps_r, p.t)
    assert z_series == pytest.approx(50.0 / math.sqrt(2.0), rel=0.01)


def test_sma_pin_is_50_ohm_in_ptfe():
    d = _namespace(ROOT / "models" / "connectors" / "sma_edge.py")["design"]()
    assert d["d_pin"] == pytest.approx(1.2544, abs=1e-3)


def test_photonic_crystal_scale_invariance():
    ns = _namespace(ROOT / "models" / "periodic" / "photonic_crystal_slab.py")
    assert ns["design"]() == {"a": pytest.approx(0.42, abs=1e-3), "r": pytest.approx(0.126, abs=1e-3)}
    d = ns["design"]({"wavelength": 3.1})
    assert d["a"] == pytest.approx(2 * ns["design"]()["a"], rel=1e-3)


@pytest.mark.parametrize("lattice, nx, ny, holes", [(0, 3, 2, 6), (1, 2, 2, 8)])
def test_photonic_crystal_slab_volume(lattice, nx, ny, holes, tmp_path):
    # Half holes on the x faces must add up to whole holes per lattice point.
    a, r, t = 0.42, 0.126, 0.22
    run = run_model(ROOT / "models" / "periodic" / "photonic_crystal_slab.py", out_dir=tmp_path, brep=False,
                    params={"lattice": lattice, "nx": nx, "ny": ny})
    assert run.ok
    py = ny * a * (1 if lattice == 0 else math.sqrt(3.0))
    expected = (nx * a * py - holes * math.pi * r * r) * t * 1e-18     # m^3
    volume = run.bodies[0]["stats"]["volume"]
    assert volume == pytest.approx(expected, rel=0.01)


@pytest.mark.parametrize("params", [{"aperture": 1}, {"aperture": 1, "substrate": 0}, {"substrate": 0}])
def test_fss_cell_variants(params, tmp_path):
    path = ROOT / "models" / "periodic" / "fss_cell.py"
    run = run_model(path, params=params, out_dir=tmp_path, brep=False)
    _check_run(run, path, str(params))
    assert {"cell_xmin", "cell_xmax", "cell_ymin", "cell_ymax"} <= {a["name"] for a in _anchors(run)}


def test_design_takes_si_frequency(tmp_path):
    # The case that used to fail: f0 = 5e9 (Hz) passed to the Wilkinson design and build.
    path = ROOT / "models" / "passives" / "wilkinson.py"
    params = _namespace(path)["design"]({"f0": 5e9})
    assert params["f0"] == 5e9
    run = run_model(path, params=params, out_dir=tmp_path, brep=False)
    _check_run(run, path, f"design {params}")
    lpf = _namespace(ROOT / "models" / "passives" / "stepped_impedance_lpf.py")["design"]({"fc": 2.5e9})
    assert lpf["fc"] == 2.5e9 and lpf["w_low"] == pytest.approx(11.2417, abs=1e-3)
    loop = _namespace(ROOT / "models" / "periodic" / "square_loop.py")["design"]({"f0": 10e9})
    assert loop["loop"] == pytest.approx(5.0612, abs=1e-3)
