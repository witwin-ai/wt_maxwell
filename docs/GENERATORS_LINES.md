# Generators: lines, passives, connectors, packages, periodic

These model files build parametric EM geometry for the Maxwell plugin. Each is a
plain Python file that the WiTwin SDK model runner executes; Studio lists them
from the `[[contributes.models]]` entries at the end of `witwin.toml`.

Run one on its own with `python models/lines/microstrip.py` (opens a preview),
or from Python:

```python
from witwin.studio.geometry import run_model
run = run_model("models/lines/microstrip.py", params={"w": 2.9})
```

Requirements: the witwin-studio SDK with its `cad`, `layout` and `geometry`
extras (build123d, shapely, manifold3d). The solver is not needed to build or
validate the geometry.

## Conventions

- **Axes and units.** `CONFIG["up"]` is `"z"`. Lengths are in `CONFIG["unit"]`:
  `mm` for everything except the photonic crystal slab (`um`). Frequencies are
  always Hz (SI), in `PARAMS` and `DESIGN_SPEC` alike, the same as the antenna
  generators: pass `f0=2.4e9`, not `2.4`. Angles are degrees. Impedances (ohm),
  dB values and ratios have no SDK unit; their descriptions name the unit
  ("ohm", "dB", "dimensionless", "count", "flag").
- **Boards.** Planar models put the bottom ground at z = -t (top face at z = 0),
  the substrate from z = 0 to h, and top copper at z = h. Copper thinner than
  100 um is a `fill="surface"` sheet on the dielectric face, carrying
  `surface_thickness = t`. Ground planes and PEC parts use material `"PEC"`.
  Dielectrics are dicts `{"name", "eps_r", "tan_delta", "sigma_e"}`, where
  `sigma_e = 2 pi f0 eps0 eps_r tan_delta` at the model's `f0`.
- **Roles.** `conductor`, `dielectric`, `port` or `other` (the Wilkinson
  isolation resistor block).
- **Ports.** Port anchors have `kind="port"` and a normal that points out of
  the device. Two-port lines use `port1` (normal -x) and `port2` (normal +x).
  Four-port couplers number ports 1 input, 2 through, 3 coupled, 4 isolated.
  CPW models add `port1_gnd` / `port2_gnd` reference points.
- **Periodic cells.** The cell is centered on the origin in xy. Anchors
  `cell_xmin`, `cell_xmax`, `cell_ymin`, `cell_ymax` (kind `periodic`) sit at
  the centers of the cell faces with outward normals: put periodic or
  Bloch/Floquet boundaries there. `port1` is the top Floquet port (normal +z);
  `port2` is the bottom one (normal -z) and is left out when a ground plane
  closes the cell. The bodies tile without gaps.
- **Grid.** `CONFIG["grid"]` (meters) is the grid each model is validated at
  with no ERROR. Finer features than half a grid step are an ERROR.
- **design().** Models with a closed-form rule have `DESIGN_SPEC` and
  `design(spec)`. `design()` returns parameter values in their declared units,
  so its output can be passed straight to `run_model(params=...)`. Missing spec
  keys take the `DESIGN_SPEC` defaults; unknown keys raise `KeyError`.

## Generator list

