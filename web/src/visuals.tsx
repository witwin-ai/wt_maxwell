import type ReactTypes from 'react';
import { Line, React, THREE, useMemo } from './runtime';
import type { FrontendHost, HostSceneObject, SceneService } from '@witwin/host';
import { Arrow, PlaneRect } from './primitives';
import { ModePlane } from './ModePlane';
import {
  MONITOR_COLOR,
  PML_COLOR,
  SOURCE_COLOR,
  boxEdges,
  findComponent,
  useDomain,
  value,
  vec3,
  worldToLocal,
  type Domain,
  type Vec3,
} from './emStyle';

/*
 * Viewport annotations for the Maxwell components: sources in blue,
 * monitors dashed green, the PML boundary dashed grey. Each draws in its
 * object's local frame (the host wraps visualizers in the object transform);
 * the few defined in world coordinates go through worldToLocal.
 *
 * Sizes of markers, arrows and dashes scale with the simulation domain, so
 * an RF scene in metres and a photonic one in micrometres look alike.
 */

type VisualProps = { object: HostSceneObject; selected: boolean; hovered: boolean };

const AXIS_INDEX: Record<string, number> = { x: 0, y: 1, z: 2, Ex: 0, Ey: 1, Ez: 2 };

function axisVector(axis: number): Vec3 {
  const v: Vec3 = [0, 0, 0];
  v[axis] = 1;
  return v;
}

/** World-space points brought into the object's frame. */
function toLocal(object: HostSceneObject, points: Vec3[]): Vec3[] {
  const m = worldToLocal(object);
  return points.map((p) => new THREE.Vector3(...p).applyMatrix4(m).toArray() as Vec3);
}

function DashedBox({ object, min, max, color, dash, opacity = 1 }: { object: HostSceneObject; min: Vec3; max: Vec3; color: string; dash: number; opacity?: number }) {
  const points = useMemo(() => toLocal(object, boxEdges(min, max)), [object, ...min, ...max]);
  return <Line points={points} segments color={color} lineWidth={1.25} dashed dashSize={dash} gapSize={dash * 0.7} transparent opacity={opacity} />;
}

// ---------- sources ----------

function polarizationOf(component: any): Vec3 {
  const mode = String(value(component, 'polarization_mode', 'Ez'));
  return mode === 'vector' ? vec3(component, 'polarization', [0, 0, 1]) : axisVector(AXIS_INDEX[mode] ?? 2);
}

function PointDipole({ component, domain }: { component: any; domain: Domain }) {
  const r = domain.extent * 0.012;
  return (
    <group>
      <mesh>
        <sphereGeometry args={[r, 16, 12]} />
        <meshBasicMaterial color={SOURCE_COLOR} toneMapped={false} />
      </mesh>
      <Arrow origin={[0, 0, 0]} direction={polarizationOf(component)} length={domain.extent * 0.1} color={SOURCE_COLOR} />
    </group>
  );
}

/** Plane wave or Gaussian beam: propagation arrow, a short polarization arrow, and the TFSF box when used. */
function DirectedWave({ object, component, domain, selected }: { object: HostSceneObject; component: any; domain: Domain; selected: boolean }) {
  const tfsf = value<string>(component, 'injection', 'soft') === 'tfsf';
  return (
    <group>
      <Arrow origin={[0, 0, 0]} direction={vec3(component, 'direction', [0, 0, 1])} length={domain.extent * 0.15} color={SOURCE_COLOR} />
      <Arrow origin={[0, 0, 0]} direction={vec3(component, 'polarization', [1, 0, 0])} length={domain.extent * 0.06} color={SOURCE_COLOR} />
      {tfsf && (
        <DashedBox
          object={object}
          min={vec3(component, 'tfsf_min', [-0.5, -0.5, -0.5])}
          max={vec3(component, 'tfsf_max', [0.5, 0.5, 0.5])}
          color={SOURCE_COLOR}
          dash={domain.extent * 0.015}
          opacity={selected ? 1 : 0.6}
        />
      )}
    </group>
  );
}

// ---------- monitors ----------

function PointMonitor({ domain }: { domain: Domain }) {
  const s = domain.extent * 0.015;
  const segments: Vec3[] = [
    [-s, 0, 0], [s, 0, 0],
    [0, -s, 0], [0, s, 0],
    [0, 0, -s], [0, 0, s],
  ];
  return <Line points={segments} segments color={MONITOR_COLOR} lineWidth={2} />;
}

/** Infinite plane monitor: drawn where it cuts the domain. Its position is a field, in world coordinates. */
function PlaneMonitor({ object, component, domain }: { object: HostSceneObject; component: any; domain: Domain }) {
  const axis = AXIS_INDEX[String(value(component, 'axis', 'z'))] ?? 2;
  const position = Number(value(component, 'position', 0));
  const corners = useMemo(() => {
    const center: Vec3 = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2) as Vec3;
    center[axis] = position;
    const size: Vec3 = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]) as Vec3;
    size[axis] = 0;
    return { center, size };
  }, [axis, position, domain]);
  const m = worldToLocal(object);
  const local = new THREE.Vector3(...corners.center).applyMatrix4(m).toArray() as Vec3;
  return (
    <PlaneRect
      center={local}
      size={corners.size}
      color={MONITOR_COLOR}
      dashed
      dash={domain.extent * 0.012}
      fillOpacity={value(component, 'compute_flux', false) ? 0.12 : 0.04}
    />
  );
}

