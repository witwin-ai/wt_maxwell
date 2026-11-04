import type ReactTypes from 'react';
import type * as ThreeTypes from 'three';
import type { FrontendHost, HostSceneObject, SceneService, TransformToolName, ViewportObjectProps, ViewportStage, ViewportStagePalette } from '@witwin/host';
import { Line, React, THREE, useMemo } from './runtime';
import { Arrow, BoxFill, HitBox, HitPlane, HitSphere, Label, PlaneRect, Ring, SceneFrame, noRaycast } from './primitives';
import { ModePlane } from './ModePlane';
import { SolverAnnotations, cellSize } from './boundary';
import { BoxHandles, PositionHandle, type Box } from './handles';
import { OFFSET_KEY, setPreview, usePreview, withPreview } from './preview';
import { sourceTimeLabel } from './sourceTime';
import {
  AXIS_INDEX,
  AXIS_NAMES,
  add,
  axisVector,
  boxEdges,
  findComponent,
  formatLength,
  insideDomain,
  normalAxis,
  paletteOf,
  positionOf,
  useDomain,
  value,
  vec3,
  type Domain,
  type Vec3,
} from './emStyle';

/*
 * The Maxwell components in the Scene view. Each annotation is coloured by
 * its role from the stage palette (sources `emitter`, monitors `sensor`,
 * boundaries `boundary`, design regions `region`), has an invisible soft
 * click target, and shows a label while selected. An annotation the solve
 * would drop (outside the domain) draws in `warning`.
 *
 * Everything draws axis-aligned around the object's scene position
 * (SceneFrame), because the solve reads only the position of a source or
 * monitor, never its rotation or scale. Domain bounds, TFSF boxes and
 * infinite planes are scene coordinates.
 *
 * Marker sizes scale with the simulation domain, so an RF scene in metres
 * and a photonic one in micrometres look alike.
 */

interface Ctx {
  scene: SceneService;
  object: HostSceneObject;
  component: any;
  domain: Domain;
  selected: boolean;
  stage?: ViewportStage;
  palette: ViewportStagePalette;
  /** Object origin in scene coordinates, with any drag preview applied. */
  origin: Vec3;
}

function fieldsText(component: any): string {
  const fields = value<string[]>(component, 'fields', []);
  return Array.isArray(fields) && fields.length ? fields.join(', ') : '';
}

function joinLabel(...parts: Array<string | null | undefined | false>): string {
  return parts.filter(Boolean).join(' · ');
}

// ---------- oriented square (plane-wave wavefront) ----------

function basis(direction: Vec3, hint: Vec3): { n: ThreeTypes.Vector3; e1: ThreeTypes.Vector3; e2: ThreeTypes.Vector3 } {
  const n = new THREE.Vector3(...direction);
  if (n.lengthSq() < 1e-20) n.set(0, 0, 1);
  n.normalize();
  const e1 = new THREE.Vector3(...hint).projectOnPlane(n);
  if (e1.lengthSq() < 1e-12) e1.copy(Math.abs(n.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0)).projectOnPlane(n);
  e1.normalize();
  return { n, e1, e2: new THREE.Vector3().crossVectors(n, e1) };
}

function Wavefront({ center, direction, polarization, side, color, opacity }: { center: Vec3; direction: Vec3; polarization: Vec3; side: number; color: string; opacity: number }) {
  const { loop, fill } = useMemo(() => {
    const { e1, e2 } = basis(direction, polarization);
    const c = new THREE.Vector3(...center);
    const h = side / 2;
    const corners = [
      [-h, -h],
      [h, -h],
      [h, h],
      [-h, h],
    ].map(([a, b]) => c.clone().addScaledVector(e1, a).addScaledVector(e2, b));
    const geometry = new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]);
    return { loop: [...corners, corners[0]].map((p) => p.toArray() as Vec3), fill: geometry };
  }, [...center, ...direction, ...polarization, side]);
  React.useEffect(() => () => fill.dispose(), [fill]);
  return (
    <group>
      <Line points={loop} color={color} lineWidth={1.5} transparent={opacity < 1} opacity={opacity} raycast={noRaycast} />
      <mesh geometry={fill} renderOrder={1} raycast={noRaycast}>
        <meshBasicMaterial color={color} transparent opacity={0.16 * opacity} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
      </mesh>
    </group>
  );
}

// ---------- sources ----------

