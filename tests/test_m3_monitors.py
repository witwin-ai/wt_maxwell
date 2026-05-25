"""M3 round-trip: monitors + ports.

Per-monitor round-trip; FluxMonitor <-> PlaneMonitor(compute_flux); ClosedSurface
box bounds preserved; ModePort reproduced and its solve-time expansion
(resolved_sources / resolved_monitors) intact.
"""
import witwin.maxwell as mw

from _helpers import assert_monitor_equal, assert_monitors_equal, assert_port_equal


def _scene() -> "mw.Scene":
    return mw.Scene(
        domain=mw.Domain(bounds=((-1.0, 1.0), (-1.0, 1.0), (-1.0, 1.0))),
        grid=mw.GridSpec.uniform(0.1),
        boundary=mw.BoundarySpec.pml(),
        device="cpu",
    )


def _roundtrip_monitor(adapter, monitor):
    scene = _scene()
    scene.add_monitor(monitor)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    return rebuilt.monitors[0]


# --- monitors ----------------------------------------------------------------

def test_point_monitor(adapter):
    mon = mw.PointMonitor("p", position=(0.1, 0.2, 0.3), fields=("Ex", "Ez"))
    assert_monitor_equal(mon, _roundtrip_monitor(adapter, mon))


def test_plane_monitor(adapter):
    mon = mw.PlaneMonitor("pl", axis="y", position=0.25, fields=("Ex", "Ez"),
                          frequencies=(1e9, 2e9), normal_direction="-")
    assert_monitor_equal(mon, _roundtrip_monitor(adapter, mon))


def test_plane_monitor_broadband(adapter):
    mon = mw.PlaneMonitor("plb", axis="z", position=0.0)
    rebuilt = _roundtrip_monitor(adapter, mon)
    assert rebuilt.frequencies is None
    assert_monitor_equal(mon, rebuilt)


def test_flux_monitor(adapter):
    mon = mw.FluxMonitor("flux", axis="z", position=0.1, frequencies=(1e9,), normal_direction="+")
    rebuilt = _roundtrip_monitor(adapter, mon)
    assert rebuilt.compute_flux is True
    assert_monitor_equal(mon, rebuilt)


def test_finite_plane_monitor(adapter):
    mon = mw.FinitePlaneMonitor("fp", position=(0.0, 0.0, 0.2), size=(0.8, 0.8, 0.0),
                                fields=("Ez",), frequencies=(1e9,), normal_direction="+")
    assert_monitor_equal(mon, _roundtrip_monitor(adapter, mon))


def test_closed_surface_monitor(adapter):
    mon = mw.ClosedSurfaceMonitor.box("cs", position=(0.0, 0.0, 0.0), size=(0.6, 0.6, 0.6),
                                      frequencies=(1e9,))
    assert_monitor_equal(mon, _roundtrip_monitor(adapter, mon))


def test_mode_monitor(adapter):
    mon = mw.ModeMonitor("mm", position=(0.0, 0.0, 0.3), size=(1.0, 1.0, 0.0), mode_index=2,
                         direction="-", frequencies=(1e9,))
    assert_monitor_equal(mon, _roundtrip_monitor(adapter, mon))


def test_multiple_monitors(adapter):
    scene = _scene()
    scene.add_monitor(mw.PointMonitor("a", position=(0.0, 0.0, 0.0)))
    scene.add_monitor(mw.PlaneMonitor("b", axis="z", position=0.0))
    scene.add_monitor(mw.ClosedSurfaceMonitor.box("c", position=(0.0, 0.0, 0.0), size=(0.5, 0.5, 0.5)))
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    assert_monitors_equal(scene.monitors, rebuilt.monitors)


# --- ports -------------------------------------------------------------------

def test_mode_port_monitor_only(adapter):
    port = mw.ModePort("port_in", position=(0.0, 0.0, -0.4), size=(1.0, 1.0, 0.0),
                       mode_index=0, direction="+", frequencies=(1e9,), monitor_offset=0.05)
    scene = _scene()
    scene.add_port(port)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    assert len(rebuilt.ports) == 1
    assert_port_equal(port, rebuilt.ports[0])


def test_mode_port_source(adapter):
    port = mw.ModePort("port_src", position=(0.0, 0.0, -0.4), size=(1.0, 1.0, 0.0),
                       mode_index=0, direction="+", frequencies=(1e9,),
                       source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8))
    scene = _scene()
    scene.add_port(port)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    rport = rebuilt.ports[0]
    assert rport.source_time is not None
    assert_port_equal(port, rport)


def test_mode_port_resolves(adapter):
    # A source-carrying port must expand into a resolved source + monitor at solve time.
    port = mw.ModePort("p", position=(0.0, 0.0, -0.4), size=(1.0, 1.0, 0.0), mode_index=0,
                       direction="+", frequencies=(1e9,), source_time=mw.CW(frequency=1e9))
    scene = _scene()
    scene.add_port(port)
    rebuilt = adapter.to_platform(adapter.to_studio(scene))
    assert len(rebuilt.resolved_sources()) >= 1
    assert len(rebuilt.resolved_monitors()) >= 1
