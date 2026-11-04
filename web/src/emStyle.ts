import { React } from './runtime';
import type { HostSceneObject, SceneService, ViewportStage, ViewportStagePalette } from '@witwin/host';

/*
 * Shared look of the Maxwell scene annotations: role colours from the
 * stage palette, sizes relative to the simulation domain, length and
 * frequency labels, and component lookup.
 *
 * Colours come from the host's stage palette by role: sources are
 * `emitter`, monitors `sensor`, the boundary `boundary`, design regions
 * `region`. FALLBACK_PALETTE is only for hosts from before the palette.
 */

/** Hosts without the stage palette: the values of Studio's dark Bench palette. */
const FALLBACK_PALETTE: ViewportStagePalette = {
  background: '#434345', /* allow-color: 3D fallback for hosts without the stage palette */
  edge: '#d4d4d8', /* allow-color: 3D fallback */
  text: '#f4f4f5', /* allow-color: 3D fallback */
  accent: '#0066cc', /* allow-color: 3D fallback */
  emitter: '#fb923c', /* allow-color: 3D fallback */
  sensor: '#4ade80', /* allow-color: 3D fallback */
  boundary: '#a1a1aa', /* allow-color: 3D fallback */
  region: '#a78bfa', /* allow-color: 3D fallback */
  warning: '#f87171', /* allow-color: 3D fallback */
};

export function paletteOf(stage: ViewportStage | undefined): ViewportStagePalette {
  return stage?.palette ?? FALLBACK_PALETTE;
}

export type Vec3 = [number, number, number];

export function findComponent(object: HostSceneObject | undefined, name: string): any | null {
  const components = Array.isArray(object?.components) ? object!.components : [];
  return components.find((c: any) => c?.name === name || c?.base_classes?.includes?.(name)) ?? null;
}

export function value<T>(component: any, name: string, fallback: T): T {
  const v = component?.values?.[name];
  return v === undefined || v === null ? fallback : (v as T);
}

export function vec3(component: any, name: string, fallback: Vec3): Vec3 {
  const v = value<unknown>(component, name, fallback);
  return Array.isArray(v) && v.length >= 3 ? [Number(v[0]), Number(v[1]), Number(v[2])] : fallback;
}

/** An object's position in its parent's frame; the composed object may carry a three Vector3 or an array. */
export function positionOf(object: HostSceneObject | undefined): Vec3 {
  const p = (object as { transform?: { position?: unknown } } | undefined)?.transform?.position as any;
  if (Array.isArray(p)) return [Number(p[0]) || 0, Number(p[1]) || 0, Number(p[2]) || 0];
  if (p && typeof p === 'object') return [Number(p.x) || 0, Number(p.y) || 0, Number(p.z) || 0];
  return [0, 0, 0];
}

export interface Domain {
  /** Scene coordinates, metres: the solver object's position plus its bounds, as the solve builds it. */
  min: Vec3;
  max: Vec3;
  /** Largest side, metres: the scale for arrows, markers and dashes. */
  extent: number;
  /** False when the scene has no MaxwellSolver (a 2 m cube stands in). */
  real: boolean;
}

const DEFAULT_DOMAIN: Domain = { min: [-1, -1, -1], max: [1, 1, 1], extent: 2, real: false };

function domainKey(scene: SceneService): string {
  for (const object of Object.values(scene.getObjects())) {
    const solver = findComponent(object, 'MaxwellSolver');
    if (!solver) continue;
    // adapter/settings_map.py _build_domain: bounds plus the solver's world translation; rotation and scale are not used.
    const offset = positionOf(object);
    const lo = vec3(solver, 'min_bound', [-1, -1, -1]).map((v, i) => v + offset[i]);
    const hi = vec3(solver, 'max_bound', [1, 1, 1]).map((v, i) => v + offset[i]);
    return JSON.stringify([lo, hi]);
  }
  return '';
}

/**
 * The Maxwell domain of the scene, or a 2 m cube without a solver. A string
 * snapshot keeps useSyncExternalStore from re-rendering on unrelated edits.
 */
