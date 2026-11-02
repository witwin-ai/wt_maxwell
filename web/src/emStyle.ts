import type * as ThreeTypes from 'three';
import { React, THREE } from './runtime';
import type { HostSceneObject, ViewportHost } from './sdk/types';

/*
 * Shared look of the Maxwell scene annotations: colours, sizes relative to
 * the simulation domain, length labels, and component lookup.
 *
 * Colours follow the usual EM-design convention: sources blue, monitors
 * green and dashed, the PML boundary a neutral dashed grey. They are 3D
 * annotation colours, so they are literals rather than theme tokens.
 */

export const SOURCE_COLOR = '#2f7fe0'; /* allow-color: 3D source annotation */
export const MONITOR_COLOR = '#2fa565'; /* allow-color: 3D monitor annotation */
export const PML_COLOR = '#8f959c'; /* allow-color: 3D PML boundary annotation */

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

export interface Domain {
  min: Vec3;
  max: Vec3;
  /** Largest side, metres: the scale for arrows, markers and dashes. */
  extent: number;
}

const DEFAULT_DOMAIN: Domain = { min: [-1, -1, -1], max: [1, 1, 1], extent: 2 };

function domainKey(host: ViewportHost): string {
  for (const object of Object.values(host.scene.getObjects())) {
    const solver = findComponent(object, 'MaxwellSolver');
    if (solver) return JSON.stringify([vec3(solver, 'min_bound', [-1, -1, -1]), vec3(solver, 'max_bound', [1, 1, 1])]);
  }
  return '';
}

/**
 * The Maxwell domain of the scene, or a 2 m cube without a solver. A string
 * snapshot keeps useSyncExternalStore from re-rendering on unrelated edits.
 */
export function useDomain(host: ViewportHost): Domain {
  const key = React.useSyncExternalStore(host.scene.subscribe, () => domainKey(host));
  return React.useMemo(() => {
    if (!key) return DEFAULT_DOMAIN;
    const [min, max] = JSON.parse(key) as [Vec3, Vec3];
    const extent = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2], 1e-12);
    return { min, max, extent };
  }, [key]);
}

const UNITS: Array<[number, string]> = [
  [1, 'm'],
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

/**
 * Converts world points into the object's local frame. Annotations are drawn
 * inside the object's transform group, but some (an infinite plane monitor,
 * a TFSF box) are defined in world coordinates.
 */
export function worldToLocal(object: HostSceneObject): ThreeTypes.Matrix4 {
  const t = (object as { transform?: { position?: number[]; rotation?: number[]; scale?: number[] } }).transform ?? {};
  const position = new THREE.Vector3(...((t.position as Vec3) ?? [0, 0, 0]));
  const r = t.rotation ?? [0, 0, 0];
  const quaternion =
    r.length === 4 ? new THREE.Quaternion(r[0], r[1], r[2], r[3]) : new THREE.Quaternion().setFromEuler(new THREE.Euler(r[0], r[1], r[2]));
  const scale = new THREE.Vector3(...((t.scale as Vec3) ?? [1, 1, 1]));
  return new THREE.Matrix4().compose(position, quaternion, scale).invert();
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
