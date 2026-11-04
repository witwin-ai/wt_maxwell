import type { ViewportStage, ViewportStagePalette } from '@witwin/host';
import { Line, React, useMemo } from './runtime';
import { BoxFill, Label, PlaneRect, SceneFrame, noRaycast } from './primitives';
import { AXIS_NAMES, formatLength, value, vec3, type Domain, type Vec3 } from './emStyle';

/*
 * What MaxwellSolver says about the domain, drawn on the domain box that
 * wt_volume's Field visualizer outlines: the boundary condition of each
 * face, symmetry planes and, while the solver is selected, the grid.
 * Boundaries stay fields of MaxwellSolver; nothing here is a scene object.
 *
 * Face kinds and the PML thickness follow adapter/grid.py
 * (boundary_face_kinds, pml_inset) so the picture is what the solve uses.
 */

const FACES = ['x_low', 'x_high', 'y_low', 'y_high', 'z_low', 'z_high'] as const;
const SPEED_OF_LIGHT = 299792458;

const KIND_LABEL: Record<string, string> = {
  none: 'None',
  pml: 'PML',
  periodic: 'Periodic',
  bloch: 'Bloch',
  pec: 'PEC',
  pmc: 'PMC',
};

/** Boundary kind of each face, x_low..z_high (adapter/grid.py boundary_face_kinds). */
export function faceKinds(solver: any): string[] {
  const mode = String(value(solver, 'mode', 'global'));
  if (mode === 'per_axis') return FACES.map((f) => String(value(solver, f[0], 'pml')));
  if (mode === 'per_face') return FACES.map((f) => String(value(solver, f, 'pml')));
  return FACES.map(() => String(value(solver, 'kind', 'pml')));
}

/** Uniform FDTD cell size, metres (adapter/grid.py grid_cell_size). */
export function cellSize(solver: any): number {
  const frequencies = (value<unknown[]>(solver, 'frequencies', []) ?? []).map(Number).filter((f) => f > 0);
  const f = frequencies.length ? Math.max(...frequencies) : Number(value(solver, 'frequency', 1e9)) || 1e9;
  const ppw = Math.max(4, Math.min(20, Math.floor(Number(value(solver, 'ppw', 10)) + 0.5)));
  return SPEED_OF_LIGHT / f / ppw;
}

/** PML thickness per face, metres; the published `pml_inset` when present, else layers x cell. */
function pmlInset(solver: any, kinds: string[]): number[] {
  const published = value<number[] | null>(solver, 'pml_inset', null);
  if (Array.isArray(published) && published.length === 6) return published.map(Number);
  const thickness = Number(value(solver, 'num_layers', 15)) * cellSize(solver);
  return kinds.map((k) => (k === 'pml' ? thickness : 0));
}

interface Face {
  axis: number;
  side: -1 | 1;
  /** Coordinate of the face plane along `axis`. */
  plane: number;
  center: Vec3;
  /** Face rectangle size; zero along `axis`. */
  size: Vec3;
}

function domainFaces(domain: Domain): Face[] {
  const centre = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2) as Vec3;
  return FACES.map((_, i) => {
    const axis = Math.floor(i / 2);
    const side = (i % 2 ? 1 : -1) as -1 | 1;
    const plane = side < 0 ? domain.min[axis] : domain.max[axis];
    const center: Vec3 = [...centre];
    center[axis] = plane;
    const size = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]) as Vec3;
    size[axis] = 0;
    return { axis, side, plane, center, size };
  });
}

/** Two short strokes forming a chevron at the face centre pointing out of the domain: periodic faces wrap. */
function chevron(face: Face, length: number): Vec3[] {
  const u = (face.axis + 1) % 3;
  const tip: Vec3 = [...face.center];
  tip[face.axis] += face.side * length * 0.5;
  const segments: Vec3[] = [];
  for (const offset of [-length * 0.25, length * 0.25]) {
    const t: Vec3 = [...tip];
    t[face.axis] += face.side * offset;
    for (const s of [-1, 1]) {
      const b: Vec3 = [...t];
      b[face.axis] -= face.side * length * 0.5;
      b[u] += s * length * 0.5;
      segments.push(t, b);
    }
  }
  return segments;
}