| id (`witwin.maxwell.` +) | File | `design()` spec -> output | Grid |
| --- | --- | --- | --- |
| `line.microstrip` | `models/lines/microstrip.py` | z0, h, t, eps_r -> w | 0.1 mm |
| `line.stripline` | `models/lines/stripline.py` | z0, b, eps_r -> w | 0.1 mm |
| `line.cpw` | `models/lines/cpw.py` | z0, s, h, eps_r -> gap | 0.05 mm |
| `line.grounded_cpw` | `models/lines/grounded_cpw.py` (via fence option) | z0, s, h, eps_r -> gap | 0.05 mm |
| `line.coax` | `models/lines/coax.py` | z0, d_outer, eps_r -> d_inner | 0.1 mm |
| `line.rect_waveguide` | `models/lines/rect_waveguide.py` | f0, ratio -> a, b | 0.25 mm |
| `line.waveguide_bend_e` | `models/lines/waveguide_bend_e.py` | f0, ratio, radius_wavelengths -> a, b, radius | 0.25 mm |
| `line.waveguide_bend_h` | `models/lines/waveguide_bend_h.py` | f0, ratio, radius_wavelengths -> a, b, radius | 0.25 mm |
| `line.waveguide_tee` | `models/lines/waveguide_tee.py` (`plane` 0 = E, 1 = H; `port3` on the arm) | f0, ratio -> a, b | 0.25 mm |
| `line.circular_waveguide` | `models/lines/circular_waveguide.py` | f0 -> radius | 0.25 mm |
| `passive.coupled_microstrip` | `models/passives/coupled_microstrip.py` | z0, coupling_db, f0, h, eps_r -> w, s, length | 0.05 mm |
| `passive.stub` | `models/passives/stub.py` (open or shorted) | z0, z_stub, length_deg, f0, h, t, eps_r -> w0, w_stub, stub_length | 0.1 mm |
| `passive.stepped_impedance_lpf` | `models/passives/stepped_impedance_lpf.py` | z0, z_low, z_high, fc, n, ripple_db, h, t, eps_r -> widths (lengths in build) | 0.1 mm |
| `passive.hairpin_bpf` | `models/passives/hairpin_bpf.py` | z0, z_resonator, f0, fbw, n, ripple_db, h, t, eps_r -> widths (arms, gaps, taps in build) | 0.05 mm |
| `passive.wilkinson` | `models/passives/wilkinson.py` | z0, f0, h, t, eps_r -> w0, w_arm, r_iso | 0.1 mm |
| `passive.branch_line` | `models/passives/branch_line.py` | z0, f0, h, t, eps_r -> w0, w_shunt, w_series | 0.1 mm |
| `connector.sma_edge` | `models/connectors/sma_edge.py` | z0, d_ptfe, eps_r -> d_pin | 0.05 mm |
| `package.qfn` | `models/packages/qfn.py` | none | 0.025 mm |
| `package.bga` | `models/packages/bga.py` | none | 0.025 mm |
| `package.wire_bond` | `models/packages/wire_bond.py` | none | 5 um |
| `periodic.square_loop` | `models/periodic/square_loop.py` | f0, eps_r, width, gap -> loop, period | 0.05 mm |
| `periodic.jerusalem_cross` | `models/periodic/jerusalem_cross.py` | none | 0.05 mm |
| `periodic.split_ring` | `models/periodic/split_ring.py` (1 or 2 rings) | none | 0.05 mm |
| `periodic.fss_cell` | `models/periodic/fss_cell.py` (patch or aperture, with or without substrate) | f0, eps_r, substrate, fill -> size, period | 0.05 mm |
| `periodic.photonic_crystal_slab` | `models/periodic/photonic_crystal_slab.py` (square or triangular lattice, optional oxide) | wavelength, u_mid, r_ratio -> a, r | 0.02 um |

Defaults are the designed values for a common case: 50 ohm lines on 1.6 mm FR4
(eps_r 4.4), 2.4 GHz passives, WR-90-like waveguides at 10 GHz, and a
silicon membrane photonic crystal for 1550 nm.

### `DESIGN_SPEC` units

| Key | Unit | Used by |
| --- | --- | --- |
| `f0` | Hz | circular_waveguide, rect_waveguide, waveguide_bend_e/h, waveguide_tee, branch_line, coupled_microstrip, hairpin_bpf, stub, wilkinson, fss_cell, square_loop |
| `fc` | Hz | stepped_impedance_lpf |
| `h`, `t`, `b`, `s`, `d_outer`, `d_ptfe`, `width`, `gap` | mm | board and line models, sma_edge, square_loop |
| `wavelength` | um | photonic_crystal_slab |
| `length_deg` | deg | stub |
| `z0`, `z_stub`, `z_low`, `z_high`, `z_resonator` | ohm (no SDK unit) | lines, passives, sma_edge |
| `coupling_db`, `ripple_db` | dB (no SDK unit) | coupled_microstrip, hairpin_bpf, stepped_impedance_lpf |
| `eps_r`, `ratio`, `fbw`, `fill`, `u_mid`, `r_ratio` | dimensionless | as listed in each model |
| `radius_wavelengths` | guided wavelengths | waveguide_bend_e/h |
| `n` | count | hairpin_bpf, stepped_impedance_lpf |
| `substrate` | 0/1 flag | fss_cell |

## Formulas and sources

Shared formulas live in `models/lines/_lines_formulas.py` (pure Python, no
imports). The passives load the same file by path.