function FinitePlaneMonitor({ component, domain }: { component: any; domain: Domain }) {
  return (
    <PlaneRect
      center={[0, 0, 0]}
      size={vec3(component, 'size', [1, 1, 0])}
      color={MONITOR_COLOR}
      dashed
      dash={domain.extent * 0.012}
      fillOpacity={value(component, 'compute_flux', false) ? 0.12 : 0.04}
    />
  );
}

function ClosedSurfaceMonitor({ component, domain }: { component: any; domain: Domain }) {
  const size = vec3(component, 'size', [1, 1, 1]);
  const half = size.map((s) => s / 2) as Vec3;
  const segments = useMemo(() => boxEdges([-half[0], -half[1], -half[2]], half), [...half]);
  return <Line points={segments} segments color={MONITOR_COLOR} lineWidth={1.25} dashed dashSize={domain.extent * 0.012} gapSize={domain.extent * 0.008} />;
}

// ---------- solver ----------

/** Dashed inner box where the PML starts; drawn when any face is a PML. */
function PmlBox({ object, component, domain }: { object: HostSceneObject; component: any; domain: Domain }) {
  const inset = value<number[] | null>(component, 'pml_inset', null);
  if (!Array.isArray(inset) || inset.length !== 6 || inset.every((t) => !(t > 0))) return null;
  const min = vec3(component, 'min_bound', domain.min);
  const max = vec3(component, 'max_bound', domain.max);
  const innerMin = [0, 1, 2].map((a) => min[a] + inset[2 * a]) as Vec3;
  const innerMax = [0, 1, 2].map((a) => max[a] - inset[2 * a + 1]) as Vec3;
  if ([0, 1, 2].some((a) => innerMin[a] >= innerMax[a])) return null;
  return <DashedBox object={object} min={innerMin} max={innerMax} color={PML_COLOR} dash={domain.extent * 0.015} opacity={0.8} />;
}

// ---------- registration ----------

type Visual = {
  component: string;
  render: (args: { scene: SceneService; object: HostSceneObject; component: any; domain: Domain; selected: boolean }) => ReactTypes.ReactNode;
};

const SOURCE_AND_MONITOR_VISUALS: Visual[] = [
  { component: 'PointDipoleSource', render: ({ component, domain }) => <PointDipole component={component} domain={domain} /> },
  { component: 'PlaneWaveSource', render: (a) => <DirectedWave {...a} /> },
  { component: 'GaussianBeamSource', render: (a) => <DirectedWave {...a} /> },
  { component: 'ModeSource', render: (a) => <ModePlane {...a} color={SOURCE_COLOR} dashed={false} /> },
  { component: 'PointMonitor', render: ({ domain }) => <PointMonitor domain={domain} /> },
  { component: 'PlaneMonitor', render: (a) => <PlaneMonitor {...a} /> },
  { component: 'FinitePlaneMonitor', render: (a) => <FinitePlaneMonitor {...a} /> },
  { component: 'ClosedSurfaceMonitor', render: (a) => <ClosedSurfaceMonitor {...a} /> },
  { component: 'ModeMonitor', render: (a) => <ModePlane {...a} color={MONITOR_COLOR} dashed /> },
];

export function registerMaxwellVisuals(host: FrontendHost): void {
  const scene = host.services.get('scene');
  for (const visual of SOURCE_AND_MONITOR_VISUALS) {
    function MaxwellVisual({ object, selected }: VisualProps) {
      const domain = useDomain(scene);
      const component = findComponent(object, visual.component);
      if (!component || object.visible === false) return null;
      return <>{visual.render({ scene, object, component, domain, selected })}</>;
    }
    host.registerVisualizer({
      id: `witwin.maxwell.${visual.component}`,
      priority: 80,
      skipStandardGeometry: true,
      match: (object) => !!findComponent(object, visual.component),
      component: MaxwellVisual,
    });
  }

  // A gizmo, not a visualizer: wt_volume's Field visualizer still draws the
  // solver's domain box and field; this only adds the PML boundary.
  function MaxwellPml({ object }: VisualProps) {
    const domain = useDomain(scene);
    const component = findComponent(object, 'MaxwellSolver');
    return component && object.visible !== false ? <PmlBox object={object} component={component} domain={domain} /> : null;
  }
  host.registerGizmo({
    id: 'witwin.maxwell.pml',
    priority: 80,
    match: (object) => !!findComponent(object, 'MaxwellSolver'),
    component: MaxwellPml,
  });
}
