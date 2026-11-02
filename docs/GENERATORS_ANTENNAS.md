# Antenna generators

`models/antennas/` holds 20 model files that build antenna geometry for the
Maxwell FDTD solver: 18 single antennas and 2 array generators that tile any
of them. Each file is listed in `witwin.toml` under `[[contributes.models]]`
with category `Antennas` and id `witwin.maxwell.antenna.<file name>`.

Every file follows the model-file contract of the `witwin.studio.geometry` SDK:

- `CONFIG = {"unit": "mm", "up": "z"}`. Lengths are in mm, z is up.
- `PARAMS`: one `ws.param` per dimension. The defaults equal `design()` at
  the default `DESIGN_SPEC`, so the default model is a working design, not a
  placeholder.
- `build(ctx)` returns the bodies and anchors.
- `DESIGN_SPEC` and `design(spec) -> dict`: give it a frequency (or band) and
  a few targets, and it returns PARAMS overrides from the textbook formulas
  cited below. Unknown spec keys raise `ValueError`.
- `suggested_grid(params) -> mm`: the FDTD grid step at which the model
  validates with no ERROR. It is the smaller of lambda0/20 at the highest
  design frequency and the smallest feature (substrate h/2, wire radius, gap,
  wall).

Use it like this:

```python
from witwin.studio.geometry import load_model
import runpy

path = "models/antennas/patch.py"
ns = runpy.run_path(path)                 # needs models/antennas on sys.path
over = ns["design"]({"f0": 5.8e9, "eps_r": 3.55, "h": 0.813})
model = load_model(path)
values, _ = model.resolve(over)
out = model.run(values)
report = out.validate(grid=ns["suggested_grid"](values) * 1e-3)
```

## Conventions

- **Materials.** Conductors are `"PEC"`. Dielectrics are
  `{"eps_r": ..., "sigma_e": ...}`. The Material component has no loss-tangent
  field, so `tan_delta` is converted to `sigma_e = 2 pi f eps0 eps_r tan_delta`
  at the design frequency (the lowest one for band designs).
- **Roles.** `conductor`, `dielectric`, and `port`-kind anchors.
- **Copper.** PCB copper (35 um by default) is a `fill="surface"` sheet on the
  dielectric face and carries its real thickness in `surface_thickness`
  (meters). Ground planes of wire antennas and the slot plane are sheets as
  well. Horns, wires, booms and the dish are solids.
- **Ports.** Every model has a `feed` anchor with `kind="port"` on the body
  that carries it. PCB models also have `feed_ref` on the reference
  conductor. Coax-fed models (`patch_probe`, `circular_patch`) put `feed` at
  the far end of a modelled coax stub (pin, PTFE dielectric, shield) below
  the ground. Arrays rename ports to `feed_<i>`. The linear array with a
  corporate feed has a single `feed`.
- **Loose anchors** (not on a body) mark useful points: `top`,
  `ground_bottom`, `aperture`, `focus`, `front`, `back`, `center`.

## Generators

