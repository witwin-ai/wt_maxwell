# Maxwell objects on the Bench

Status: plan and record of the 2026-11-04 work. Branch `d16/maxwell-bench`
(wt_maxwell, from `d16/maxwell-0.5.1`) and `maxwell-bench-seams` (Studio,
from integration `653c0ffa`).

**Conclusion.** Every Maxwell object gets a deliberate look in both stages,
coloured by a role from the stage palette (emitter, sensor, boundary,
region) instead of hand-picked colours; resize handles under the Bounds tool
(T); a click target; and a short label while selected. Boundaries, symmetry
and the grid stay fields of `MaxwellSolver` (no new scene objects), so the
user-facing model does not change. Studio needs two small additive seams in
`@witwin/host`: the `tool` prop for gizmos (from main `e728d69d`) and a
`stage` prop with the stage palette for visualizers and gizmos.

## 1. What is there today

Read on the D16 line (Studio `653c0ffa`, wt_maxwell `7c86c5f`).

| Object | Today (both stages look the same) |
|---|---|
| PointDipoleSource | Blue sphere + polarization arrow; 1-px hit area |
| PlaneWaveSource | Two blue arrows from the origin; TFSF box dashed blue |
| GaussianBeamSource | Same as plane wave; waist and focus not drawn |
| ModeSource | Mode plane with profile texture, mode list while selected |
| PointMonitor | Green 3-axis cross, no hit area worth clicking |
| PlaneMonitor | Dashed green rectangle clipped to the domain; fill 0.12 when `compute_flux` |
| FluxMonitor (= Plane/FinitePlane with `compute_flux`) | Only a denser fill; normal direction not shown |
| FinitePlaneMonitor | Dashed green rectangle |
| ClosedSurfaceMonitor | Dashed green box |
| ModeMonitor | Mode plane, dashed |
| ModePort | **Nothing** (standard Empty marker) |
| MaxwellSolver domain | wt_volume Field box (+ Field gizmo) |
| Boundary | One dashed grey inner box where PML starts; periodic, Bloch, PEC, PMC and per-face kinds **not shown** |
| Symmetry | **Not shown** |
| Grid | **Not shown** (only Properties `ppw`) |
| Solids | Bench part style (feature edges, X-ray) |
| MaterialRegion | **Nothing** beyond its box mesh |
| Temporal profile | **Not shown** |
| Results | wt_volume Field visualizer (slices, volume, SDF, vector) |

Colours are three literals in `emStyle.ts`; the Bench's own colours are
literals inside `BenchPartStyle.tsx` / `BenchStageEnvironment.tsx` with no
way for a Plugin to read them. No Maxwell object has an edit handle.

## 2. Studio seams

Both are optional props, so older Plugins and hosts keep working (minor,
additive change to the stable `VisualizerConfig` / `GizmoProvider`).

1. **`tool?: TransformToolName`** on gizmo components, only for selected
   objects. Already on Studio main (`e728d69d`, Select Q / Bounds T); taken
   into the seam branch by cherry-pick so the D16 line has it too.
2. **`stage?: ViewportStage`** on visualizer and gizmo components:

   ```ts
   interface ViewportStage {
     kind: 'world' | 'bench';
     xray: boolean;          // Bench X-ray is on
     palette: ViewportStagePalette;
   }
   interface ViewportStagePalette {
     background: string; edge: string; text: string; accent: string;
     emitter: string;   // what injects energy: sources, transmitters
     sensor: string;    // what records: monitors, probes, receivers
     boundary: string;  // domain limits and absorbers
     region: string;    // design and material regions
     warning: string;   // something the solve will not use as drawn
   }
   ```

   Studio defines the palette once (`features/sceneStage/stagePalette.ts`,
   per stage and theme, `allow-color` tagged) and `BenchPartStyle` /
   `BenchStageEnvironment` read their edge and background colours from it,
   so Plugins and the Bench share one source.

No new picking or handle API is needed: a mesh with an invisible material is
already a soft click target (`viewportSelection.ts`), handles mark
themselves `userData.isGizmo`, and `host.interaction.setGizmoDragging` +
`scene.updateComponentField` already exist.

## 3. Per object

"Handles" are shown only for the selected object under the Bounds tool (T),
like the Field box. Ctrl snaps to the grid cell, Alt resizes about the
centre. Labels appear while selected (Bench and World).

