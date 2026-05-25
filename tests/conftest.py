"""Pytest harness for the wt_maxwell round-trip suite.

Runs against the real environment: ``witwin_server`` (with the frozen
``platform_bridge``) and the maxwell solver (``witwin.maxwell`` / ``witwin.core``)
must be installed — e.g. ``pip install -e server`` and ``pip install -e
<platform>/maxwell`` (the same packages the running server uses), so no PYTHONPATH
is needed. This conftest only adds the plugins directory so
``importlib.import_module("wt_maxwell")`` resolves (the plugin itself is not
pip-installed; the server adds the same directory at startup). If the base/solver
deps are not importable, the whole suite is skipped rather than erroring.
"""
import importlib
import sys
from pathlib import Path

import pytest

# .../plugins/wt_maxwell/tests -> .../plugins
PLUGINS_DIR = Path(__file__).resolve().parents[2]
if str(PLUGINS_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGINS_DIR))

PKG = "wt_maxwell"

try:
    import witwin_server  # noqa: F401
    import witwin.maxwell  # noqa: F401
    _DEPS_OK = True
except ImportError:
    _DEPS_OK = False

# Skip collection of every test module when the base/solver deps are absent.
if not _DEPS_OK:
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(scope="session")
def wtm():
    """Import the plugin package (registers components + the maxwell adapter)."""
    return importlib.import_module(PKG)


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
    """'cuda' when available, else 'cpu' (FDFD/FDTD run on either for small grids)."""
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


@pytest.fixture(scope="session")
def solver_ready(device):
    """Skip the live-solve suite if the maxwell solver can't run a tiny FDFD here."""
    import witwin.maxwell as mw
    try:
        scene = mw.Scene(domain=mw.Domain(bounds=((-0.3, 0.3), (-0.3, 0.3), (-0.3, 0.3))),
                         grid=mw.GridSpec.uniform(0.15), boundary=mw.BoundarySpec.pml(6), device=device)
        scene.add_source(mw.PointDipole(position=(0.0, 0.0, 0.0), polarization="Ez",
                                        source_time=mw.CW(frequency=1e9)))
        mw.Simulation.fdfd(scene, frequency=1e9).run()
    except Exception as exc:  # noqa: BLE001 - test gate: needs-user-verification if solver absent
        pytest.skip(f"maxwell solver unavailable in this environment: {exc}")
    return True
