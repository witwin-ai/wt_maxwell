"""M5 display data: the PML inset the viewport draws and the mode-profile contract."""
import math

import pytest
from witwin_server.api import SceneObject

C = 299792458.0


def _solver(**values):
    obj = SceneObject(name="Maxwell", mesh_type="Empty")
    comp = obj.add_component("MaxwellSolver")
    for name, value in values.items():
        comp.set_field(name, value, force=True)
    return comp


def test_pml_inset_follows_layers_and_cell_size(wtm):
    comp = _solver(frequencies=[1e9], ppw="10", num_layers=12)
    cell = C / 1e9 / 10
    assert comp.to_dict()["values"]["pml_inset"] == pytest.approx([12 * cell] * 6)


def test_pml_inset_is_zero_on_non_pml_faces(wtm):
    comp = _solver(frequencies=[2e9], ppw="20", num_layers=8, mode="per_face", z_low="pec", x_high="periodic")
    inset = comp.to_dict()["values"]["pml_inset"]
    t = 8 * C / 2e9 / 20
    assert inset == pytest.approx([t, 0.0, t, t, 0.0, t])


def test_pml_inset_is_derived_not_saved(wtm):
    comp = _solver()
    comp.to_dict()
    assert "pml_inset" not in comp.to_properties_dict()["properties"]


def _profile(index, n_eff=2.4, te=0.97, scale=3.0):
    u = [-0.5e-6, 0.0, 0.5e-6]
    v = [-0.2e-6, 0.2e-6]
    return {"index": index, "n_eff": n_eff, "te_fraction": te, "u": u, "v": v,
            "values": [scale * x for x in (0.1, 1.0, 0.1, -0.2, -0.5, -0.2)], "label": f"TE{index}"}


@pytest.mark.parametrize("name", ["ModeSource", "ModeMonitor"])
def test_mode_profiles_are_normalized_sorted_and_saved(wtm, name):
    obj = SceneObject(name="mode", mesh_type="Empty")
    comp = obj.add_component(name)
    assert comp.to_dict()["values"]["mode_profiles"] == []

    comp.set_mode_profiles([_profile(1, te=1.4), _profile(0)])
    profiles = comp.to_dict()["values"]["mode_profiles"]
    assert [p["index"] for p in profiles] == [0, 1]
    assert max(abs(x) for x in profiles[0]["values"]) == pytest.approx(1.0)
    assert profiles[1]["te_fraction"] == 1.0
    assert profiles[0]["label"] == "TE0"

    saved = comp.to_properties_dict()["properties"]
    other = SceneObject(name="copy", mesh_type="Empty").add_component(name)
    other.from_properties_dict(saved)
    assert other.mode_profiles == profiles


@pytest.mark.parametrize("bad, message", [
    ({"values": [0.0] * 5}, "expected len"),
    ({"u": [0.0, 0.0, 1.0]}, "ascending"),
    ({"v": [0.0]}, "at least 2"),
    ({"values": [math.nan] * 6}, "finite"),
])
def test_mode_profile_validation(wtm, bad, message):
    comp = SceneObject(name="mode", mesh_type="Empty").add_component("ModeSource")
    with pytest.raises(ValueError, match=message):
        comp.set_mode_profiles([{**_profile(0), **bad}])


def test_mode_profile_indices_must_be_unique(wtm):
    comp = SceneObject(name="mode", mesh_type="Empty").add_component("ModeSource")
    with pytest.raises(ValueError, match="unique"):
        comp.set_mode_profiles([_profile(0), _profile(0)])
