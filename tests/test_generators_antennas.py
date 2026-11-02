"""Antenna generators (models/antennas): run, validate, check dimensions and the manifest.

Each generator runs through the SDK model loader with its defaults and with
``design()`` at two frequencies (or bands). Every run must validate with no
ERROR at the generator's own ``suggested_grid``, and must expose a port anchor.
Key dimensions are checked against the textbook formulas written out here
again, independently of ``_antenna_common.py``.

Needs only the geometry stack (``witwin.studio`` SDK, build123d, shapely,
trimesh, manifold3d); the maxwell solver is not used.
"""
import math
import runpy
import sys
import tomllib
from pathlib import Path

import pytest

pytest.importorskip("witwin.studio.geometry")
pytest.importorskip("build123d")
pytest.importorskip("shapely")
pytest.importorskip("trimesh")
pytest.importorskip("manifold3d")

from witwin.studio.geometry import load_model, run_model  # noqa: E402

PLUGIN = Path(__file__).resolve().parents[1]
MODELS = PLUGIN / "models" / "antennas"
C0 = 299_792_458.0

GENERATORS = (
    "patch", "patch_probe", "circular_patch", "aperture_coupled_patch", "dipole", "monopole", "pifa", "ifa",
    "yagi", "lpda", "helix", "spiral", "pyramidal_horn", "conical_horn", "corrugated_horn", "vivaldi", "slot",
    "reflector", "linear_array", "planar_array",
)

# Two design points per generator: the spec keys that set the frequency.
BANDS = ("lpda", "spiral", "vivaldi")
DESIGN_POINTS = {
    "lpda": ({"f_low": 0.4e9, "f_high": 1.2e9}, {"f_low": 1e9, "f_high": 6e9}),
    "spiral": ({"f_low": 1e9, "f_high": 6e9}, {"f_low": 4e9, "f_high": 18e9}),
    "vivaldi": ({"f_low": 2e9, "f_high": 8e9}, {"f_low": 6e9, "f_high": 18e9}),
}
HIGH_BAND = ("pyramidal_horn", "conical_horn", "corrugated_horn", "reflector")
for _name in GENERATORS:
    if _name in HIGH_BAND:
        DESIGN_POINTS[_name] = ({"f0": 8e9}, {"f0": 24e9})
    elif _name not in BANDS:
        DESIGN_POINTS[_name] = ({"f0": 1.575e9}, {"f0": 5.8e9})


def wavelength_mm(f, eps=1.0):
    return C0 / (f * math.sqrt(eps)) * 1e3


def namespace(name):
    """The generator module's globals (its folder must be importable for _antenna_common)."""
    sys.path.insert(0, str(MODELS))
    try:
        return runpy.run_path(str(MODELS / f"{name}.py"))
    finally:
        sys.path.remove(str(MODELS))


def run(name, overrides=None):
    """(values, output, report) of one run, validated at the generator's suggested grid."""
    model = load_model(MODELS / f"{name}.py")
    values, _ = model.resolve(overrides or {})
    out = model.run(values)
    grid_mm = namespace(name)["suggested_grid"](values)
    return values, out, out.validate(grid=grid_mm * 1e-3)


def port_anchors(out):
    found = [a for body in out.bodies for a in body.anchors if a.kind == "port"]
    return found + [a for a in out.anchors if a.kind == "port"]


def assert_valid(name, out, report):
    assert out.bodies, f"{name}: no bodies"
    assert report.ok, f"{name}: {report.summary()}"
    ports = port_anchors(out)
    assert ports, f"{name}: no port anchor"
    assert any(a.name == "feed" or a.name.startswith("feed_") for a in ports), f"{name}: no feed port"


# --- run and validate ---------------------------------------------------------

@pytest.mark.parametrize("name", GENERATORS)
def test_defaults_validate(name):
    _, out, report = run(name)
    assert_valid(name, out, report)


@pytest.mark.parametrize("name,point", [(n, i) for n in GENERATORS for i in (0, 1)])
def test_design_validates(name, point):
    spec = DESIGN_POINTS[name][point]
    overrides = namespace(name)["design"](spec)
    _, out, report = run(name, overrides)
    assert_valid(name, out, report)


