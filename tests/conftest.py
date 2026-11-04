"""Pytest harness for the wt_maxwell round-trip suite.

Runs against the real environment: ``witwin_server`` (with the frozen
``platform_bridge``) and the maxwell solver (``witwin.maxwell`` / ``witwin.core``)
must be installed — e.g. ``pip install -e server`` and ``pip install -e
<platform>/maxwell`` (the same packages the running server uses), so no PYTHONPATH
is needed. This conftest only adds the plugins directory so
``importlib.import_module("wt_maxwell")`` resolves (the plugin itself is not
pip-installed; the server adds the same directory at startup). If the base/solver
deps are not importable, the round-trip modules are skipped rather than erroring.
"""
import importlib
import importlib.util
import sys
from pathlib import Path

import pytest

PKG = "wt_maxwell"
# Load this checkout as ``wt_maxwell`` whatever its folder is called (a
# worktree such as ``wt_maxwell-eval``); importing by name from the parent
# folder would test the sibling ``wt_maxwell`` checkout instead.
PLUGIN_ROOT = Path(__file__).resolve().parents[1]

try:
    if importlib.util.find_spec("witwin_server") is None:
        raise ImportError("witwin_server")
    import witwin.maxwell  # noqa: F401
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False

# Skip the round-trip suites (test_m<N>_*.py) when the base/solver deps are absent;
# the geometry-only generator tests (test_generators_*.py) still run.
if not _DEPS_OK:
    collect_ignore_glob = ["test_m[0-9]_*.py"]
elif PKG not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        PKG, PLUGIN_ROOT / "__init__.py", submodule_search_locations=[str(PLUGIN_ROOT)])
    sys.modules[PKG] = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(sys.modules[PKG])


@pytest.fixture(scope="session")
def wtm():
    """Import the plugin package (registers components + the maxwell adapter)."""
    return sys.modules[PKG]


@pytest.fixture(scope="session")
def adapter(wtm):
    """A fresh :class:`MaxwellAdapter` instance."""
    return importlib.import_module(f"{PKG}.adapter.maxwell_adapter").MaxwellAdapter()


@pytest.fixture(scope="session")
def mat_adapter(wtm):
    """The :class:`MaterialAdapter` class (for direct material round-trip / guards)."""
    return importlib.import_module(f"{PKG}.adapter.material_adapter").MaterialAdapter


@pytest.fixture(scope="session")
def solve_mod(wtm):
    """The solve module (SolveRunner / SolveConfig / SliceExtractor)."""
    return importlib.import_module(f"{PKG}.adapter.solve")


@pytest.fixture(scope="session")
def device():
    """'cuda' when available, else 'cpu' (FDTD runs on either for tiny test grids)."""
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


@pytest.fixture(scope="session")
def solver_ready(device):
    """Skip the live-solve suite if the maxwell solver can't run a tiny FDTD here."""
    import witwin.maxwell as mw
    try:
        scene = mw.Scene(domain=mw.Domain(bounds=((-0.3, 0.3), (-0.3, 0.3), (-0.3, 0.3))),
                         grid=mw.GridSpec.uniform(0.15), boundary=mw.BoundarySpec.pml(6), device=device)
        scene.add_source(mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez",
                                        source_time=mw.GaussianPulse(frequency=1e9, fwidth=2e8)))
        # full_field_dft: a solve with no output is an error, which skipped every live test.
        mw.Simulation.fdtd(scene, frequencies=(1e9,), full_field_dft=True,
                           run_time=mw.TimeConfig(time_steps=20)).run()
    except Exception as exc:  # noqa: BLE001 - test gate: needs-user-verification if solver absent
        pytest.skip(f"maxwell solver unavailable in this environment: {exc}")
    return True


@pytest.fixture(scope="session", autouse=True)
def _studio_system_plugins():
    """Activate Studio's system Plugins once, as a ProjectServer does.

    The EM fields of Material and the Transmitter, Receiver and Field
    components belong to the system Plugin ``studio.em`` (2026-11-03); Scenes
    built directly in these tests need it active.
    """
    try:
        from witwin_server.api import testing
    except ImportError:
        return
    testing.activate_system_plugins()
