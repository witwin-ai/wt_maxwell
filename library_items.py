"""Maxwell library prefabs — drag-to-create scene building blocks.

Registers a ``Maxwell`` library category with:

- **Maxwell 3D Field (Demo)** — a point source at the center of an empty PML
  domain (wt-FDTD style). Drag it in, press **Solve** on the Maxwell Settings
  object, and the radiated 3D field volume appears in the viewport.
- **Maxwell Settings** — one Maxwell Solver component with domain / grid / boundary
  / settings / result foldouts and a Solve button for composing a custom scene.
- **Dipole Source**, **Plane Monitor**, **Dielectric Box** — individual building
  blocks.

Each prefab object is built by reusing the tested adapter maps (so geometry,
materials, and components match the round-trip exactly). The factory adds any extra
objects to the drop scene and returns the primary one (the library handler adds
that one). Result/runtime state is never part of a prefab.
"""
import inspect as _inspect
from pathlib import Path as _Path

from witwin_server.api import Library


_PREVIEWS = _Path(__file__).resolve().parent / "previews" / "library"


def _preview(item_id):
    """The Library card image for an item, as keyword arguments.

    Images are renders from Studio's `scripts/template-previews/library_items.py`.
    Empty when the file is missing or Studio's `register_item` has no `preview`
    parameter yet (older Studio), so the card falls back to the item's icon.
    """
    path = _PREVIEWS / f"{item_id}.webp"
    if not path.is_file() or "preview" not in _inspect.signature(Library.register_item).parameters:
        return {}
    return {"preview": str(path)}

_CATEGORY = "maxwell"
_DEFAULT_FREQ = 1e9  # lambda ~0.3 m -> ~7.5 cells/wavelength on the 0.04 m demo grid
_DOMAIN = ((-0.6, 0.6), (-0.6, 0.6), (-0.6, 0.6))


def _config_scene():
    """A config-only maxwell.Scene (no structures) for the Settings object.

    Grid is ~7.5 cells per wavelength at the default 1 GHz (lambda ~0.3 m) so the
    field is well resolved — a coarse grid relative to the wavelength produces
    numerical garbage, not a clean field.
    """
    import witwin.maxwell as mw
    return mw.Scene(domain=mw.Domain(bounds=_DOMAIN), grid=mw.GridSpec.uniform(0.04),
                    boundary=mw.BoundarySpec.pml(num_layers=10), device="cuda")


def _settings_object(name="Maxwell Settings"):
    """Build the Maxwell Settings object with solve frequencies pre-filled."""
    from .adapter.settings_map import SettingsMap

    obj = SettingsMap.to_studio(_config_scene())
    obj.name = name
    solve = obj.get_component("MaxwellSolver")
    if solve is not None:
        solve.frequencies = [_DEFAULT_FREQ]
    return obj


def _box_object():
    import witwin.maxwell as mw
    from .adapter.maxwell_adapter import MaxwellAdapter

    return MaxwellAdapter._structure_to_studio(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.3, 0.3, 0.3)),
        mw.Material(eps_r=11.7, name="silicon"), name="Dielectric Box"))


def _dipole_object(position=(0.0, 0.0, 0.0)):
    import witwin.maxwell as mw
    from .adapter.source_map import SourceMap
    return SourceMap.to_studio(mw.PointDipole(
        position=position, polarization="Ez",
        source_time=mw.GaussianPulse(frequency=_DEFAULT_FREQ, fwidth=_DEFAULT_FREQ * 0.2),
        name="Point Source"))


def _plane_monitor_object():
    import witwin.maxwell as mw
    from .adapter.monitor_map import MonitorMap
    return MonitorMap.to_studio(mw.PlaneMonitor("Field Slice", axis="z", position=0.0, fields=("Ez",)))


# --- library factories (context.scene gets the extras; return the primary obj) ---

def _make_demo(ctx):
    """3D-field demo: Maxwell Settings (returned) + a point source at the domain center.

    Mirrors the wt-FDTD "3D field" experience: drag it in, press Solve, and the
    radiated 3D field volume appears in the viewport (the Settings object's
    Maxwell Solver auto-shows its own volume; the field is the full FDTD solution,
    so no structure or monitor is needed).
    """
    settings = _settings_object(ctx.name)
    ctx.scene.add_object(_dipole_object(position=(0.0, 0.0, 0.0)))
    return settings


def _make_settings(ctx):
    return _settings_object(ctx.name)


def _make_box(ctx):
    obj = _box_object()
    obj.name = ctx.name
    return obj


def _make_dipole(ctx):
    obj = _dipole_object()
    obj.name = ctx.name
    return obj


def _make_plane_monitor(ctx):
    obj = _plane_monitor_object()
    obj.name = ctx.name
    return obj


def register() -> None:
    """Register the Maxwell library category + prefab items."""
    Library.register_category(_CATEGORY, "Maxwell", icon="waves", order=20)
    Library.register_item("maxwell_demo", "Maxwell 3D Field (Demo)", _CATEGORY,
                          icon="sparkles", object_type="empty", factory=_make_demo,
                          description="Point source at the domain center; Solve to see the 3D field", **_preview("maxwell_demo"))
    Library.register_item("maxwell_settings", "Maxwell Settings", _CATEGORY,
                          icon="settings", object_type="empty", factory=_make_settings,
                          description="Scene config + Solve button (build your own scene)", **_preview("maxwell_settings"))
    Library.register_item("maxwell_box", "Dielectric Box", _CATEGORY,
                          icon="box", object_type="mesh", factory=_make_box,
                          description="A box structure with an EM material", **_preview("maxwell_box"))
    Library.register_item("maxwell_dipole", "Dipole Source", _CATEGORY,
                          icon="radio", object_type="empty", factory=_make_dipole,
                          description="Point dipole source (CW)", **_preview("maxwell_dipole"))
    Library.register_item("maxwell_plane_monitor", "Plane Monitor", _CATEGORY,
                          icon="scan", object_type="empty", factory=_make_plane_monitor,
                          description="Axis-aligned field monitor plane", **_preview("maxwell_plane_monitor"))


register()