@pytest.mark.parametrize("name", [n for n in GENERATORS if n not in ("linear_array", "planar_array")])
def test_defaults_match_design(name):
    """PARAMS defaults are design() at the default spec, so the default model is a real design."""
    ns = namespace(name)
    for key, value in ns["design"]().items():
        assert ns["PARAMS"][key].value == pytest.approx(value, rel=1e-9, abs=1e-9), f"{name}.{key}"


@pytest.mark.parametrize("name,overrides", [
    ("linear_array", {"feed_network": 1, "n": 8}),
    ("linear_array", {"element": 4, "n": 5}),
    ("planar_array", {"element": 2, "nx": 3, "ny": 3, "lattice": 1, "spacing": 0.6}),
    ("planar_array", {"element": 3}),
])
def test_array_variants(name, overrides):
    _, out, report = run(name, overrides)
    assert_valid(name, out, report)


def test_corporate_feed_has_single_port():
    _, out, _ = run("linear_array", {"feed_network": 1, "n": 4})
    names = sorted(a.name for a in port_anchors(out))
    assert names == ["feed"]


def test_corporate_feed_needs_power_of_two():
    model = load_model(MODELS / "linear_array.py")
    values, _ = model.resolve({"feed_network": 1, "n": 6})
    with pytest.raises(Exception):
        model.run(values)


def test_unknown_design_key_is_rejected():
    with pytest.raises(Exception):
        namespace("patch")["design"]({"frequency": 2e9})


def test_runs_in_child_process():
    """The SDK subprocess runner (what Studio uses) builds and validates a generator."""
    result = run_model(MODELS / "patch.py", grid=0.8e-3, timeout=300)
    assert result.ok, result.error
    assert result.validation["error_count"] == 0
    anchors = {a["name"] for b in result.bodies for a in b.get("anchors", [])}
    assert {"feed", "feed_ref"} <= anchors


# --- key dimensions against the textbook formulas -------------------------------

def balanis_patch(f, er, h):
    """(W, L) in mm, Balanis eqs. 14-6, 14-1, 14-2, 14-7."""
    w = C0 / (2 * f) * math.sqrt(2 / (er + 1)) * 1e3
    eeff = (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 * h / w)
    dl = 0.412 * h * (eeff + 0.3) * (w / h + 0.264) / ((eeff - 0.258) * (w / h + 0.8))
    return w, C0 / (2 * f * math.sqrt(eeff)) * 1e3 - 2 * dl


@pytest.mark.parametrize("name", ["patch", "patch_probe", "aperture_coupled_patch"])
@pytest.mark.parametrize("f0", [1.575e9, 2.45e9, 5.8e9])
def test_patch_size(name, f0):
    d = namespace(name)["design"]({"f0": f0})
    w, length = balanis_patch(f0, d["eps_r"], d["h"])
    assert d["W"] == pytest.approx(w, rel=0.02)
    assert d["L"] == pytest.approx(length, rel=0.02)


@pytest.mark.parametrize("f0", [1.575e9, 2.45e9, 5.8e9])
def test_circular_patch_radius(f0):
    """Balanis eqs. 14-67, 14-68 (cm in the formula)."""
    d = namespace("circular_patch")["design"]({"f0": f0})
    er, h_cm = d["eps_r"], d["h"] / 10
    big_f = 8.791e9 / (f0 * math.sqrt(er))
    a_cm = big_f / math.sqrt(1 + 2 * h_cm / (math.pi * er * big_f) * (math.log(math.pi * big_f / (2 * h_cm)) + 1.7726))
    assert d["a"] == pytest.approx(a_cm * 10, rel=0.02)