| id (`witwin.maxwell.antenna.*`) | What it builds | `DESIGN_SPEC` keys | Design formulas |
| --- | --- | --- | --- |
| `patch` | Rectangular patch with an inset 50 ohm microstrip feed | f0, eps_r, h, tan_delta, z0 | Balanis 14-6 (W), 14-1/14-2/14-7 (eps_eff, dL, L); edge resistance from 14-12, 14-18a; inset from 14-20a, R_edge cos^2(pi y0/L) = Z0; line width by Hammerstad (Pozar 3.197) |
| `patch_probe` | Rectangular patch, coax probe through the ground | f0, eps_r, h, tan_delta, z0, pin_d | Same patch formulas; probe where R_edge cos^2(pi y0/L) = Z0 (probe inductance not compensated); PTFE coax with Z0 = 60/sqrt(eps_r) ln(D/d) |
| `circular_patch` | Circular patch (TM11), coax probe | f0, eps_r, h, tan_delta, z0 | Balanis 14-67/14-68 (radius); probe where R(rho0) = R(a_e) J1^2(k rho0)/J1^2(k a_e) = Z0 (14-73), R(a_e) = 1/G_rad (14-70) |
| `aperture_coupled_patch` | Patch on one substrate, slot in the ground, microstrip on a second substrate below | f0, eps_r, h, tan_delta, eps_r_feed, h_feed, tan_delta_feed, z0 | Patch by Balanis TLM; slot length 0.15 lambda0 (at most 0.9 W), width a tenth of that, open stub 0.22 lambda_g (Pozar 1996 review starting values) |
| `dipole` | Half-wave dipole, flat strip or round wire, centre gap | f0, width, kind | Induced-EMF reactance (Balanis 8-60b), length solved for X = 0; a strip of width w is a wire of radius w/4 |
| `monopole` | Quarter-wave wire over a disc ground | f0, wire_d | Image theory: half the induced-EMF resonant dipole of the same wire radius; ground radius 0.5 lambda0 |
| `pifa` | Planar inverted-F: top plate, shorting plate, feed pin, ground | f0, H, aspect, short_ratio | Taga's rule L1 + W1 + H - ws = lambda0/4 (Hirasawa and Haneishi 1992, ch. 5) |
| `ifa` | Printed inverted-F on a PCB edge (top copper) | f0, eps_r, h, tan_delta, trace_w | arm_l + arm_h = lambda_eff/4 with eps_eff = (eps_r + 1)/2 |
| `yagi` | Reflector, driven dipole, N directors (wires, no boom) | f0, n_directors, d_over_lambda | NBS TN-688 starting values (Balanis 10.3.3): reflector 0.482 lambda at 0.2 lambda, directors 0.428 lambda tapering 0.004 lambda, 0.25 lambda apart |
| `lpda` | Log-periodic dipole array on a twin boom with transposed feed | f_low, f_high, tau | Carrel (Balanis 11.4.2): sigma_opt = 0.243 tau - 0.051, B_ar, B_s, N, L1 = lambda_max/2, L(n+1) = tau Ln, dn = 2 sigma Ln |
| `helix` | Axial-mode helix over a disc ground | f0, turns, pitch_deg, wire_d | Kraus: C = lambda0, pitch 13 deg, ground 0.75 lambda0, R_in about 140 C/lambda0 |
| `spiral` | Two-arm self-complementary Archimedean spiral | f_low, f_high, turns, eps_r, h | Active-region rule (Balanis 11.5): r_out = lambda_low/(2 pi), r_in = lambda_high/(4 pi) |
| `pyramidal_horn` | Pyramidal horn on a rectangular waveguide | f0, gain_dbi, a, b | Balanis 13-56 to 13-58 (optimum horn, chi by a secant solver), p_e = p_h; EIA waveguide chosen from f0 unless a, b are given. Checked against Balanis Example 13.6 |
| `conical_horn` | Conical horn on a circular waveguide | f0, gain_dbi | Optimum cone (Balanis 13.6): D = (pi d/lambda)^2 - 2.91 dB, slant l = d^2/(3 lambda); waveguide radius at 1.2 x TE11 cutoff |
| `corrugated_horn` | Conical corrugated (scalar) horn | f0, gain_dbi, flare_deg | Groove depth lambda/4, period lambda/5, slot/period 0.8 (Clarricoats and Olver 1984); D = 0.75 (pi d/lambda)^2 |
| `vivaldi` | Exponential tapered slot, microstrip-to-slotline feed with cavity and stub | f_low, f_high, eps_r, h, tan_delta | Gibson 1979; Shin and Schaubert 1999: L = lambda_low, W = lambda_low/2; cavity lambda_eff/4, stub lambda_g/4 at sqrt(f_low f_high) |
| `slot` | Half-wave slot in a finite PEC sheet, off-centre gap port | f0, slot_w_lambda, z0 | Babinet (Balanis 12.8): length of the complementary strip dipole, Z_slot = eta^2/(4 x 73.1); feed offset where R_c cos^2(pi x/L) = Z0 |
| `reflector` | Prime-focus paraboloid with an open circular waveguide at the focus | f0, gain_dbi, f_over_d | G = eta_ap (pi D/lambda)^2 with eta_ap = 0.55 (Balanis 15.4) |
| `linear_array` | n copies of any element along x, optional corporate feed | f0, element, n, spacing | Element from its own design() at f0; pitch in lambda0 or mm. Corporate feed: 50 ohm lines, 25 ohm T-junctions, 35.36 ohm lambda_g/4 transformers |
| `planar_array` | nx x ny copies on a rectangular or triangular lattice | f0, element, nx, ny, lattice, spacing | Element from its own design() at f0; triangular rows shift by half a pitch |

The `element` parameter of the arrays is an integer code in this order:
0 patch, 1 patch_probe, 2 circular_patch, 3 aperture_coupled_patch,
4 dipole, 5 monopole, 6 pifa, 7 ifa, 8 yagi, 9 lpda, 10 helix, 11 spiral,
12 pyramidal_horn, 13 conical_horn, 14 corrugated_horn, 15 vivaldi, 16 slot,
17 reflector. With `use_design = 1` the element is designed at the array f0
(band elements keep their default band ratio around f0). Board layers that
an element lists in `ARRAY_SHARED` (ground, substrate) become one board
under the whole array; ground planes keep each element's holes.

## Known approximations

These are starting geometries. Tune them in the solver before trusting
impedance or pattern numbers.

- **Patches.** The transmission-line model is good to a few percent in
  frequency. The circular-patch probe position uses radiation conductance
  only (no dielectric or copper loss), so it sits slightly too far out.
- **Corporate feed** (`linear_array`, `feed_network = 1`, patch element only):
  impedances are right on paper, but the network is not EM-tuned. Junction
  parasitics and coupling to the patches are ignored. `n` must be a power of
  two.
- **Arrays** only translate the element, in the XY plane. No rotation,
  amplitude taper or phase steering; set those on the ports in the solver.
  Mutual coupling is not compensated.
- **Yagi**: no boom; driven-element impedance shifts with coupling.
- **LPDA**: no rear short-circuit stub and no element-diameter scaling.
- **IFA**: top copper only, no bottom ground pour.
- **Spiral**: free-space wavelengths (thin substrate); no absorbing cavity.
- **Corrugated horn**: no throat mode converter.
- **Reflector**: the feed is an open waveguide placeholder whose pattern does
  not match the dish edge angle; no struts.
- **Vivaldi**: the microstrip-to-slotline transition is a starting point,
  not a matched design.
- **Validation** uses bounding boxes for overlap and port checks, so arrays
  and coax stubs report overlap warnings that are not real intersections.

## Tests

`tests/test_generators_antennas.py` runs every generator with its defaults
and with `design()` at two frequencies or bands, validates each at its
`suggested_grid` (no ERROR allowed), checks the feed port anchors, checks key
dimensions against the formulas above written out independently, checks the
manifest entries, and runs one model through the subprocess runner. It needs
only the geometry stack (the SDK, build123d, shapely, trimesh, manifold3d),
not the solver.