function polarizationOf(component: any): Vec3 {
  const mode = String(value(component, 'polarization_mode', 'Ez'));
  return mode === 'vector' ? vec3(component, 'polarization', [0, 0, 1]) : axisVector(AXIS_INDEX[mode] ?? 2);
}

function PointDipole({ component, domain, selected, palette, origin }: Ctx) {
  const r = domain.extent * 0.012;
  const p = new THREE.Vector3(...polarizationOf(component)).normalize();
  const length = domain.extent * 0.1;
  const color = insideDomain(domain, origin) ? palette.emitter : palette.warning;
  const mode = String(value(component, 'polarization_mode', 'Ez'));
  return (
    <group>
      <mesh raycast={noRaycast}>
        <sphereGeometry args={[r, 16, 12]} />
        <meshBasicMaterial color={color} toneMapped={false} />
      </mesh>
      <Arrow origin={p.clone().multiplyScalar(-length / 2).toArray() as Vec3} direction={p.toArray() as Vec3} length={length} color={color} />
      <HitSphere radius={r * 3} />
      {selected && (
        <Label position={[0, r * 4, 0]} color={color}>
          {joinLabel(`Dipole ${mode === 'vector' ? 'p' : mode}`, sourceTimeLabel(component), color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

/** Plane wave or Gaussian beam: a wavefront plate with k and E arrows; the TFSF box and the beam waist. */
function DirectedWave({ component, domain, selected, palette, origin, gaussian }: Ctx & { gaussian: boolean }) {
  const direction = vec3(component, 'direction', [0, 0, 1]);
  const polarization = vec3(component, 'polarization', [1, 0, 0]);
  const { n, e1 } = basis(direction, polarization);
  const side = domain.extent * 0.22;
  const crest = domain.extent * 0.035;
  const color = insideDomain(domain, origin) ? palette.emitter : palette.warning;
  const name = gaussian ? 'Gaussian beam' : 'Plane wave';
  const tfsf = value<string>(component, 'injection', 'soft') === 'tfsf';
  return (
    <group>
      {[0, 1, 2].map((i) => (
        <Wavefront
          key={i}
          center={n.clone().multiplyScalar(i * crest).toArray() as Vec3}
          direction={direction}
          polarization={polarization}
          side={side}
          color={color}
          opacity={[1, 0.5, 0.25][i]}
        />
      ))}
      <Arrow origin={[0, 0, 0]} direction={n.toArray() as Vec3} length={domain.extent * 0.16} color={color} />
      <Arrow origin={[0, 0, 0]} direction={e1.toArray() as Vec3} length={side * 0.42} color={color} lineWidth={1.25} opacity={0.85} />
      <HitSphere radius={side * 0.5} />
      {selected && (
        <Label position={[0, side * 0.7, 0]} color={color}>
          {joinLabel(name, tfsf && 'TFSF', sourceTimeLabel(component), color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

/** Scene-coordinate parts of a directed source: the TFSF box and the Gaussian waist at the focus. */
function DirectedWaveScene({ component, domain, palette, gaussian }: Ctx & { gaussian: boolean }) {
  const tfsf = value<string>(component, 'injection', 'soft') === 'tfsf';
  const min = vec3(component, 'tfsf_min', [-0.5, -0.5, -0.5]);
  const max = vec3(component, 'tfsf_max', [0.5, 0.5, 0.5]);
  const focus = vec3(component, 'focus', [0, 0, 0]);
  const edges = useMemo(() => boxEdges(min, max), [...min, ...max]);
  const marker = domain.extent * 0.012;
  return (
    <group>
      {tfsf && (
        <group>
          <Line points={edges} segments color={palette.emitter} lineWidth={1.25} raycast={noRaycast} />
          <BoxFill min={min} max={max} color={palette.emitter} opacity={0.035} />
        </group>
      )}
      {gaussian && (
        <group>
          <Ring center={focus} normal={vec3(component, 'direction', [0, 0, 1])} radius={Math.max(Number(value(component, 'beam_waist', 0.5)), 1e-12)} color={palette.emitter} dashed dash={domain.extent * 0.012} />
          <Line
            points={[add(focus, [-marker, 0, 0]), add(focus, [marker, 0, 0]), add(focus, [0, -marker, 0]), add(focus, [0, marker, 0]), add(focus, [0, 0, -marker]), add(focus, [0, 0, marker])]}
            segments
            color={palette.emitter}
            lineWidth={1.5}
            raycast={noRaycast}
          />
        </group>
      )}
    </group>
  );
}

// ---------- monitors ----------

function PointMonitor({ component, domain, selected, palette, origin }: Ctx) {
  const s = domain.extent * 0.016;
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  return (
    <group>
      <mesh raycast={noRaycast}>
        <octahedronGeometry args={[s]} />
        <meshBasicMaterial color={color} wireframe toneMapped={false} />
      </mesh>
      <mesh raycast={noRaycast} renderOrder={1}>
        <octahedronGeometry args={[s * 0.98]} />
        <meshBasicMaterial color={color} transparent opacity={0.25} depthWrite={false} toneMapped={false} />
      </mesh>
      <HitSphere radius={s * 2.5} />
      {selected && (
        <Label position={[0, s * 2.2, 0]} color={color}>
          {joinLabel('Point monitor', fieldsText(component), color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

function FluxArrow({ center, normal, component, domain, color }: { center: Vec3; normal: number; component: any; domain: Domain; color: string }) {
  if (!value(component, 'compute_flux', false)) return null;
  const sign = value<string>(component, 'normal_direction', '+') === '-' ? -1 : 1;
  return <Arrow origin={center} direction={axisVector(normal, sign)} length={domain.extent * 0.08} color={color} />;
}

/** Infinite plane monitor, in scene coordinates: drawn where it cuts the domain. */
function PlaneMonitorScene({ component, domain, selected, palette }: Ctx) {
  const axis = AXIS_INDEX[String(value(component, 'axis', 'z'))] ?? 2;
  const position = Number(value(component, 'position', 0));
  const center = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2) as Vec3;
  center[axis] = position;
  const size = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]) as Vec3;
  size[axis] = 0;
  const color = insideDomain(domain, center) ? palette.sensor : palette.warning;
  const flux = !!value(component, 'compute_flux', false);
  const labelAt: Vec3 = [...center];
  labelAt[(axis + 1) % 3] = domain.max[(axis + 1) % 3];
  return (
    <group>
      <PlaneRect center={center} size={size} color={color} dashed dash={domain.extent * 0.012} fillOpacity={flux ? 0.12 : 0.05} />
      <FluxArrow center={center} normal={axis} component={component} domain={domain} color={color} />
      <HitPlane center={center} size={size} />
      {selected && (
        <Label position={labelAt} color={color}>
          {joinLabel(flux ? 'Flux monitor' : 'Plane monitor', fieldsText(component), `${AXIS_NAMES[axis]} = ${formatLength(position)}`, color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

function FinitePlaneMonitor({ component, domain, selected, palette, origin }: Ctx) {
  const size = vec3(component, 'size', [1, 1, 0]);
  const normal = normalAxis(size);
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  const flux = !!value(component, 'compute_flux', false);
  const labelAt: Vec3 = [0, 0, 0];
  labelAt[(normal + 1) % 3] = size[(normal + 1) % 3] / 2 + domain.extent * 0.03;
  return (
    <group>
      <PlaneRect center={[0, 0, 0]} size={size} color={color} dashed dash={domain.extent * 0.012} fillOpacity={flux ? 0.12 : 0.05} />
      <FluxArrow center={[0, 0, 0]} normal={normal} component={component} domain={domain} color={color} />
      <HitPlane center={[0, 0, 0]} size={size} />
      {selected && (
        <Label position={labelAt} color={color}>
          {joinLabel(flux ? 'Flux monitor' : 'Plane monitor', fieldsText(component), color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

function ClosedSurfaceMonitor({ component, domain, selected, palette, origin }: Ctx) {
  const size = vec3(component, 'size', [1, 1, 1]);
  const half = size.map((s) => s / 2) as Vec3;
  const min = half.map((h) => -h) as Vec3;
  const segments = useMemo(() => boxEdges(min, half), [...half]);
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  return (
    <group>
      <Line points={segments} segments color={color} lineWidth={1.25} dashed dashSize={domain.extent * 0.012} gapSize={domain.extent * 0.008} raycast={noRaycast} />
      <BoxFill min={min} max={half} color={color} opacity={0.035} />
      <HitBox min={min} max={half} />
      {selected && (
        <Label position={[0, half[1] + domain.extent * 0.04, 0]} color={color}>
          {joinLabel('Closed surface', 'flux', color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

function ModePlaneVisual(props: Ctx & { color: string; dashed: boolean; title: string; time?: string | null }) {
  const { component, domain, selected, palette, origin, color: base, dashed, title, time } = props;
  const size = vec3(component, 'size', [1, 1, 0]);
  const normal = normalAxis(size);
  const color = insideDomain(domain, origin) ? base : palette.warning;
  const labelAt: Vec3 = [0, 0, 0];
  labelAt[(normal + 1) % 3] = -size[(normal + 1) % 3] / 2 - domain.extent * 0.05;
  return (
    <group>
      <ModePlane scene={props.scene} object={props.object} component={component} selected={selected} domain={domain} color={color} dashed={dashed} />
      <HitPlane center={[0, 0, 0]} size={size} />
      {selected && (
        <Label position={labelAt} color={color}>
          {joinLabel(title, `mode ${Number(value(component, 'mode_index', 0))}`, time, color === palette.warning && 'Outside domain')}
        </Label>
      )}
    </group>
  );
}

/** ModePort: one plane that excites (emitter) or only records (sensor), plus its monitor plane at `monitor_offset`. */
function ModePort(props: Ctx) {
  const { component, domain, palette } = props;
  const exciting = !!value(component, 'is_source', false);
  const size = vec3(component, 'size', [1, 1, 0]);
  const normal = normalAxis(size);
  const offset = Number(value(component, 'monitor_offset', 0));
  const monitorCenter = axisVector(normal, offset);
  return (
    <group>
      <ModePlaneVisual
        {...props}
        color={exciting ? palette.emitter : palette.sensor}
        dashed={false}
        title={exciting ? 'Port · source' : 'Port'}
        time={exciting ? sourceTimeLabel(component, 'is_source') : null}
      />
      {exciting && offset !== 0 && <PlaneRect center={monitorCenter} size={size} color={palette.sensor} dashed dash={domain.extent * 0.012} />}
    </group>
  );
}

// ---------- design region ----------

/** MaterialRegion on its box mesh (the object's unit cube): region outline, and the design grid while selected. */
function MaterialRegion({ component, selected, palette }: { component: any; selected: boolean; palette: ViewportStagePalette }) {
  const n = [value(component, 'density_nx', 8), value(component, 'density_ny', 8), value(component, 'density_nz', 8)].map((v) => Math.max(1, Math.min(32, Math.round(Number(v))))) as Vec3;
  const edges = useMemo(() => boxEdges([-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]), []);
  const lattice = useMemo(() => {
    // Grid lines on the three faces at the low corner; drawing all of them inside the box would hide the part.
    const out: Vec3[] = [];
    for (let face = 0; face < 3; face++) {
      const [u, v] = [0, 1, 2].filter((a) => a !== face);
      for (const [along, across] of [
        [u, v],
        [v, u],
      ]) {
        for (let k = 1; k < n[across]; k++) {
          const a: Vec3 = [-0.5, -0.5, -0.5];
          a[across] = -0.5 + k / n[across];
          const b: Vec3 = [...a];
          b[along] = 0.5;
          out.push(a, b);
        }
      }
    }
    return out;
  }, [...n]);
  const name = String(value(component, 'region_name', '')) || 'Design region';
  return (
    <group>
      <Line points={edges} segments color={palette.region} lineWidth={1.75} raycast={noRaycast} />
      {selected && <Line points={lattice} segments color={palette.region} lineWidth={1} transparent opacity={0.55} raycast={noRaycast} />}
      {selected && <Label position={[0, 0.62, 0]} color={palette.region}>{joinLabel(name, `${n.join(' × ')} density`)}</Label>}
    </group>
  );
}

// ---------- registration ----------

type Visual = {
  component: string;
  /** Drawn axis-aligned around the object's scene position. */
  local?: (ctx: Ctx) => ReactTypes.ReactNode;
  /** Drawn in scene coordinates. */
  scene?: (ctx: Ctx) => ReactTypes.ReactNode;
};

const VISUALS: Visual[] = [
  { component: 'PointDipoleSource', local: (c) => <PointDipole {...c} /> },
  { component: 'PlaneWaveSource', local: (c) => <DirectedWave {...c} gaussian={false} />, scene: (c) => <DirectedWaveScene {...c} gaussian={false} /> },
  { component: 'GaussianBeamSource', local: (c) => <DirectedWave {...c} gaussian />, scene: (c) => <DirectedWaveScene {...c} gaussian /> },
  { component: 'ModeSource', local: (c) => <ModePlaneVisual {...c} color={c.palette.emitter} dashed={false} title="Mode source" time={sourceTimeLabel(c.component)} /> },
  { component: 'PointMonitor', local: (c) => <PointMonitor {...c} /> },
  { component: 'PlaneMonitor', scene: (c) => <PlaneMonitorScene {...c} /> },
  { component: 'FinitePlaneMonitor', local: (c) => <FinitePlaneMonitor {...c} /> },
  { component: 'ClosedSurfaceMonitor', local: (c) => <ClosedSurfaceMonitor {...c} /> },
  { component: 'ModeMonitor', local: (c) => <ModePlaneVisual {...c} color={c.palette.sensor} dashed title="Mode monitor" /> },
  { component: 'ModePort', local: (c) => <ModePort {...c} /> },
];

/** Components whose `size` is a plane (one zero side) or a box, resized by face handles. */
const SIZED = new Set(['FinitePlaneMonitor', 'ModeMonitor', 'ModeSource', 'ModePort', 'ClosedSurfaceMonitor']);

function solverOf(scene: SceneService): any | null {
  for (const object of Object.values(scene.getObjects())) {
    const solver = findComponent(object, 'MaxwellSolver');
    if (solver) return solver;
  }
  return null;
}

function offsetOf(preview: Record<string, unknown> | null): Vec3 | undefined {
  const v = preview?.[OFFSET_KEY];
  return Array.isArray(v) ? (v as Vec3) : undefined;
}

/** Handles of one Maxwell object under the Bounds tool. */
function MaxwellHandles({ host, scene, object, name, domain, palette }: { host: FrontendHost; scene: SceneService; object: HostSceneObject; name: string; domain: Domain; palette: ViewportStagePalette }) {
  const preview = usePreview(object.id);
  const component = withPreview(findComponent(object, name), preview);
  const solver = solverOf(scene);
  const cell = solver ? cellSize(solver) : 0;
  const minSize = cell > 0 ? cell : domain.extent * 1e-3;
  const interaction = host.interaction;
  const offset = offsetOf(preview);
  const done = (writes: Array<Promise<void>>) => {
    void Promise.allSettled(writes).then(() => setPreview(object.id, null));
  };

  if (SIZED.has(name)) {
    const size = vec3(component, 'size', [1, 1, 1]);
    const plane = name !== 'ClosedSurfaceMonitor';
    const normal = normalAxis(size);
    const axes = plane ? [0, 1, 2].filter((a) => a !== normal) : [0, 1, 2];
    const shift = offset ?? [0, 0, 0];
    const box: Box = { min: size.map((s, a) => shift[a] - s / 2) as Vec3, max: size.map((s, a) => shift[a] + s / 2) as Vec3 };
    const toFields = (b: Box) => {
      const nextSize = [0, 1, 2].map((a) => (plane && a === normal ? 0 : b.max[a] - b.min[a])) as Vec3;
      const centre = [0, 1, 2].map((a) => (plane && a === normal ? 0 : (b.min[a] + b.max[a]) / 2)) as Vec3;
      return { nextSize, centre };
    };
    return (
      <SceneFrame anchor="object">
        <BoxHandles
          box={box}
          axes={axes}
          color={palette.accent}
          cell={cell}
          minSize={minSize}
          interaction={interaction}
          onPreview={(b) => {
            const { nextSize, centre } = toFields(b);
            setPreview(object.id, { size: nextSize, [OFFSET_KEY]: centre });
          }}
          onCommit={(b) => {
            const { nextSize, centre } = toFields(b);
            const writes = [scene.updateComponentField(object.id, name, 'size', nextSize)];
            // The solve reads the object's position only; a one-sided resize moves the centre.
            if (centre.some((c) => Math.abs(c) > 1e-12)) {
              writes.push(scene.updateObjectTransform(object.id, { position: add(positionOf(object), centre) }));
            }
            done(writes);
          }}
        />
      </SceneFrame>
    );
  }

  if ((name === 'PlaneWaveSource' || name === 'GaussianBeamSource') && value<string>(component, 'injection', 'soft') === 'tfsf') {
    const box: Box = { min: vec3(component, 'tfsf_min', [-0.5, -0.5, -0.5]), max: vec3(component, 'tfsf_max', [0.5, 0.5, 0.5]) };
    return (
      <SceneFrame anchor="scene">
        <BoxHandles
          box={box}
          axes={[0, 1, 2]}
          color={palette.accent}
          cell={cell}
          minSize={minSize}
          interaction={interaction}
          onPreview={(b) => setPreview(object.id, { tfsf_min: b.min, tfsf_max: b.max })}
          onCommit={(b) =>
            done([scene.updateComponentField(object.id, name, 'tfsf_min', b.min), scene.updateComponentField(object.id, name, 'tfsf_max', b.max)])
          }
        />
      </SceneFrame>
    );
  }

  if (name === 'PlaneMonitor') {
    const axis = AXIS_INDEX[String(value(component, 'axis', 'z'))] ?? 2;
    const at = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2) as Vec3;
    at[axis] = Number(value(component, 'position', 0));
    return (
      <SceneFrame anchor="scene">
        <PositionHandle
          position={at}
          axis={axis}
          color={palette.accent}
          cell={cell}
          interaction={interaction}
          onPreview={(coordinate) => setPreview(object.id, { position: coordinate })}
          onCommit={(coordinate) => done([scene.updateComponentField(object.id, name, 'position', coordinate)])}
        />
      </SceneFrame>
    );
  }
  return null;
}

const HANDLED = [...SIZED, 'PlaneWaveSource', 'GaussianBeamSource', 'PlaneMonitor'];

export function registerMaxwellVisuals(host: FrontendHost): void {
  const scene = host.services.get('scene');

  for (const visual of VISUALS) {
    function MaxwellVisual({ object, selected, stage }: ViewportObjectProps) {
      const domain = useDomain(scene);
      const preview = usePreview(object.id);
      const raw = findComponent(object, visual.component);
      if (!raw || object.visible === false) return null;
      const component = withPreview(raw, preview);
      const offset = offsetOf(preview);
      const origin = offset ? add(positionOf(object), offset) : positionOf(object);
      const ctx: Ctx = { scene, object, component, domain, selected, stage, palette: paletteOf(stage), origin };
      return (
        <>
          {visual.local && <SceneFrame anchor="object" offset={offset}>{visual.local(ctx)}</SceneFrame>}
          {visual.scene && <SceneFrame anchor="scene">{visual.scene(ctx)}</SceneFrame>}
        </>
      );
    }
    host.registerVisualizer({
      id: `witwin.maxwell.${visual.component}`,
      priority: 80,
      skipStandardGeometry: true,
      match: (object) => !!findComponent(object, visual.component),
      component: MaxwellVisual,
    });
  }

  // Gizmos, not visualizers: wt_volume's Field visualizer still draws the
  // solver's domain box and field, and a MaterialRegion keeps its mesh.
  function MaxwellSolverGizmo({ object, selected, stage }: ViewportObjectProps) {
    const domain = useDomain(scene);
    const solver = findComponent(object, 'MaxwellSolver');
    if (!solver || object.visible === false || !domain.real) return null;
    return <SolverAnnotations solver={solver} domain={domain} selected={selected} stage={stage} palette={paletteOf(stage)} />;
  }
  host.registerGizmo({
    id: 'witwin.maxwell.pml',
    priority: 80,
    match: (object) => !!findComponent(object, 'MaxwellSolver'),
    component: MaxwellSolverGizmo,
  });

  function MaterialRegionGizmo({ object, selected, stage }: ViewportObjectProps) {
    const component = findComponent(object, 'MaterialRegion');
    if (!component || object.visible === false) return null;
    return <MaterialRegion component={component} selected={selected} palette={paletteOf(stage)} />;
  }
  host.registerGizmo({
    id: 'witwin.maxwell.region',
    priority: 80,
    match: (object) => !!findComponent(object, 'MaterialRegion'),
    component: MaterialRegionGizmo,
  });

  function MaxwellHandlesGizmo({ object, selected, stage, tool }: ViewportObjectProps & { tool?: TransformToolName }) {
    const domain = useDomain(scene);
    // A host older than the Bounds tool passes no tool; then handles show whenever the object is selected.
    if (!selected || object.visible === false || (tool !== undefined && tool !== 'bounds')) return null;
    const name = HANDLED.find((n) => findComponent(object, n));
    if (!name) return null;
    return <MaxwellHandles host={host} scene={scene} object={object} name={name} domain={domain} palette={paletteOf(stage)} />;
  }
  host.registerGizmo({
    id: 'witwin.maxwell.handles',
    priority: 90,
    match: (object) => HANDLED.some((n) => !!findComponent(object, n)),
    component: MaxwellHandlesGizmo,
  });
}