| Quantity | Formula | Source |
| --- | --- | --- |
| Microstrip Z0, eps_eff | Hammerstad-Jensen closed form with the strip-thickness correction; width by bisection | Hammerstad & Jensen, IEEE MTT-S Digest 1980, 407-409 |
| Stripline Z0 and width | Closed form for a zero-thickness strip | Pozar, Microwave Engineering, 4th ed., eqs. 3.179-3.182 |
| CPW and grounded CPW | Conformal mapping with K(k)/K(k') by the AGM; asymptote (pi/2)/ln(4/k) for k < 1e-7 | Simons, Coplanar Waveguide Circuits, Components and Systems, 2001, ch. 2 |
| Coax | Z0 = eta0 / (2 pi sqrt(eps_r)) ln(D/d) | Pozar, Table 2.1 |
| Rectangular waveguide | fc_mn = c/2 sqrt((m/a)^2 + (n/b)^2); design puts f0 at `ratio` x fc10, b = a/2 | Pozar, sec. 3.3 |
| Circular waveguide | TE11 cutoff p'11 = 1.8412, TM01 cutoff p01 = 2.4049; design puts f0 midway | Pozar, sec. 3.4 |
| Waveguide bends | Bend radius = `radius_wavelengths` x guided wavelength (default 1) | Rule of thumb for low reflection |
| Coupled lines | Z0e, Z0o = Z0 sqrt((1 +/- C)/(1 -/+ C)) | Pozar, eq. 7.79 |
| Coupled microstrip | Garg-Bahl even/odd model, Newton refinement from an Akhtarzad starting guess | Garg & Bahl, IEEE MTT-27, 1979; Akhtarzad et al., IEEE MTT-23, 1975 |
| Low-pass prototypes | Butterworth and Chebyshev g-values | Matthaei, Young & Jones, 1964; Pozar, sec. 8.3 |
| Stepped-impedance LPF | beta*l = g*Z_low/Z0 (shunt C) or g*Z0/Z_high (series L) | Pozar, sec. 8.6; defaults reproduce Example 8.6 |
| Hairpin BPF | M(i,i+1) = FBW / sqrt(g_i g_i+1); Qe = g0 g1 / FBW; tap from Qe = (pi/2)(Z0/Zr) / sin^2(theta) | Hong & Lancaster, Microstrip Filters for RF/Microwave Applications, 2001, ch. 5-6 |
| Wilkinson | Arms Z0 sqrt(2), lambda/4; R = 2 Z0 | Pozar, sec. 7.3 |
| Branch-line | Series arms Z0/sqrt(2), shunt arms Z0, all lambda/4 | Pozar, sec. 7.5 |
| SMA pin | Coax formula inside the PTFE bore | Pozar, Table 2.1 |
| Square loop | Mean perimeter = one wavelength; wavelength shortened by sqrt((eps_r + 1)/2) | Munk, Frequency Selective Surfaces, 2000, ch. 2 and 4 |
| FSS patch / aperture | Side = lambda/2 with the same shortening; aperture by Babinet's principle | Munk, 2000 |
| Photonic crystal slab | a = u_mid x lambda (scale invariance), r = r_ratio x a | Joannopoulos et al., Photonic Crystals, 2nd ed., 2008, ch. 2; Johnson et al., Phys. Rev. B 60, 5751, 1999 |
| QFN, BGA, wire bond | JEDEC-style outlines (MO-220 lead pattern, JEP95 ball rows skipping I, O, Q, S, X, Z; 4-point loop with h1, alpha, beta) | JEDEC outlines, simplified |

## Approximations and limits

- **Junctions are ideal.** Tees, steps, bends and stub junctions add no
  discontinuity correction. Line lengths come from the ideal quarter-wave or
  prototype rule; the solver shows the real response.
- **Hairpin filter.** Gaps come from the coupled-line coupling of each pair
  (scaled by `gap_scale`) and the tap from the external-Q rule. Both are first
  cuts: they ignore the hairpin bend and the coupling between non-adjacent
  resonators. Tune with the solver.
- **Coupled microstrip.** Akhtarzad's synthesis is only a starting guess. The
  result is refined on the Garg-Bahl model, which is good to a few percent.
- **Metasurface design rules** are crude (roughly 10-20 %). The gap between
  elements, the substrate thickness and a ground plane all shift the
  resonance. Jerusalem cross and split ring have no `design()`.
- **Photonic crystal slab.** `design()` does not compute the band gap. Take
  `u_mid` from a band solve for your r/a, t/a and cladding.
- **Simplified parts.** The SMA, QFN and BGA keep only what matters for the
  fields: pin, insulator and shell; mold, pad and leads; laminate, mold and
  balls. No threads, chamfers, bond fingers or internal routing.
- **Wilkinson resistor.** A lossy block with `role="other"`, sized so its bulk
  conductivity gives `r_iso` between the arms. Anchors `iso_a` and `iso_b`
  (kind `lumped`) mark where a lumped element can replace it.
- **Validation warnings that are expected.** `conductor_overlap` on coax,
  SMA and QFN is a bounding-box check: the nested inner and outer conductors,
  and the leads around the exposed pad, do not actually touch. No other model
  warns at its default parameters.
- **Dependencies.** The plugin's `pyproject.toml` does not list build123d,
  shapely and manifold3d. They come with the witwin-studio SDK extras.

## Tests

`tests/test_generators_lines.py` runs every generator here through the SDK
runner, with defaults and with `design()` output. Each run must have no
validation ERROR and must have port anchors. The tests also check the formulas
against published values, check every file against its manifest entry, and
check a few geometry variants. Run them from `tests/`:

```bash
python -m pytest test_generators_lines.py -q
```
