import type * as ThreeTypes from 'three';
import type { ViewportInteractionApi } from '@witwin/host';
import { React, THREE, useFrame, useRef, useState, type ThreeEvent } from './runtime';
import type { Vec3 } from './emStyle';

/*
 * Resize handles for Maxwell boxes and planes, shown under the Bounds tool
 * (T) like the Field box: one dot in the accent colour on the centre of
 * each face that can move. Dragging moves that face along its axis; Alt
 * moves the opposite face too (resize about the centre); Ctrl snaps the
 * change to whole grid cells.
 *
 * Positions are in the frame of the handles' parent group (a SceneFrame),
 * so the drag works the same on the Bench, whose scene carries a display
 * scale, and in World.
 */

/** Handle radius as a share of the view height: about 5 px in a 900 px viewport. */
const SCREEN_RADIUS = 0.006;
const HOVER_SCALE = 1.35;

export interface DragModifiers {
  snap: boolean;
  symmetric: boolean;
}

/** Parameter along the axis line (point `p`, unit axis `u`) of the point closest to `ray`. */
function axisParameter(ray: ThreeTypes.Ray, p: ThreeTypes.Vector3, u: ThreeTypes.Vector3): number | null {
  const w0 = p.clone().sub(ray.origin);
  const b = u.dot(ray.direction);
  const c = ray.direction.dot(ray.direction);
  const d = u.dot(w0);
  const e = ray.direction.dot(w0);
  const denom = u.dot(u) * c - b * b;
  // The ray runs along the axis: no usable drag.
  if (Math.abs(denom) < 1e-12 * c) return null;
  return (b * e - c * d) / denom;
}

