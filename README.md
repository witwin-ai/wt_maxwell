# wt-maxwell

A WiTwin studio plugin that round-trips **`witwin.maxwell`** electromagnetic
solver scenes to and from the studio editor, re-runs `Simulation.fdtd`, and
visualizes the resulting 2D field slices / 3D field volumes.

It registers a `MaxwellAdapter` under the `"maxwell"` domain on the core
`PlatformSceneHandler` (frozen base layer `witwin_server.platform_bridge`) so the
editor's `load_platform_scene` / `export_platform_scene` messages dispatch maxwell
scenes here. The plugin owns only the maxwell-specific surface; geometry,
transform, structure metadata, and the unified `Material` component are shared
base-layer code it reads/writes.

## Scope

- **Scene config** — `Domain`, `GridSpec` (uniform / anisotropic), `BoundarySpec`
  (none/pml/periodic/bloch/pec/pmc; global, per-axis, per-face), subpixel, symmetry,
  device — on a singleton `Maxwell Settings` object.
- **Materials** — the unified `Material` (EM superset): Debye/Drude/Lorentz poles
  (electric and magnetic), diagonal anisotropy tensors, Kerr — built into a full
  `maxwell.Material`. Plus `MaterialRegion` (topology optimization; density is
  runtime state and never serialized).
- **Sources** — `PointDipole`, `PlaneWave`, `GaussianBeam`, `ModeSource` with
  nested temporal profiles (`CW` / `GaussianPulse` / `RickerWavelet`) and TFSF.
- **Monitors** — `PointMonitor`, `PlaneMonitor` (+ flux), `FinitePlaneMonitor`,
  `ClosedSurfaceMonitor`, `ModeMonitor`; `ModePort`.
- **Solve + viz** — FDTD with 2D slice + 3D volume.

## Layout

```
wt-maxwell/
├── witwin.manifest.json   # plugin metadata + deps
├── __init__.py            # registers components + the maxwell adapter (eager)
├── components/            # maxwell scene components (auto-registered)
│   └── solver.py          # Maxwell Solver single component
├── adapter/               # the round-trip translation layer
│   ├── maxwell_adapter.py # MaxwellAdapter (detect / to_studio / to_platform)
│   ├── settings_map.py    # scene config <-> the Maxwell Solver component
│   └── material_adapter.py# Material (EM superset) <-> maxwell.Material
└── tests/                 # CPU round-trip suites (one per phase)
```

## Running the tests

The round-trip suites run against the **installed** environment — the same
packages the running server uses. Install the studio backend (with the frozen
`platform_bridge`) and the maxwell solver editable, in an env that also has
`torch`, `drjit>=1.0`, `scipy`, `trimesh`, and `pytest`:

```bash
pip install -e <studio>/server --no-deps        # witwin_server (+ platform_bridge)
pip install -e <platform>/maxwell --no-deps      # witwin.maxwell (needs witwin.core)
```

Then just run pytest — no `PYTHONPATH` needed (conftest adds only the plugins
directory so `import wt_maxwell` resolves):

```bash
# from plugins/wt_maxwell
python -m pytest tests
```

They run on CPU except the M4 live-solve suite, which uses CUDA when available and
skips if no working solver is present.
