import type * as ThreeTypes from 'three';
import { Html, Line, React, THREE, useFrame, useMemo, useRef } from './runtime';
import { formatLength, normalAxis, rectCorners, type Vec3 } from './emStyle';

/** Annotation fills and outlines never take a click; HitSphere / HitPlane / HitBox do. */
export const noRaycast = () => undefined;

/*
 * A mesh whose material is fully transparent is a soft click target in
 * Studio (viewportSelection.ts): it selects the object only when nothing
 * solid is under the pointer, so a thin marker gets a usable hit area
 * without blocking the parts behind or inside it.
 */
function useHitMaterial() {
  const material = useMemo(
    () => new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false, side: THREE.DoubleSide }),
    [],
  );
  React.useEffect(() => () => material.dispose(), [material]);
  return material;
}

export function HitSphere({ position = [0, 0, 0], radius }: { position?: Vec3; radius: number }) {
  const material = useHitMaterial();
  return (
    <mesh position={position} material={material}>
      <sphereGeometry args={[radius, 12, 8]} />
    </mesh>
  );
}

export function HitPlane({ center, size }: { center: Vec3; size: Vec3 }) {
  const material = useHitMaterial();
  const geometry = useMemo(() => {
    const corners = rectCorners(center, size).map((c) => new THREE.Vector3(...c));
    return new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...center, ...size]);
  React.useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} material={material} />;
}

export function HitBox({ min, max }: { min: Vec3; max: Vec3 }) {
  const material = useHitMaterial();
  const size = [0, 1, 2].map((a) => Math.max(max[a] - min[a], 1e-12)) as Vec3;
  const center = [0, 1, 2].map((a) => (min[a] + max[a]) / 2) as Vec3;
  return (
    <mesh position={center} material={material}>
      <boxGeometry args={size} />
    </mesh>
  );
}

function sceneContainer(node: ThreeTypes.Object3D): ThreeTypes.Object3D | null {
  // Studio tags every scene-object group with userData.sceneObjectId; the
  // first ancestor without it holds the scene in scene coordinates (on the
  // Bench it carries the display scale).
  let current: ThreeTypes.Object3D | null = node;
  while (current && typeof current.userData?.sceneObjectId === 'string') current = current.parent;
  return current;
}

const scratch = { container: new THREE.Matrix4(), parent: new THREE.Matrix4(), position: new THREE.Vector3() };

/**
 * Draw children in scene coordinates instead of the object's frame.
 *
 * `anchor = 'scene'`: children are in scene coordinates (domain bounds, an
 * infinite plane's position, a TFSF box). `anchor = 'object'`: children are
 * axis-aligned around the object's scene position, the way the solve reads
 * a monitor or source: it uses the position only, never rotation or scale.
 * `offset` shifts the anchor, for a handle drag preview.
 */
export function SceneFrame({ anchor, offset, children }: { anchor: 'scene' | 'object'; offset?: Vec3; children: React.ReactNode }) {
  const ref = useRef<ThreeTypes.Group>(null);
  const update = () => {
    const group = ref.current;
    const parent = group?.parent;
    if (!group || !parent) return;
    parent.updateWorldMatrix(true, false);
    const container = sceneContainer(parent);
    scratch.container.copy(container ? container.matrixWorld : new THREE.Matrix4());
    // parent frame <- world <- scene: inverse(parentWorld) * containerWorld.
    const m = scratch.parent.copy(parent.matrixWorld).invert().multiply(scratch.container);
    if (anchor === 'object') {
      // Object origin in scene coordinates: inverse(containerWorld) * parentWorld * 0.
      const p = scratch.position.setFromMatrixPosition(parent.matrixWorld).applyMatrix4(scratch.container.clone().invert());
      if (offset) p.add(new THREE.Vector3(...offset));
      m.multiply(new THREE.Matrix4().makeTranslation(p.x, p.y, p.z));
    } else if (offset) {
      m.multiply(new THREE.Matrix4().makeTranslation(...offset));
    }
    if (!group.matrix.equals(m)) {
      group.matrix.copy(m);
      group.matrixWorldNeedsUpdate = true;
    }
  };
  useFrame(update);
  React.useLayoutEffect(update);
  return (
    <group ref={ref} matrixAutoUpdate={false}>
      {children}
    </group>
  );
}

/** A solid arrow: shaft line plus a cone head, `length` metres from `origin` along `direction`. */
export function Arrow({
  origin,
  direction,
  length,
  color,
  lineWidth = 2,
  opacity = 1,
}: {
  origin: Vec3;
  direction: Vec3;
  length: number;
  color: string;
  lineWidth?: number;
  opacity?: number;
}) {
  const { tip, headCenter, quaternion, head } = useMemo(() => {
    const dir = new THREE.Vector3(...direction);
    if (dir.lengthSq() < 1e-20) dir.set(0, 0, 1);
    dir.normalize();
    const start = new THREE.Vector3(...origin);
    const headLength = length * 0.28;
    const shaftEnd = start.clone().addScaledVector(dir, length - headLength);
    return {
      tip: shaftEnd.toArray() as Vec3,
      headCenter: start.clone().addScaledVector(dir, length - headLength / 2).toArray() as Vec3,
      // ConeGeometry points along +y.
      quaternion: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir),
      head: { radius: headLength * 0.38, height: headLength },
    };
  }, [origin[0], origin[1], origin[2], direction[0], direction[1], direction[2], length]);
  return (
    <group>
      <Line points={[origin, tip]} color={color} lineWidth={lineWidth} transparent={opacity < 1} opacity={opacity} raycast={noRaycast} />
      <mesh position={headCenter} quaternion={quaternion} raycast={noRaycast}>
        <coneGeometry args={[head.radius, head.height, 18]} />
        <meshBasicMaterial color={color} toneMapped={false} transparent={opacity < 1} opacity={opacity} />
      </mesh>
    </group>
  );
}

