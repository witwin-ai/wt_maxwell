# wt-maxwell — deferred follow-ups (Phase M5)

The M0–M4 phases cover the complete declarative authoring + solve surface:
scene config (domain / grid / boundary global+per-axis+per-face / subpixel /
symmetry / device), the full unified `Material` EM superset (Debye/Drude/Lorentz electric
**and** magnetic, diagonal anisotropy, Kerr) + `MaterialRegion`, all four sources
with the three temporal profiles and TFSF, all six monitors, `ModePort`, and the
FDTD solve with 2D slice / 3D volume field visualization.

The following are intentionally **deferred** (master §9, plan §7.3 / §8 M5):

## Postprocessing (plan §7.3 — "Phase 4, not v1")
`maxwell.postprocess` offers S-parameters, mode overlap, bistatic RCS,
directivity, and NFFT/NTFF. These should become buttons on `MaxwellSolver` that
call the relevant postprocess function and push a `Results.plot` / `Results.commit`.
Not implemented yet — the solve `Result` is kept server-side, so adding these is a
pure additive step on `components/result.py`.

## Topology optimization / adjoint (plan §6.3)
`MaterialRegion` round-trips its shape/bounds/filter/projection, but the `density`
tensor is the optimization design variable (runtime state) and is **not**
serialized — `to_platform` rebuilds a zero placeholder. The adjoint/optimization
loop (`requires_grad` density, gradient bridge, `adjoint_checkpoint_stride`) is out
of scope for v1.

## UX polish
- Per-face boundary editing currently uses the `mode` enum (global / per_axis /
  per_face) with flat fields; an always-expanded 6-face widget could be nicer.
- Multi-frequency monitor / result selectors: `frequency_index` is a plain int
  field; a proper frequency dropdown driven by the solved result would be better.

## Platform-limited (mirror, don't implement)
The adapter already mirrors the platform's `NotImplemented` guards as errors +
`info_box` warnings: full `Tensor3x3` anisotropy, `orientation`, anisotropic +
dispersive, and Kerr + (dispersive | anisotropic). These unlock only when the
maxwell solver supports them.

## Live editor verification (needs a running server)
The round-trip and solve are covered headlessly by the pytest suites. Loading a
scene into the *running editor* and rendering it is left for manual verification —
load `examples/demo_scene.py` via a `load_platform_scene` message:

```json
{ "type": "load_platform_scene", "factory": "wt_maxwell.examples.demo_scene:build_scene" }
```

then edit, `export_platform_scene`, and press **Solve** on the Maxwell Settings
object.
