import { Html, Line, React, THREE, useMemo } from './runtime';
import { formatLength, normalAxis, rectCorners, type Vec3 } from './emStyle';

/** A solid arrow: shaft line plus a cone head, `length` metres from `origin` along `direction`. */
export function Arrow({ origin, direction, length, color }: { origin: Vec3; direction: Vec3; length: number; color: string }) {
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
      <Line points={[origin, tip]} color={color} lineWidth={2} />
      <mesh position={headCenter} quaternion={quaternion}>
        <coneGeometry args={[head.radius, head.height, 18]} />
        <meshBasicMaterial color={color} toneMapped={false} />
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
}: {
  center: Vec3;
  size: Vec3;
  color: string;
  dashed?: boolean;
  /** Dash length, metres. */
  dash?: number;
  fillOpacity?: number;
}) {
  const corners = rectCorners(center, size);
  const fill = useMemo(() => {
    if (fillOpacity <= 0) return null;
    const g = new THREE.BufferGeometry().setFromPoints(
      [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]].map((c) => new THREE.Vector3(...c)),
    );
    return g;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(corners), fillOpacity > 0]);
  React.useEffect(() => () => fill?.dispose(), [fill]);
  return (
    <group>
      <Line
        points={[...corners, corners[0]]}
        color={color}
        lineWidth={1.5}
        dashed={dashed}
        dashSize={dash}
        gapSize={dash ? dash * 0.6 : undefined}
      />
      {fill && (
        <mesh geometry={fill} renderOrder={1}>
          <meshBasicMaterial color={color} transparent opacity={fillOpacity} side={THREE.DoubleSide} depthWrite={false} toneMapped={false} />
        </mesh>
      )}
    </group>
  );
}

/** Small fixed-size label in the 3D scene, styled like the app's tooltips. */
export function Label({ position, children }: { position: Vec3; children: React.ReactNode }) {
  return (
    <Html position={position} center zIndexRange={[20, 0]} style={{ pointerEvents: 'none' }}>
      <div
        style={{
          padding: '1px 5px',
          borderRadius: 3,
          background: 'var(--bg-tooltip, var(--gray-5))',
          color: 'var(--text-primary)',
          font: '11px var(--font-family)',
          whiteSpace: 'nowrap',
        }}
      >
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
  const offset = Math.max(size[ua], size[va]) * 0.08;
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
          <Line points={d.segments} segments color={color} lineWidth={1} />
          <Label position={d.mid}>{d.text}</Label>
        </group>
      ))}
    </group>
  );
}