/** Outline of an axis-aligned rectangle (one zero side), solid or dashed, with an optional translucent fill. */
export function PlaneRect({
  center,
  size,
  color,
  dashed = false,
  dash,
  fillOpacity = 0,
  lineWidth = 1.5,
}: {
  center: Vec3;
  size: Vec3;
  color: string;
  dashed?: boolean;
  /** Dash length, metres. */
  dash?: number;
  fillOpacity?: number;
  lineWidth?: number;
}) {
  const corners = rectCorners(center, size);
  const fill = useMemo(() => {
    if (fillOpacity <= 0) return null;
    return new THREE.BufferGeometry().setFromPoints(
      [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]].map((c) => new THREE.Vector3(...c)),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(corners), fillOpacity > 0]);
  React.useEffect(() => () => fill?.dispose(), [fill]);
  return (
    <group>
      <Line
        points={[...corners, corners[0]]}
        color={color}
        lineWidth={lineWidth}
        dashed={dashed}
        dashSize={dash}
        gapSize={dash ? dash * 0.6 : undefined}
        raycast={noRaycast}
      />
      {fill && (
        <mesh geometry={fill} renderOrder={1} raycast={noRaycast}>
          <meshBasicMaterial color={color} transparent opacity={fillOpacity} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Translucent faces of an axis-aligned box, drawn after opaque parts and never picked. */
export function BoxFill({ min, max, color, opacity }: { min: Vec3; max: Vec3; color: string; opacity: number }) {
  const size = [0, 1, 2].map((a) => Math.max(max[a] - min[a], 1e-12)) as Vec3;
  const center = [0, 1, 2].map((a) => (min[a] + max[a]) / 2) as Vec3;
  return (
    <mesh position={center} renderOrder={1} raycast={noRaycast}>
      <boxGeometry args={size} />
      <meshBasicMaterial color={color} transparent opacity={opacity} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

/** Circle of `radius` around `center`, in the plane normal to `normal`. */
export function Ring({ center, normal, radius, color, dashed = false, dash }: { center: Vec3; normal: Vec3; radius: number; color: string; dashed?: boolean; dash?: number }) {
  const points = useMemo(() => {
    const n = new THREE.Vector3(...normal).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), n);
    const c = new THREE.Vector3(...center);
    return Array.from({ length: 65 }, (_, i) => {
      const t = (i / 64) * Math.PI * 2;
      return new THREE.Vector3(Math.cos(t) * radius, Math.sin(t) * radius, 0).applyQuaternion(q).add(c).toArray() as Vec3;
    });
  }, [...center, ...normal, radius]);
  return <Line points={points} color={color} lineWidth={1.5} dashed={dashed} dashSize={dash} gapSize={dash ? dash * 0.6 : undefined} raycast={noRaycast} />;
}

/**
 * Small fixed-size label in the 3D scene, styled like the app's tooltips,
 * with a dot in the annotation's role colour so a label reads as belonging
 * to its marker.
 */
/**
 * A tag that floats just above its anchor point on screen, so it never
 * covers the object it names. `row` stacks tags that share an anchor:
 * row 0 is nearest the point, each next row one tag height higher.
 * `centered` puts the tag on the point instead (a dimension's length sits
 * on its line).
 */
export function Label({ position, color, row = 0, centered = false, children }: { position: Vec3; color?: string; row?: number; centered?: boolean; children: React.ReactNode }) {
  return (
    <Html position={position} zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
      <div
        style={{
          transform: centered ? 'translate(-50%, -50%)' : `translate(-50%, calc(-100% - ${8 + row * 22}px))`,
          display: 'flex',
          alignItems: 'center',
          gap: 5,
          padding: '1px 6px',
          borderRadius: 3,
          background: 'var(--tooltip-bg, var(--gray-5))',
          color: 'var(--tooltip-text, var(--text-primary))',
          font: '11px var(--font-family)',
          whiteSpace: 'nowrap',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {color && <span style={{ width: 6, height: 6, borderRadius: 3, background: color, flex: 'none' }} />}
        {children}
      </div>
    </Html>
  );
}

/**
 * Width and height of a plane, drawn like a mechanical drawing: a line
 * parallel to each edge, offset outward, with end ticks and the length at
 * its middle.
 */
export function PlaneDimensions({ center, size, color }: { center: Vec3; size: Vec3; color: string }) {
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  // Far enough out that the length tag clears the edge handles at the edge midpoints.
  const offset = Math.max(size[ua], size[va]) * 0.2;
  const tick = offset * 0.35;
  const dims = [
    [ua, va],
    [va, ua],
  ].map(([along, across]) => {
    const lo: Vec3 = [...center];
    lo[along] = center[along] - size[along] / 2;
    lo[across] = center[across] - size[across] / 2 - offset;
    const hi: Vec3 = [...lo];
    hi[along] = center[along] + size[along] / 2;
    const segments: Vec3[] = [lo, hi];
    for (const p of [lo, hi]) {
      const a: Vec3 = [...p];
      const b: Vec3 = [...p];
      a[across] -= tick;
      b[across] += offset;
      segments.push(a, b);
    }
    const mid: Vec3 = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    mid[across] -= tick * 2.2;
    return { segments, mid, text: formatLength(size[along]) };
  });
  return (
    <group>
      {dims.map((d, i) => (
        <group key={i}>
          <Line points={d.segments} segments color={color} lineWidth={1} raycast={noRaycast} />
          <Label position={d.mid} centered>{d.text}</Label>
        </group>
      ))}
    </group>
  );
}