@pytest.mark.parametrize("f0", [0.9e9, 2.45e9, 5.8e9])
def test_wire_resonant_lengths(f0):
    lam = wavelength_mm(f0)
    assert 0.45 < namespace("dipole")["design"]({"f0": f0})["length"] / lam < 0.49
    # A 2 mm wire is fat at 5.8 GHz (d = 0.04 lambda), which shortens it to 0.22 lambda.
    assert 0.215 < namespace("monopole")["design"]({"f0": f0})["height"] / lam < 0.245
    assert 0.45 < namespace("slot")["design"]({"f0": f0})["slot_l"] / lam < 0.49
    yagi = namespace("yagi")["design"]({"f0": f0})
    assert yagi["ref_len"] == pytest.approx(0.482 * lam, rel=0.01)
    assert yagi["dir_space"] == pytest.approx(0.25 * lam, rel=0.01)
    assert yagi["dir_len"] < yagi["drv_len"] < yagi["ref_len"]


@pytest.mark.parametrize("f0", [0.9e9, 2.45e9])
def test_pifa_and_ifa_quarter_wave(f0):
    p = namespace("pifa")["design"]({"f0": f0})
    assert p["L1"] + p["W1"] + p["H"] - p["ws"] == pytest.approx(wavelength_mm(f0) / 4, rel=0.01)
    i = namespace("ifa")["design"]({"f0": f0})
    assert i["arm_l"] + i["arm_h"] == pytest.approx(wavelength_mm(f0, (i["eps_r"] + 1) / 2) / 4, rel=0.01)


@pytest.mark.parametrize("f0", [1.2e9, 2.45e9])
def test_helix_kraus(f0):
    d = namespace("helix")["design"]({"f0": f0})
    circumference = math.pi * d["D"]
    assert circumference == pytest.approx(wavelength_mm(f0), rel=0.01)
    assert d["S"] / circumference == pytest.approx(math.tan(math.radians(13)), rel=0.01)


def test_lpda_carrel():
    ns = namespace("lpda")
    d = ns["design"]({"f_low": 0.5e9, "f_high": 2e9, "tau": 0.9})
    assert d["sigma"] == pytest.approx(0.243 * 0.9 - 0.051, abs=1e-4)
    values, _ = load_model(MODELS / "lpda.py").resolve(d)
    elems = ns["elements"](values)
    assert elems[0][1] == pytest.approx(wavelength_mm(0.5e9) / 2, rel=1e-6)
    assert elems[-1][1] <= wavelength_mm(2e9) / 2
    for (x0, l0), (x1, l1) in zip(elems, elems[1:]):
        assert l1 / l0 == pytest.approx(0.9)
        assert (x1 - x0) / l0 == pytest.approx(2 * d["sigma"])


def test_spiral_and_vivaldi_band_limits():
    s = namespace("spiral")["design"]({"f_low": 2e9, "f_high": 10e9})
    assert s["r_out"] == pytest.approx(wavelength_mm(2e9) / (2 * math.pi), rel=0.01)
    assert s["r_in"] == pytest.approx(wavelength_mm(10e9) / (4 * math.pi), rel=0.01)
    v = namespace("vivaldi")["design"]({"f_low": 3e9, "f_high": 10e9})
    assert v["aperture_w"] == pytest.approx(wavelength_mm(3e9) / 2, rel=0.01)
    assert v["taper_l"] == pytest.approx(wavelength_mm(3e9), rel=0.01)


def test_pyramidal_horn_balanis_example_13_6():
    """Balanis Example 13.6: 11 GHz, 22.6 dB, a = 2.286 cm, b = 1.016 cm -> A = 16.36 cm, B = 12.84 cm."""
    d = namespace("pyramidal_horn")["design"]({"f0": 11e9, "gain_dbi": 22.6, "a": 22.86, "b": 10.16})
    assert d["A"] == pytest.approx(163.6, rel=0.01)
    assert d["B"] == pytest.approx(128.4, rel=0.01)


@pytest.mark.parametrize("f0,gain", [(10e9, 20.0), (24e9, 18.0)])
def test_pyramidal_horn_is_realizable(f0, gain):
    """p_e = p_h = horn_len (Balanis 13-49), and the gain formula gives the target."""
    d = namespace("pyramidal_horn")["design"]({"f0": f0, "gain_dbi": gain})
    lam = wavelength_mm(f0)
    rho_e, rho_h = d["B"] ** 2 / (2 * lam), d["A"] ** 2 / (3 * lam)
    p_e = (d["B"] - d["b"]) * math.sqrt((rho_e / d["B"]) ** 2 - 0.25)
    p_h = (d["A"] - d["a"]) * math.sqrt((rho_h / d["A"]) ** 2 - 0.25)
    assert p_e == pytest.approx(d["horn_len"], rel=0.01)
    assert p_h == pytest.approx(d["horn_len"], rel=0.01)
    g = 10 * math.log10(0.51 * 4 * math.pi * d["A"] * d["B"] / lam ** 2)
    assert g == pytest.approx(gain, abs=0.1)