export function useDomain(scene: SceneService): Domain {
  const subscribe = React.useCallback((onChange: () => void) => {
    const subscription = scene.subscribe(onChange);
    return () => subscription.dispose();
  }, [scene]);
  const key = React.useSyncExternalStore(subscribe, () => domainKey(scene));
  return React.useMemo(() => {
    if (!key) return DEFAULT_DOMAIN;
    const [min, max] = JSON.parse(key) as [Vec3, Vec3];
    const extent = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2], 1e-12);
    return { min, max, extent, real: true };
  }, [key]);
}

/** True when `p` (scene coordinates) lies in the domain, with a small tolerance for points on a face. */
export function insideDomain(domain: Domain, p: Vec3): boolean {
  if (!domain.real) return true;
  const tol = domain.extent * 1e-6;
  return [0, 1, 2].every((a) => p[a] >= domain.min[a] - tol && p[a] <= domain.max[a] + tol);
}

const UNITS: Array<[number, string]> = [
  [1, 'm'],
  [1e-2, 'cm'],
  [1e-3, 'mm'],
  [1e-6, 'µm'],
  [1e-9, 'nm'],
];

/** "1.50 µm": three significant digits in the largest unit that keeps the value at least 1. */
export function formatLength(metres: number): string {
  const a = Math.abs(metres);
  const [scale, name] = UNITS.find(([s]) => a >= s) ?? UNITS[UNITS.length - 1];
  return `${Number((metres / scale).toPrecision(3))} ${name}`;
}

const FREQUENCY_UNITS: Array<[number, string]> = [
  [1e12, 'THz'],
  [1e9, 'GHz'],
  [1e6, 'MHz'],
  [1e3, 'kHz'],
  [1, 'Hz'],
];

/** "2.4 GHz": three significant digits in the largest unit that keeps the value at least 1. */
export function formatFrequency(hz: number): string {
  const a = Math.abs(hz);
  const [scale, name] = FREQUENCY_UNITS.find(([s]) => a >= s) ?? FREQUENCY_UNITS[FREQUENCY_UNITS.length - 1];
  return `${Number((hz / scale).toPrecision(3))} ${name}`;
}

/** Corners, in loop order, of an axis-aligned rectangle with one zero side centred on `center`. */
export function rectCorners(center: Vec3, size: Vec3): Vec3[] {
  const normal = normalAxis(size);
  const [u, v] = [0, 1, 2].filter((d) => d !== normal);
  const corner = (su: number, sv: number): Vec3 => {
    const p: Vec3 = [...center];
    p[u] = center[u] + (su * size[u]) / 2;
    p[v] = center[v] + (sv * size[v]) / 2;
    return p;
  };
  return [corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, 1)];
}

/** The plane's normal: its zero (else smallest) side. */
export function normalAxis(size: Vec3): number {
  let n = 0;
  for (let a = 1; a < 3; a++) if (Math.abs(size[a]) < Math.abs(size[n])) n = a;
  return n;
}

/** The 12 edges of an axis-aligned box, as segment pairs for drei Line's `segments`. */
export function boxEdges(min: Vec3, max: Vec3): Vec3[] {
  const c = (i: number): Vec3 => [i & 1 ? max[0] : min[0], i & 2 ? max[1] : min[1], i & 4 ? max[2] : min[2]];
  const out: Vec3[] = [];
  for (let i = 0; i < 8; i++) {
    for (const bit of [1, 2, 4]) if (!(i & bit)) out.push(c(i), c(i | bit));
  }
  return out;
}

export const AXIS_INDEX: Record<string, number> = { x: 0, y: 1, z: 2, Ex: 0, Ey: 1, Ez: 2 };
export const AXIS_NAMES = ['x', 'y', 'z'] as const;

export function axisVector(axis: number, sign = 1): Vec3 {
  const v: Vec3 = [0, 0, 0];
  v[axis] = sign;
  return v;
}

export function add(a: Vec3, b: Vec3): Vec3 {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

export function sub(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}