/** Diagonal hatch over a face rectangle: marks a mirror (symmetry) plane. */
function hatch(face: Face, count: number): Vec3[] {
  const [u, v] = [0, 1, 2].filter((a) => a !== face.axis);
  const lo = (a: number) => face.center[a] - face.size[a] / 2;
  const segments: Vec3[] = [];
  for (let i = 1; i < count; i++) {
    const t = i / count;
    const a: Vec3 = [...face.center];
    const b: Vec3 = [...face.center];
    a[u] = lo(u) + t * face.size[u];
    a[v] = lo(v);
    b[u] = lo(u);
    b[v] = lo(v) + t * face.size[v];
    segments.push(a, b);
    const c: Vec3 = [...face.center];
    const d: Vec3 = [...face.center];
    c[u] = lo(u) + t * face.size[u];
    c[v] = lo(v) + face.size[v];
    d[u] = lo(u) + face.size[u];
    d[v] = lo(v) + t * face.size[v];
    segments.push(c, d);
  }
  return segments;
}

function FaceBoundary({ face, kind, inset, palette, dash, bench }: { face: Face; kind: string; inset: number; palette: ViewportStagePalette; dash: number; bench: boolean }) {
  const color = palette.boundary;
  if (kind === 'pml' && inset > 0) {
    const inner = face.plane - face.side * inset;
    const min = [0, 1, 2].map((a) => face.center[a] - face.size[a] / 2) as Vec3;
    const max = [0, 1, 2].map((a) => face.center[a] + face.size[a] / 2) as Vec3;
    min[face.axis] = Math.min(face.plane, inner);
    max[face.axis] = Math.max(face.plane, inner);
    const innerCenter: Vec3 = [...face.center];
    innerCenter[face.axis] = inner;
    return (
      <group>
        <BoxFill min={min} max={max} color={color} opacity={bench ? 0.07 : 0.1} />
        <PlaneRect center={innerCenter} size={face.size} color={color} dashed dash={dash} lineWidth={1} />
      </group>
    );
  }
  if (kind === 'periodic' || kind === 'bloch') {
    return (
      <group>
        <PlaneRect center={face.center} size={face.size} color={color} dashed dash={dash * 0.6} lineWidth={1.25} />
        <Line points={chevron(face, Math.min(face.size[(face.axis + 1) % 3], face.size[(face.axis + 2) % 3]) * 0.08)} segments color={color} lineWidth={1.5} raycast={noRaycast} />
      </group>
    );
  }
  if (kind === 'pec' || kind === 'pmc') {
    return (
      <PlaneRect
        center={face.center}
        size={face.size}
        color={color}
        dashed={kind === 'pmc'}
        dash={dash * 0.4}
        lineWidth={2}
        fillOpacity={kind === 'pec' ? 0.3 : 0.15}
      />
    );
  }
  return null;
}

function SymmetryPlane({ face, mode, palette }: { face: Face; mode: string; palette: ViewportStagePalette }) {
  const segments = useMemo(() => hatch(face, 8), [face]);
  return (
    <group>
      <PlaneRect center={face.center} size={face.size} color={palette.boundary} lineWidth={2} fillOpacity={mode === 'PEC' ? 0.18 : 0.1} />
      <Line points={segments} segments color={palette.boundary} lineWidth={1} transparent opacity={0.7} raycast={noRaycast} />
    </group>
  );
}

