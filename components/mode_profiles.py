"""Mode profiles on ``ModeSource`` and ``ModeMonitor``: display data only.

A mode solver fills them through :meth:`ModeProfilesMixin.set_mode_profiles`;
the viewport paints the profile of ``mode_index`` on the mode plane and lists
every mode with its effective index and TE fraction. This plugin does not
solve modes, and nothing here invents placeholder profiles: until a solver
publishes them the list stays empty and the plane shows only its outline.

Contract, one dict per mode (all lengths in metres):

``index``        int, the mode number ``mode_index`` selects.
``n_eff``        float, effective index (real part).
``te_fraction``  float in [0, 1], share of energy in the TE-like components.
``u``, ``v``     ascending grid coordinates along the plane's two in-plane
                 axes (the axes with non-zero ``size``, in x, y, z order),
                 relative to the plane centre.
``values``       ``len(u) * len(v)`` signed samples of the displayed field
                 component, u fastest. Stored scaled to max |value| = 1.
``label``        optional str, e.g. ``"TE0"``.
``component``    optional str, the field component shown, e.g. ``"Ey"``.

The list is published outside the declared fields (like a Field's volume
refs): sent with every sync and saved with the component.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping

import numpy as np

MODE_PROFILES = "mode_profiles"


def publish_value(component: Any, name: str, value: Any) -> None:
    """Sets a value outside the declared fields and sends it to the viewport."""
    component._values[name] = value
    owner = getattr(component, "_owner", None)
    scene = getattr(owner, "scene", None) if owner else None
    if scene:
        scene._emit("component_updated", object_id=owner.id, component_name=component._component_name,
                    field_name=name, value=value)


def normalize_mode_profile(profile: Mapping[str, Any]) -> Dict[str, Any]:
    """Validated copy of one mode profile, values scaled to max |value| = 1."""
    u = np.asarray(profile["u"], dtype=np.float64).ravel()
    v = np.asarray(profile["v"], dtype=np.float64).ravel()
    values = np.asarray(profile["values"], dtype=np.float64)
    # A (len(v), len(u)) array is accepted as well as the flat u-fastest list.
    values = values.ravel()
    if len(u) < 2 or len(v) < 2:
        raise ValueError("mode profile needs at least 2 grid points along u and v")
    if np.any(np.diff(u) <= 0) or np.any(np.diff(v) <= 0):
        raise ValueError("mode profile u and v must be strictly ascending")
    if values.size != u.size * v.size:
        raise ValueError(f"mode profile values has {values.size} samples, expected len(u) * len(v) = {u.size * v.size}")
    if not np.all(np.isfinite(values)):
        raise ValueError("mode profile values must be finite")
    peak = float(np.max(np.abs(values)))
    if peak > 0:
        values = values / peak
    out: Dict[str, Any] = {
        "index": int(profile["index"]),
        "n_eff": float(profile["n_eff"]),
        "te_fraction": float(min(1.0, max(0.0, float(profile["te_fraction"])))),
        "u": u.tolist(),
        "v": v.tolist(),
        "values": [round(float(x), 5) for x in values],
    }
    if profile.get("label"):
        out["label"] = str(profile["label"])
    if profile.get("component"):
        out["component"] = str(profile["component"])
    return out


class ModeProfilesMixin:
    """Publishes and persists ``mode_profiles`` on a mode plane component."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._values.setdefault(MODE_PROFILES, [])

    @property
    def mode_profiles(self) -> List[Dict[str, Any]]:
        return list(self._values.get(MODE_PROFILES) or [])

    def set_mode_profiles(self, profiles: Iterable[Mapping[str, Any]]) -> None:
        """Replaces the profiles (see the module docstring for the contract) and updates the viewport."""
        normalized = sorted((normalize_mode_profile(p) for p in profiles), key=lambda p: p["index"])
        if len({p["index"] for p in normalized}) != len(normalized):
            raise ValueError("mode profile indices must be unique")
        publish_value(self, MODE_PROFILES, normalized)

    def clear_mode_profiles(self) -> None:
        publish_value(self, MODE_PROFILES, [])

    def from_properties_dict(self, properties: Dict[str, Any]) -> None:
        properties = dict(properties)
        saved = properties.pop(MODE_PROFILES, None)
        super().from_properties_dict(properties)
        self._values[MODE_PROFILES] = list(saved or [])