@pytest.mark.parametrize("f0", [10e9, 24e9])
def test_conical_and_corrugated_horns(f0):
    lam = wavelength_mm(f0)
    c = namespace("conical_horn")["design"]({"f0": f0, "gain_dbi": 20.0})
    assert 20 * math.log10(math.pi * c["aperture_d"] / lam) - 2.91 == pytest.approx(20.0, abs=0.05)
    # The waveguide radius puts f0 at 1.2 x the TE11 cutoff.
    assert C0 * 1.8412 / (2 * math.pi * c["a"] * 1e-3) * 1.2 == pytest.approx(f0, rel=0.01)
    g = namespace("corrugated_horn")["design"]({"f0": f0, "gain_dbi": 20.0})
    assert g["depth"] == pytest.approx(lam / 4, rel=0.01)
    assert g["pitch"] == pytest.approx(lam / 5, rel=0.01)
    assert 10 * math.log10(0.75 * (math.pi * g["aperture_d"] / lam) ** 2) == pytest.approx(20.0, abs=0.05)


@pytest.mark.parametrize("f0,gain,ratio", [(10e9, 30.0, 0.4), (24e9, 35.0, 0.3)])
def test_reflector(f0, gain, ratio):
    d = namespace("reflector")["design"]({"f0": f0, "gain_dbi": gain, "f_over_d": ratio})
    lam = wavelength_mm(f0)
    assert 10 * math.log10(0.55 * (math.pi * d["D"] / lam) ** 2) == pytest.approx(gain, abs=0.05)
    assert d["F"] / d["D"] == pytest.approx(ratio, rel=1e-3)


def test_array_pitch_and_count():
    _, out, _ = run("linear_array", {"element": 4, "n": 5, "spacing": 0.5})
    feeds = sorted((a for a in port_anchors(out)), key=lambda a: a.point[0])
    assert len(feeds) == 5
    pitch = feeds[1].point[0] - feeds[0].point[0]
    assert pitch == pytest.approx(wavelength_mm(2.45e9) / 2, rel=0.01)
    _, out, _ = run("planar_array", {"element": 4, "nx": 3, "ny": 2})
    assert len(port_anchors(out)) == 6


# --- manifest -------------------------------------------------------------------

def manifest_models():
    with open(PLUGIN / "witwin.toml", "rb") as fh:
        data = tomllib.load(fh)
    return [m for m in data["contributes"]["models"] if m["path"].startswith("models/antennas/")]


def test_manifest_lists_every_generator():
    entries = manifest_models()
    assert sorted(m["id"] for m in entries) == sorted(f"witwin.maxwell.antenna.{n}" for n in GENERATORS)
    files = sorted(p.stem for p in MODELS.glob("*.py") if not p.name.startswith("_"))
    assert files == sorted(GENERATORS)
    for m in entries:
        assert (PLUGIN / m["path"]).is_file(), m["path"]
        assert m["category"] == "Antennas"
        assert m["title"] and m["tags"]


@pytest.mark.parametrize("name", GENERATORS)
def test_model_file_contract(name):
    ns = namespace(name)
    doc = (ns.get("__doc__") or "").strip()
    assert doc and doc.splitlines()[0].endswith("."), f"{name}: first docstring line must be a sentence"
    assert ns["CONFIG"]["unit"] == "mm" and ns["CONFIG"]["up"] == "z"
    assert callable(ns["build"]) and callable(ns["design"]) and ns["DESIGN_SPEC"] and ns["PARAMS"]
    assert set(ns["design"]()) <= set(ns["PARAMS"]), f"{name}: design() returns unknown params"
