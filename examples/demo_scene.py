"""Demo maxwell scene factory for end-to-end editor verification.

Load it into a running editor with a ``load_platform_scene`` message:

    { "type": "load_platform_scene",
      "factory": "wt_maxwell.examples.demo_scene:build_scene" }

The maxwell adapter detects it (``isinstance(scene, maxwell.Scene)``), translates
it to studio objects (a ``Maxwell Settings`` object + a dielectric box + a dipole
source + a plane monitor), and renders them. Editing then exporting via
``export_platform_scene`` rebuilds an equivalent ``maxwell.Scene``; pressing
``Solve`` on the Maxwell Settings object runs FDFD and shows the field slice.

This factory is the live-editor verification left for the user (the round-trip and
solve are covered headlessly by the M0-M4 pytest suites).
"""


def build_scene():
    """An empty PML domain with a single point (dipole) source at the center.

    The 3D field radiated by the center source is the full FDFD solution, so no
    structure or monitor is needed — solving it shows a clean 3D field volume.
    Grid ~7.5 cells/wavelength at 1 GHz (lambda ~0.3 m).
    """
    import witwin.maxwell as mw

    scene = mw.Scene(
        domain=mw.Domain(bounds=((-0.6, 0.6), (-0.6, 0.6), (-0.6, 0.6))),
        grid=mw.GridSpec.uniform(0.04),
        boundary=mw.BoundarySpec.pml(num_layers=10),
        device="cuda",
    )
    scene.add_source(mw.PointDipole(
        position=(0.0, 0.0, 0.0), polarization="Ez",
        source_time=mw.CW(frequency=1e9), name="Point Source"))
    return scene
