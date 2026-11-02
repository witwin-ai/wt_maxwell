import { Html, React, THREE, useEffect, useMemo, useRef } from './runtime';
import type { HostSceneObject, ViewportHost } from './sdk/types';
import { Arrow, PlaneDimensions, PlaneRect } from './primitives';
import { normalAxis, value, vec3, type Domain, type Vec3 } from './emStyle';
import { modeLabel, paintModeProfile, readModeProfiles, type ModeProfile } from './modeProfile';

/*
 * A mode plane (ModeSource or ModeMonitor) in its object's local frame:
 * outline, propagation arrow, the profile of the selected mode painted on
 * the plane, and, while selected, dimension lines and the mode list.
 *
 * Without published mode_profiles the plane shows its outline and a light
 * fill only; nothing is invented.
 */

const TEXTURE_WIDTH = 192;
const THUMB_WIDTH = 56;

function ProfileSurface({ size, profile, opacity }: { size: Vec3; profile: ModeProfile; opacity: number }) {
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const canvas = useMemo(() => document.createElement('canvas'), []);
  const texture = useMemo(() => {
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [canvas]);
  const height = Math.max(8, Math.round((TEXTURE_WIDTH * size[va]) / Math.max(size[ua], 1e-12)));

  useEffect(() => {
    const [w0, h0] = [canvas.width, canvas.height];
    paintModeProfile(canvas, profile, TEXTURE_WIDTH, Math.min(height, 1024));
    // WebGL2 textures have immutable storage; a new size needs a fresh upload.
    if (w0 !== canvas.width || h0 !== canvas.height) texture.dispose();
    texture.needsUpdate = true;
  }, [canvas, texture, profile, height]);
  useEffect(() => () => texture.dispose(), [texture]);

  // Quad over the plane rectangle; UV (0, 0) at (u min, v min).
  const geometry = useMemo(() => {
    const corner = (su: number, sv: number) => {
      const p = new THREE.Vector3();
      p.setComponent(ua, (su * size[ua]) / 2);
      p.setComponent(va, (sv * size[va]) / 2);
      return p;
    };
    const g = new THREE.BufferGeometry().setFromPoints([corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, -1), corner(1, 1), corner(-1, 1)]);
    g.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1], 2));
    return g;
  }, [ua, va, size[ua], size[va]]);
  useEffect(() => () => geometry.dispose(), [geometry]);

  return (
    <mesh geometry={geometry} renderOrder={2}>
      <meshBasicMaterial map={texture} side={THREE.DoubleSide} transparent opacity={opacity} depthWrite={false} toneMapped={false} />
    </mesh>
  );
}

function Thumbnail({ profile, aspect }: { profile: ModeProfile; aspect: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const height = Math.max(8, Math.min(64, Math.round(THUMB_WIDTH * aspect)));
  useEffect(() => {
    if (ref.current) paintModeProfile(ref.current, profile, THUMB_WIDTH, height);
  }, [profile, height]);
  return <canvas ref={ref} style={{ width: THUMB_WIDTH, height, borderRadius: 2, flex: 'none' }} />;
}

function ModeList({
  profiles,
  selected,
  aspect,
  onSelect,
}: {
  profiles: ModeProfile[];
  selected: number;
  aspect: number;
  onSelect: (index: number) => void;
}) {
  return (
    <div
      style={{
        minWidth: 220,
        background: 'var(--gray-3)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 6,
        padding: 4,
        font: '11px var(--font-family)',
        color: 'var(--text-primary)',
        boxShadow: 'var(--shadow-md)',
      }}
      // Clicks here must not reach the viewport's selection handler.
      onPointerDown={(e) => e.stopPropagation()}
    >
      {profiles.map((p) => {
        const active = p.index === selected;
        return (
          <div
            key={p.index}
            role="button"
            tabIndex={0}
            aria-pressed={active}
            onClick={() => onSelect(p.index)}
            onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && onSelect(p.index)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              padding: '3px 6px',
              borderRadius: 4,
              cursor: 'pointer',
              background: active ? 'var(--selected-bg)' : 'transparent',
              color: active ? 'var(--selected-text)' : undefined,
            }}
          >
            <Thumbnail profile={p} aspect={aspect} />
            <div style={{ display: 'grid', gap: 1, fontVariantNumeric: 'tabular-nums' }}>
              <span style={{ fontWeight: 500 }}>
                {modeLabel(p)}
                {p.component ? ` · ${p.component}` : ''}
              </span>
              <span>n_eff {p.n_eff.toFixed(4)}</span>
              <span>TE {(p.te_fraction * 100).toFixed(0)}%</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ModePlane({
  host,
  object,
  component,
  selected,
  domain,
  color,
  dashed,
}: {
  host: ViewportHost;
  object: HostSceneObject;
  component: any;
  selected: boolean;
  domain: Domain;
  color: string;
  dashed: boolean;
}) {
  const size = vec3(component, 'size', [1, 1, 0]);
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const sign = value<string>(component, 'direction', '+') === '-' ? -1 : 1;
  const modeIndex = Number(value(component, 'mode_index', 0));
  const profiles = readModeProfiles(component);
  const profile = profiles.find((p) => p.index === modeIndex) ?? null;
  const direction: Vec3 = [0, 0, 0];
  direction[normal] = sign;
  const origin: Vec3 = [0, 0, 0];
  const planeSide = Math.max(size[ua], size[va]);

  const selectMode = (index: number) => {
    void host.sceneWrites.updateComponentField(object.id, component.name, 'mode_index', index);
  };

  // The list sits beside the plane's +u edge, at mid height.
  const listAnchor: Vec3 = [0, 0, 0];
  listAnchor[ua] = size[ua] / 2 + planeSide * 0.12;

  return (
    <group>
      {profile && <ProfileSurface size={size} profile={profile} opacity={0.92} />}
      <PlaneRect center={origin} size={size} color={color} dashed={dashed} dash={domain.extent * 0.012} fillOpacity={profile ? 0 : 0.14} />
      <Arrow origin={origin} direction={direction} length={Math.max(planeSide * 0.6, domain.extent * 0.06)} color={color} />
      {selected && <PlaneDimensions center={origin} size={size} color={color} />}
      {selected && profiles.length > 0 && (
        <Html position={listAnchor} zIndexRange={[30, 0]} style={{ transform: 'translate(8px, -50%)' }}>
          <ModeList profiles={profiles} selected={modeIndex} aspect={size[va] / Math.max(size[ua], 1e-12)} onSelect={selectMode} />
        </Html>
      )}
    </group>
  );
}
