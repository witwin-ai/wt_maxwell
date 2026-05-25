"""Maxwell library prefabs — drag-to-create scene building blocks.

Registers a ``Maxwell`` library category with:

- **Maxwell Scene (Demo)** — a complete, immediately solvable setup (Maxwell
  Settings with solve frequencies + a dielectric box + a dipole source + a plane
  monitor). Drag it in, then press **Solve** on the Maxwell Settings object.
- **Maxwell Settings** — just the scene-config singleton (domain / grid / boundary
  / solve settings / result + Solve button) for composing a custom scene.
- **Dipole Source**, **Plane Monitor**, **Dielectric Box** — individual building
  blocks.

Each prefab object is built by reusing the tested adapter maps (so geometry,
materials, and components match the round-trip exactly). The factory adds any extra
objects to the drop scene and returns the primary one (the library handler adds
that one). Result/runtime state is never part of a prefab.
"""
from witwin_server import Library

_CATEGORY = "maxwell"
_DEFAULT_FREQ = 5e9
_DOMAIN = ((-0.6, 0.6), (-0.6, 0.6), (-0.6, 0.6))


def _config_scene():
    """A config-only maxwell.Scene (no structures) for the Settings object."""
    import witwin.maxwell as mw
    return mw.Scene(domain=mw.Domain(bounds=_DOMAIN), grid=mw.GridSpec.uniform(0.05),
                    boundary=mw.BoundarySpec.pml(num_layers=10), device="cuda")


def _settings_object(name="Maxwell Settings"):
    """Build the Maxwell Settings object with solve frequencies pre-filled."""
    from .adapter.settings_map import SettingsMap

    obj = SettingsMap.to_studio(_config_scene())
    obj.name = name
    solve = obj.get_component("MaxwellSolveSettings")
    if solve is not None:
        solve.frequencies = [_DEFAULT_FREQ]
    return obj


def _box_object():
    import witwin.maxwell as mw
    from witwin_server.platform_bridge import StructureMap
    return StructureMap.to_studio(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.3, 0.3, 0.3)),
        mw.Material(eps_r=11.7, name="silicon"), name="Dielectric Box"))


def _dipole_object():
    import witwin.maxwell as mw
    from .adapter.source_map import SourceMap
    return SourceMap.to_studio(mw.PointDipole(
        position=(-0.25, 0.0, 0.0), polarization="Ez",
        source_time=mw.CW(frequency=_DEFAULT_FREQ), name="Dipole Source"))


def _plane_monitor_object():
    import witwin.maxwell as mw
    from .adapter.monitor_map import MonitorMap
    return MonitorMap.to_studio(mw.PlaneMonitor("Field Slice", axis="z", position=0.0, fields=("Ez",)))


# --- library factories (context.scene gets the extras; return the primary obj) ---

def _make_demo(ctx):
    """Full solvable scene: settings (returned) + box + dipole + plane monitor."""
    settings = _settings_object(ctx.name)
    extras = [_box_object(), _dipole_object(), _plane_monitor_object()]
    ctx.scene.begin_batch()
    for obj in extras:
        ctx.scene.add_object(obj)
    ctx.scene.end_batch()
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
    Library.register_item("maxwell_demo", "Maxwell Scene (Demo)", _CATEGORY,
                          icon="sparkles", object_type="empty", factory=_make_demo,
                          description="Solvable starter scene: settings + box + dipole + monitor")
    Library.register_item("maxwell_settings", "Maxwell Settings", _CATEGORY,
                          icon="settings", object_type="empty", factory=_make_settings,
                          description="Scene config + Solve button (build your own scene)")
    Library.register_item("maxwell_box", "Dielectric Box", _CATEGORY,
                          icon="box", object_type="mesh", factory=_make_box,
                          description="A box structure with an EM material")
    Library.register_item("maxwell_dipole", "Dipole Source", _CATEGORY,
                          icon="radio", object_type="empty", factory=_make_dipole,
                          description="Point dipole source (CW)")
    Library.register_item("maxwell_plane_monitor", "Plane Monitor", _CATEGORY,
                          icon="scan", object_type="empty", factory=_make_plane_monitor,
                          description="Axis-aligned field monitor plane")


register()
