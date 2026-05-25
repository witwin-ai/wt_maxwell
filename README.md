# wt-maxwell

A WiTwin studio plugin that round-trips **`witwin.maxwell`** electromagnetic
solver scenes to and from the studio editor, re-runs `Simulation.fdfd` / `fdtd`,
and visualizes the resulting 2D field slices / 3D field volumes.

It registers a `MaxwellAdapter` under the `"maxwell"` domain on the core
`PlatformSceneHandler` (frozen base layer `witwin_server.platform_bridge`) so the
editor's `load_platform_scene` / `export_platform_scene` messages dispatch maxwell
scenes here. The plugin owns only the maxwell-specific surface; geometry,
transform, structure metadata, and the unified `EMMaterial` component are shared
base-layer code it reads/writes.

## Scope

- **Scene config** — `Domain`, `GridSpec` (uniform / anisotropic), `BoundarySpec`
  (none/pml/periodic/bloch/pec/pmc; global, per-axis, per-face), subpixel, symmetry,
  device — on a singleton `Maxwell Settings` object.
- **Materials** — the unified `EMMaterial` superset: Debye/Drude/Lorentz poles
  (electric and magnetic), diagonal anisotropy tensors, Kerr — built into a full
  `maxwell.Material`. Plus `MaterialRegion` (topology optimization; density is
  runtime state and never serialized).
- **Sources** — `PointDipole`, `PlaneWave`, `GaussianBeam`, `ModeSource` with
  nested temporal profiles (`CW` / `GaussianPulse` / `RickerWavelet`) and TFSF.
- **Monitors** — `PointMonitor`, `PlaneMonitor` (+ flux), `FinitePlaneMonitor`,
  `ClosedSurfaceMonitor`, `ModeMonitor`; `ModePort`.
- **Solve + viz** — FDFD (single-freq) / FDTD (multi-freq); 2D slice + 3D volume.

## Layout

```
wt-maxwell/
├── witwin.manifest.json   # plugin metadata + deps
├── __init__.py            # registers components + the maxwell adapter (eager)
├── components/            # maxwell scene components (auto-registered)
│   └── settings.py        # MaxwellDomain / Grid / Boundary / SolveSettings
├── adapter/               # the round-trip translation layer
│   ├── maxwell_adapter.py # MaxwellAdapter (detect / to_studio / to_platform)
│   ├── settings_map.py    # scene config <-> the Maxwell Settings components
│   └── material_adapter.py# EMMaterial <-> maxwell.Material
└── tests/                 # CPU round-trip suites (one per phase)
```

## Running the tests

The round-trip suites need the studio backend with the frozen base layer
(`witwin_server` + `witwin_server.platform_bridge`) and the maxwell solver
(`witwin.core` / `witwin.maxwell`) on `PYTHONPATH`. They run on CPU (no GPU
needed except the M4 live-solve suite, which requires CUDA). Use a Python
environment with `torch`, `drjit>=1.0`, `scipy`, `trimesh`, and `pytest`:

```bash
# from plugins/wt-maxwell
PYTHONPATH="<studio>/server;<platform>/core;<platform>/maxwell" \
  python -m pytest tests
```