/** Ticks at the cell spacing along the three domain edges from the min corner, with the grid size. */
function GridTicks({ domain, solver, palette }: { domain: Domain; solver: any; palette: ViewportStagePalette }) {
  const resolution = vec3(solver, 'resolution', [1, 1, 1]).map((n) => Math.max(1, Math.round(n))) as Vec3;
  const cell = cellSize(solver);
  const segments = useMemo(() => {
    const out: Vec3[] = [];
    const tick = domain.extent * 0.012;
    for (let a = 0; a < 3; a++) {
      const b = (a + 1) % 3;
      const n = resolution[a];
      const step = Math.max(1, Math.ceil(n / 100));
      const d = (domain.max[a] - domain.min[a]) / n;
      for (let k = 0; k <= n; k += step) {
        const p: Vec3 = [...domain.min];
        p[a] = domain.min[a] + k * d;
        const q: Vec3 = [...p];
        q[b] -= k % (step * 5) === 0 ? tick * 1.8 : tick;
        out.push(p, q);
      }
    }
    return out;
  }, [domain, ...resolution]);
  const labelAt: Vec3 = [...domain.min];
  labelAt[1] -= domain.extent * 0.05;
  return (
    <group>
      <Line points={segments} segments color={palette.text} lineWidth={1} transparent opacity={0.75} raycast={noRaycast} />
      <Label position={labelAt}>{`Grid Δ ${formatLength(cell)} · ${resolution.join(' × ')}`}</Label>
    </group>
  );
}

export function SolverAnnotations({ solver, domain, selected, stage, palette }: { solver: any; domain: Domain; selected: boolean; stage?: ViewportStage; palette: ViewportStagePalette }) {
  const faces = useMemo(() => domainFaces(domain), [domain]);
  const kinds = faceKinds(solver);
  const inset = pmlInset(solver, kinds);
  const dash = domain.extent * 0.015;
  const bench = stage?.kind === 'bench';
  const uniform = kinds.every((k) => k === kinds[0]);
  const layers = Math.round(Number(value(solver, 'num_layers', 15)));
  const kindText = (k: string) => (k === 'pml' ? `PML · ${layers} layers` : KIND_LABEL[k] ?? k);
  const symmetry = [0, 1, 2]
    .map((axis) => ({ axis, mode: String(value(solver, `symmetry_${AXIS_NAMES[axis]}`, 'none')), side: String(value(solver, `symmetry_${AXIS_NAMES[axis]}_face`, 'low')) }))
    .filter((s) => s.mode !== 'none');
  const top: Vec3 = [(domain.min[0] + domain.max[0]) / 2, domain.max[1] + domain.extent * 0.06, (domain.min[2] + domain.max[2]) / 2];

  return (
    <SceneFrame anchor="scene">
      {faces.map((face, i) => (
        <FaceBoundary key={FACES[i]} face={face} kind={kinds[i]} inset={inset[i]} palette={palette} dash={dash} bench={bench} />
      ))}
      {symmetry.map(({ axis, mode, side }) => (
        <SymmetryPlane key={axis} face={faces[axis * 2 + (side === 'high' ? 1 : 0)]} mode={mode} palette={palette} />
      ))}
      {selected && uniform && <Label position={top} color={palette.boundary}>{`Boundary · ${kindText(kinds[0])}`}</Label>}
      {selected &&
        !uniform &&
        faces.map((face, i) => {
          const at: Vec3 = [...face.center];
          at[face.axis] += face.side * domain.extent * 0.05;
          return (
            <Label key={FACES[i]} position={at} color={palette.boundary}>
              {`${AXIS_NAMES[face.axis]} ${face.side < 0 ? 'low' : 'high'} · ${kindText(kinds[i])}`}
            </Label>
          );
        })}
      {selected &&
        symmetry.map(({ axis, mode, side }) => {
          const face = faces[axis * 2 + (side === 'high' ? 1 : 0)];
          const at: Vec3 = [...face.center];
          at[(axis + 1) % 3] += face.size[(axis + 1) % 3] * 0.3;
          return (
            <Label key={`sym${axis}`} position={at} color={palette.boundary}>
              {`${mode} symmetry · ${AXIS_NAMES[axis]} ${side}`}
            </Label>
          );
        })}
      {selected && <GridTicks domain={domain} solver={solver} palette={palette} />}
    </SceneFrame>
  );
}