### Sources (role `emitter`)

| Object | Look | Handles | Click target |
|---|---|---|---|
| PointDipoleSource | Small solid sphere; double-ended dipole arrow along the polarization | none | sphere ×3 |
| PlaneWaveSource | Square wavefront plate across the domain section, k arrow, short E arrow; TFSF box as a solid-edge box with faint faces | TFSF box faces (`tfsf_min/max`) | plate |
| GaussianBeamSource | As plane wave, plus the waist circle at `focus` (radius `beam_waist`) | TFSF box faces | plate |
| ModeSource | Mode plane (profile texture), solid outline | plane edges (`size`) | plane |
| Temporal profile | Label: kind, centre frequency, bandwidth ("Gaussian pulse · 1 GHz ± 200 MHz") | — | — |

### Monitors (role `sensor`)

| Object | Look | Handles | Click target |
|---|---|---|---|
| PointMonitor | Hollow octahedron probe + short axis ticks | none | octahedron ×3 |
| PlaneMonitor | Dashed rectangle clipped to the domain, faint fill | one handle moves `position` along the axis | plane |
| Flux (Plane/FinitePlane `compute_flux`) | As above, denser fill, normal arrow for `normal_direction`, "Flux" in the label | as its base type | plane |
| FinitePlaneMonitor | Dashed rectangle, faint fill | plane edges (`size`) | plane |
| ClosedSurfaceMonitor | Dashed box, faint faces | box faces (`size`) | faces |
| ModeMonitor | Mode plane, dashed | plane edges (`size`) | plane |
| ModePort | Port plane in `emitter` when `is_source` else `sensor`, direction arrow, the monitor plane at `monitor_offset` dashed in `sensor`, label "Port · mode n" | plane edges (`size`) | plane |

### Solver object (`MaxwellSolver`)

| Part | Look | Handles |
|---|---|---|
| Domain | wt_volume Field box, unchanged | Field gizmo (Bounds tool) |
| PML faces | Translucent slab of the PML thickness on each PML face, in `boundary` | — |
| Periodic / Bloch faces | Face outline dashed, matching chevrons on the paired face; Bloch adds "k" to the label | — |
| PEC / PMC faces | Face filled in `boundary` (PEC denser than PMC), hatched edge | — |
| Symmetry | Mirror plane on the chosen face, label "PEC symmetry" / "PMC symmetry" | — |
| Grid | While selected: cell ticks on the three domain edges nearest the camera, label "Δ 4.28 cm · 38 × 38 × 38" | — |

Face labels (kind per face) show only while the solver is selected, so the
per-face boundary fields in Properties can be read on the faces.

### Geometry

| Object | Look |
|---|---|
| Solids | Bench part style (feature edges, X-ray), unchanged |
| MaterialRegion | Region box in `region`, design-grid lattice (`density_nx/ny/nz`, capped) while selected, label with `region_name` |

### Results

Field slices and volumes stay wt_volume's Field visualizer on the solver
object. Maxwell annotations draw after it with `depthWrite` off, so a field
shows through them; under X-ray annotations stay at full opacity.

### Bench vs World

Same geometry in both. World uses the world palette (more saturated against
the sky); Bench uses the Bench palette (tuned to its zinc background) and
draws boundary slabs lighter. An annotation outside the domain draws in
`warning` with the label "Outside domain", because the solve drops it.

## 4. Order of work

1. Studio seam branch: cherry-pick `e728d69d`; add `stage` + palette; the
   Bench reads its colours from the palette; docs and tests.
2. wt_maxwell: palette-driven colours (`emStyle.ts`), new parts (wavefront,
   probe, port, boundary faces, symmetry, grid ticks, MaterialRegion),
   labels, click targets.
3. Handles: one generic box/plane handle part in wt_maxwell, used by the
   plane monitors, mode planes, ModePort, ClosedSurface, TFSF and
   PlaneMonitor position.
4. Checks: plugin tests, typecheck, bundle test; Studio tsc, lints, jest.
5. Electron on the EM Design template on the Bench, one screenshot per type.

## 5. Not in this pass

- Dragging direction and polarization arrows (edit in Properties).
- A Gaussian-beam waist handle.
- One undo step for a box move: the Field gizmo and these handles write
  `size` and the transform as separate steps.
- Moving the generic handle part into `@witwin/ui`/the host so wt_volume and
  wt_maxwell share it.