function AxisHandle({
  position,
  axis,
  color,
  interaction,
  onMove,
  onEnd,
}: {
  position: Vec3;
  axis: number;
  color: string;
  interaction: ViewportInteractionApi;
  /** Called on every move with the offset along the axis since the press, in the parent frame. */
  onMove: (delta: number, mods: DragModifiers) => void;
  onEnd: () => void;
}) {
  const mesh = useRef<ThreeTypes.Mesh>(null);
  const drag = useRef<{ start: number } | null>(null);
  const [hovered, setHovered] = useState(false);

  // A constant size on screen whatever the zoom, the scene's display scale or the object's scale.
  useFrame(({ camera }) => {
    const m = mesh.current;
    if (!m?.parent) return;
    const world = m.getWorldPosition(new THREE.Vector3());
    const parentScale = m.parent.getWorldScale(new THREE.Vector3()).x || 1;
    const ortho = (camera as ThreeTypes.OrthographicCamera).isOrthographicCamera;
    const viewHeight = ortho
      ? ((camera as ThreeTypes.OrthographicCamera).top - (camera as ThreeTypes.OrthographicCamera).bottom) / (camera as ThreeTypes.OrthographicCamera).zoom
      : 2 * world.distanceTo(camera.position) * Math.tan(THREE.MathUtils.degToRad((camera as ThreeTypes.PerspectiveCamera).fov / 2));
    m.scale.setScalar(((viewHeight * SCREEN_RADIUS) / parentScale) * (hovered || drag.current ? HOVER_SCALE : 1));
  });

  const localRay = (e: ThreeEvent<PointerEvent>): ThreeTypes.Ray | null => {
    const parent = mesh.current?.parent;
    if (!parent) return null;
    return e.ray.clone().applyMatrix4(parent.matrixWorld.clone().invert());
  };
  const parameter = (e: ThreeEvent<PointerEvent>): number | null => {
    const ray = localRay(e);
    return ray ? axisParameter(ray, new THREE.Vector3(...position), new THREE.Vector3().setComponent(axis, 1)) : null;
  };

  const onPointerDown = (e: ThreeEvent<PointerEvent>) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const t = parameter(e);
    if (t === null) return;
    (e.target as Element | null)?.setPointerCapture?.(e.pointerId);
    drag.current = { start: t };
    interaction.setGizmoDragging(true);
  };
  const onPointerMove = (e: ThreeEvent<PointerEvent>) => {
    if (!drag.current) return;
    e.stopPropagation();
    const t = parameter(e);
    if (t === null) return;
    onMove(t - drag.current.start, { snap: e.ctrlKey || e.metaKey, symmetric: e.altKey });
  };
  const finish = (e: ThreeEvent<PointerEvent>) => {
    if (!drag.current) return;
    e.stopPropagation();
    (e.target as Element | null)?.releasePointerCapture?.(e.pointerId);
    drag.current = null;
    interaction.setGizmoDragging(false);
    onEnd();
  };

  return (
    <mesh
      ref={mesh}
      position={position}
      renderOrder={20}
      userData={{ isGizmo: true }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={finish}
      onPointerOver={(e) => {
        e.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      <sphereGeometry args={[1, 16, 12]} />
      <meshBasicMaterial color={color} depthTest={false} depthWrite={false} transparent toneMapped={false} />
    </mesh>
  );
}

export interface Box {
  min: Vec3;
  max: Vec3;
}

/** The box after moving face `axis`/`side` by `delta` from `start`. */
export function dragBox(start: Box, axis: number, side: -1 | 1, delta: number, mods: DragModifiers, cell: number, minSize: number): Box {
  const d = mods.snap && cell > 0 ? Math.round(delta / cell) * cell : delta;
  const min: Vec3 = [...start.min];
  const max: Vec3 = [...start.max];
  if (side > 0) {
    max[axis] = start.max[axis] + d;
    if (mods.symmetric) min[axis] = start.min[axis] - d;
  } else {
    min[axis] = start.min[axis] + d;
    if (mods.symmetric) max[axis] = start.max[axis] - d;
  }
  if (max[axis] - min[axis] < minSize) {
    const centre = mods.symmetric ? (start.min[axis] + start.max[axis]) / 2 : side > 0 ? min[axis] + minSize / 2 : max[axis] - minSize / 2;
    min[axis] = centre - minSize / 2;
    max[axis] = centre + minSize / 2;
  }
  return { min, max };
}

/**
 * Face handles of an axis-aligned box. `axes` lists the axes whose two
 * faces get a handle (a plane passes its two in-plane axes). `onPreview`
 * runs on every move, `onCommit` once on release with the final box.
 */
export function BoxHandles({
  box,
  axes,
  color,
  cell,
  minSize,
  interaction,
  onPreview,
  onCommit,
}: {
  box: Box;
  axes: number[];
  color: string;
  /** Grid cell, metres, for Ctrl snapping; 0 disables it. */
  cell: number;
  minSize: number;
  interaction: ViewportInteractionApi;
  onPreview: (box: Box) => void;
  onCommit: (box: Box) => void;
}) {
  const start = useRef<Box | null>(null);
  const latest = useRef<Box | null>(null);
  const centre = [0, 1, 2].map((a) => (box.min[a] + box.max[a]) / 2) as Vec3;
  const handles = axes.flatMap((axis) =>
    ([-1, 1] as const).map((side) => {
      const p: Vec3 = [...centre];
      p[axis] = side < 0 ? box.min[axis] : box.max[axis];
      return { axis, side, position: p };
    }),
  );
  return (
    <group userData={{ isGizmo: true }}>
      {handles.map(({ axis, side, position }) => (
        <AxisHandle
          key={`${axis}${side}`}
          position={position}
          axis={axis}
          color={color}
          interaction={interaction}
          onMove={(delta, mods) => {
            if (!start.current) start.current = box;
            latest.current = dragBox(start.current, axis, side, delta, mods, cell, minSize);
            onPreview(latest.current);
          }}
          onEnd={() => {
            const next = latest.current;
            start.current = null;
            latest.current = null;
            if (next) onCommit(next);
          }}
        />
      ))}
    </group>
  );
}

/** One handle that moves a plane along its normal (an infinite plane monitor's `position`). */
export function PositionHandle({
  position,
  axis,
  color,
  cell,
  interaction,
  onPreview,
  onCommit,
}: {
  position: Vec3;
  axis: number;
  color: string;
  cell: number;
  interaction: ViewportInteractionApi;
  onPreview: (coordinate: number) => void;
  onCommit: (coordinate: number) => void;
}) {
  const start = useRef<number | null>(null);
  const latest = useRef<number | null>(null);
  return (
    <group userData={{ isGizmo: true }}>
      <AxisHandle
        position={position}
        axis={axis}
        color={color}
        interaction={interaction}
        onMove={(delta, mods) => {
          if (start.current === null) start.current = position[axis];
          const d = mods.snap && cell > 0 ? Math.round(delta / cell) * cell : delta;
          latest.current = start.current + d;
          onPreview(latest.current);
        }}
        onEnd={() => {
          const next = latest.current;
          start.current = null;
          latest.current = null;
          if (next !== null) onCommit(next);
        }}
      />
    </group>
  );
}
