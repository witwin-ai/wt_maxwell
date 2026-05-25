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
    """A small dielectric-box cavity with a dipole source and a plane monitor."""
    import witwin.maxwell as mw

    scene = mw.Scene(
        domain=mw.Domain(bounds=((-0.6, 0.6), (-0.6, 0.6), (-0.6, 0.6))),
        grid=mw.GridSpec.uniform(0.05),
        boundary=mw.BoundarySpec.pml(num_layers=10),
        device="cuda",
    )
    scene.add_structure(mw.Structure(
        mw.Box(position=(0.0, 0.0, 0.0), size=(0.3, 0.3, 0.3)),
        mw.Material(eps_r=11.7, name="silicon"), name="cavity"))
    scene.add_structure(mw.Structure(
        mw.Sphere(position=(0.2, 0.1, 0.0), radius=0.08),
        mw.Material(eps_r=2.1, name="ptfe"), name="bead"))
    scene.add_source(mw.PointDipole(
        position=(-0.25, 0.0, 0.0), polarization="Ez",
        source_time=mw.GaussianPulse(frequency=5e9, fwidth=1e9)))
    scene.add_monitor(mw.PlaneMonitor("xy_slice", axis="z", position=0.0, fields=("Ez",)))
    return scene
