// src/runtime.ts
function shared() {
  const globals = globalThis.__witwin;
  if (!globals?.react || !globals.three || !globals.fiber) {
    throw new Error("[wt_maxwell] viewport host singletons are unavailable");
  }
  return globals;
}
var React = shared().react;
var THREE = shared().three;
var useCallback = React.useCallback;
var useEffect = React.useEffect;
var useMemo = React.useMemo;
var useRef = React.useRef;
var useState = React.useState;
var fiber = shared().fiber;
var drei = shared().drei;
if (!drei?.Html || !drei.Line || !drei.Text) {
  throw new Error("[wt_maxwell] @react-three/drei host singleton is incomplete");
}
var useFrame = fiber.useFrame;
var useThree = fiber.useThree;
var Html = drei.Html;
var Line = drei.Line;
var Text = drei.Text;

// src/emStyle.ts
var FALLBACK_PALETTE = {
  background: "#434345",
  /* allow-color: 3D fallback for hosts without the stage palette */
  edge: "#d4d4d8",
  /* allow-color: 3D fallback */
  text: "#f4f4f5",
  /* allow-color: 3D fallback */
  accent: "#0066cc",
  /* allow-color: 3D fallback */
  emitter: "#fb923c",
  /* allow-color: 3D fallback */
  sensor: "#4ade80",
  /* allow-color: 3D fallback */
  boundary: "#a1a1aa",
  /* allow-color: 3D fallback */
  region: "#a78bfa",
  /* allow-color: 3D fallback */
  warning: "#f87171"
  /* allow-color: 3D fallback */
};
function paletteOf(stage) {
  return stage?.palette ?? FALLBACK_PALETTE;
}
function findComponent(object, name) {
  const components = Array.isArray(object?.components) ? object.components : [];
  return components.find((c) => c?.name === name || c?.base_classes?.includes?.(name)) ?? null;
}
function value(component, name, fallback) {
  const v = component?.values?.[name];
  return v === void 0 || v === null ? fallback : v;
}
function vec3(component, name, fallback) {
  const v = value(component, name, fallback);
  return Array.isArray(v) && v.length >= 3 ? [Number(v[0]), Number(v[1]), Number(v[2])] : fallback;
}
function positionOf(object) {
  const p = object?.transform?.position;
  if (Array.isArray(p)) return [Number(p[0]) || 0, Number(p[1]) || 0, Number(p[2]) || 0];
  if (p && typeof p === "object") return [Number(p.x) || 0, Number(p.y) || 0, Number(p.z) || 0];
  return [0, 0, 0];
}
var DEFAULT_DOMAIN = { min: [-1, -1, -1], max: [1, 1, 1], extent: 2, real: false };
function domainKey(scene) {
  for (const object of Object.values(scene.getObjects())) {
    const solver = findComponent(object, "MaxwellSolver");
    if (!solver) continue;
    const offset = positionOf(object);
    const lo = vec3(solver, "min_bound", [-1, -1, -1]).map((v, i) => v + offset[i]);
    const hi = vec3(solver, "max_bound", [1, 1, 1]).map((v, i) => v + offset[i]);
    return JSON.stringify([lo, hi]);
  }
  return "";
}
function useDomain(scene) {
  const subscribe2 = React.useCallback((onChange) => {
    const subscription = scene.subscribe(onChange);
    return () => subscription.dispose();
  }, [scene]);
  const key = React.useSyncExternalStore(subscribe2, () => domainKey(scene));
  return React.useMemo(() => {
    if (!key) return DEFAULT_DOMAIN;
    const [min, max] = JSON.parse(key);
    const extent = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2], 1e-12);
    return { min, max, extent, real: true };
  }, [key]);
}
function insideDomain(domain, p) {
  if (!domain.real) return true;
  const tol = domain.extent * 1e-6;
  return [0, 1, 2].every((a) => p[a] >= domain.min[a] - tol && p[a] <= domain.max[a] + tol);
}
var UNITS = [
  [1, "m"],
  [0.01, "cm"],
  [1e-3, "mm"],
  [1e-6, "\xB5m"],
  [1e-9, "nm"]
];
function formatLength(metres) {
  const a = Math.abs(metres);
  const [scale, name] = UNITS.find(([s]) => a >= s) ?? UNITS[UNITS.length - 1];
  return `${Number((metres / scale).toPrecision(3))} ${name}`;
}
var FREQUENCY_UNITS = [
  [1e12, "THz"],
  [1e9, "GHz"],
  [1e6, "MHz"],
  [1e3, "kHz"],
  [1, "Hz"]
];
function formatFrequency(hz) {
  const a = Math.abs(hz);
  const [scale, name] = FREQUENCY_UNITS.find(([s]) => a >= s) ?? FREQUENCY_UNITS[FREQUENCY_UNITS.length - 1];
  return `${Number((hz / scale).toPrecision(3))} ${name}`;
}
function rectCorners(center, size) {
  const normal = normalAxis(size);
  const [u, v] = [0, 1, 2].filter((d) => d !== normal);
  const corner = (su, sv) => {
    const p = [...center];
    p[u] = center[u] + su * size[u] / 2;
    p[v] = center[v] + sv * size[v] / 2;
    return p;
  };
  return [corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, 1)];
}
function normalAxis(size) {
  let n = 0;
  for (let a = 1; a < 3; a++) if (Math.abs(size[a]) < Math.abs(size[n])) n = a;
  return n;
}
function boxEdges(min, max) {
  const c = (i) => [i & 1 ? max[0] : min[0], i & 2 ? max[1] : min[1], i & 4 ? max[2] : min[2]];
  const out = [];
  for (let i = 0; i < 8; i++) {
    for (const bit of [1, 2, 4]) if (!(i & bit)) out.push(c(i), c(i | bit));
  }
  return out;
}
var AXIS_INDEX = { x: 0, y: 1, z: 2, Ex: 0, Ey: 1, Ez: 2 };
var AXIS_NAMES = ["x", "y", "z"];
function axisVector(axis, sign = 1) {
  const v = [0, 0, 0];
  v[axis] = sign;
  return v;
}
function add(a, b) {
  return [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
}

// src/primitives.tsx
var noRaycast = () => void 0;
function useHitMaterial() {
  const material = useMemo(
    () => new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false, colorWrite: false, side: THREE.DoubleSide }),
    []
  );
  React.useEffect(() => () => material.dispose(), [material]);
  return material;
}
function HitSphere({ position = [0, 0, 0], radius }) {
  const material = useHitMaterial();
  return /* @__PURE__ */ React.createElement("mesh", { position, material }, /* @__PURE__ */ React.createElement("sphereGeometry", { args: [radius, 12, 8] }));
}
function HitPlane({ center, size }) {
  const material = useHitMaterial();
  const geometry = useMemo(() => {
    const corners = rectCorners(center, size).map((c) => new THREE.Vector3(...c));
    return new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]);
  }, [...center, ...size]);
  React.useEffect(() => () => geometry.dispose(), [geometry]);
  return /* @__PURE__ */ React.createElement("mesh", { geometry, material });
}
function HitBox({ min, max }) {
  const material = useHitMaterial();
  const size = [0, 1, 2].map((a) => Math.max(max[a] - min[a], 1e-12));
  const center = [0, 1, 2].map((a) => (min[a] + max[a]) / 2);
  return /* @__PURE__ */ React.createElement("mesh", { position: center, material }, /* @__PURE__ */ React.createElement("boxGeometry", { args: size }));
}
function sceneContainer(node) {
  let current = node;
  while (current && typeof current.userData?.sceneObjectId === "string") current = current.parent;
  return current;
}
var scratch = { container: new THREE.Matrix4(), parent: new THREE.Matrix4(), position: new THREE.Vector3() };
function SceneFrame({ anchor, offset, children }) {
  const ref = useRef(null);
  const update = () => {
    const group = ref.current;
    const parent = group?.parent;
    if (!group || !parent) return;
    parent.updateWorldMatrix(true, false);
    const container = sceneContainer(parent);
    scratch.container.copy(container ? container.matrixWorld : new THREE.Matrix4());
    const m = scratch.parent.copy(parent.matrixWorld).invert().multiply(scratch.container);
    if (anchor === "object") {
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
  return /* @__PURE__ */ React.createElement("group", { ref, matrixAutoUpdate: false }, children);
}
function Arrow({
  origin,
  direction,
  length,
  color,
  lineWidth = 2,
  opacity = 1
}) {
  const { tip, headCenter, quaternion, head } = useMemo(() => {
    const dir = new THREE.Vector3(...direction);
    if (dir.lengthSq() < 1e-20) dir.set(0, 0, 1);
    dir.normalize();
    const start = new THREE.Vector3(...origin);
    const headLength = length * 0.28;
    const shaftEnd = start.clone().addScaledVector(dir, length - headLength);
    return {
      tip: shaftEnd.toArray(),
      headCenter: start.clone().addScaledVector(dir, length - headLength / 2).toArray(),
      // ConeGeometry points along +y.
      quaternion: new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir),
      head: { radius: headLength * 0.38, height: headLength }
    };
  }, [origin[0], origin[1], origin[2], direction[0], direction[1], direction[2], length]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: [origin, tip], color, lineWidth, transparent: opacity < 1, opacity, raycast: noRaycast }), /* @__PURE__ */ React.createElement("mesh", { position: headCenter, quaternion, raycast: noRaycast }, /* @__PURE__ */ React.createElement("coneGeometry", { args: [head.radius, head.height, 18] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, toneMapped: false, transparent: opacity < 1, opacity })));
}
function PlaneRect({
  center,
  size,
  color,
  dashed = false,
  dash,
  fillOpacity = 0,
  lineWidth = 1.5
}) {
  const corners = rectCorners(center, size);
  const fill = useMemo(() => {
    if (fillOpacity <= 0) return null;
    return new THREE.BufferGeometry().setFromPoints(
      [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]].map((c) => new THREE.Vector3(...c))
    );
  }, [JSON.stringify(corners), fillOpacity > 0]);
  React.useEffect(() => () => fill?.dispose(), [fill]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(
    Line,
    {
      points: [...corners, corners[0]],
      color,
      lineWidth,
      dashed,
      dashSize: dash,
      gapSize: dash ? dash * 0.6 : void 0,
      raycast: noRaycast
    }
  ), fill && /* @__PURE__ */ React.createElement("mesh", { geometry: fill, renderOrder: 1, raycast: noRaycast }, /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, transparent: true, opacity: fillOpacity, side: THREE.DoubleSide, depthWrite: false, toneMapped: false })));
}
function BoxFill({ min, max, color, opacity }) {
  const size = [0, 1, 2].map((a) => Math.max(max[a] - min[a], 1e-12));
  const center = [0, 1, 2].map((a) => (min[a] + max[a]) / 2);
  return /* @__PURE__ */ React.createElement("mesh", { position: center, renderOrder: 1, raycast: noRaycast }, /* @__PURE__ */ React.createElement("boxGeometry", { args: size }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, transparent: true, opacity, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }));
}
function Ring({ center, normal, radius, color, dashed = false, dash }) {
  const points = useMemo(() => {
    const n = new THREE.Vector3(...normal).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 0, 1), n);
    const c = new THREE.Vector3(...center);
    return Array.from({ length: 65 }, (_, i) => {
      const t = i / 64 * Math.PI * 2;
      return new THREE.Vector3(Math.cos(t) * radius, Math.sin(t) * radius, 0).applyQuaternion(q).add(c).toArray();
    });
  }, [...center, ...normal, radius]);
  return /* @__PURE__ */ React.createElement(Line, { points, color, lineWidth: 1.5, dashed, dashSize: dash, gapSize: dash ? dash * 0.6 : void 0, raycast: noRaycast });
}
function Label({ position, color, row = 0, centered = false, children }) {
  return /* @__PURE__ */ React.createElement(Html, { position, zIndexRange: [20, 0], style: { pointerEvents: "none" } }, /* @__PURE__ */ React.createElement(
    "div",
    {
      style: {
        transform: centered ? "translate(-50%, -50%)" : `translate(-50%, calc(-100% - ${8 + row * 22}px))`,
        display: "flex",
        alignItems: "center",
        gap: 5,
        padding: "1px 6px",
        borderRadius: 3,
        background: "var(--tooltip-bg, var(--gray-5))",
        color: "var(--tooltip-text, var(--text-primary))",
        font: "11px var(--font-family)",
        whiteSpace: "nowrap",
        fontVariantNumeric: "tabular-nums"
      }
    },
    color && /* @__PURE__ */ React.createElement("span", { style: { width: 6, height: 6, borderRadius: 3, background: color, flex: "none" } }),
    children
  ));
}
function PlaneDimensions({ center, size, color }) {
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const offset = Math.max(size[ua], size[va]) * 0.2;
  const tick = offset * 0.35;
  const dims = [
    [ua, va],
    [va, ua]
  ].map(([along, across]) => {
    const lo = [...center];
    lo[along] = center[along] - size[along] / 2;
    lo[across] = center[across] - size[across] / 2 - offset;
    const hi = [...lo];
    hi[along] = center[along] + size[along] / 2;
    const segments = [lo, hi];
    for (const p of [lo, hi]) {
      const a = [...p];
      const b = [...p];
      a[across] -= tick;
      b[across] += offset;
      segments.push(a, b);
    }
    const mid = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
    mid[across] -= tick * 2.2;
    return { segments, mid, text: formatLength(size[along]) };
  });
  return /* @__PURE__ */ React.createElement("group", null, dims.map((d, i) => /* @__PURE__ */ React.createElement("group", { key: i }, /* @__PURE__ */ React.createElement(Line, { points: d.segments, segments: true, color, lineWidth: 1, raycast: noRaycast }), /* @__PURE__ */ React.createElement(Label, { position: d.mid, centered: true }, d.text))));
}

// src/modeProfile.ts
function readModeProfiles(component) {
  const raw = component?.values?.mode_profiles;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (p) => p && Array.isArray(p.u) && Array.isArray(p.v) && Array.isArray(p.values) && p.values.length === p.u.length * p.v.length
  );
}
function modeLabel(p) {
  return p.label || `Mode ${p.index}`;
}
var RDBU = [
  "#053061",
  "#2166ac",
  "#4393c3",
  "#92c5de",
  "#d1e5f0",
  "#f7f7f7",
  "#fddbc7",
  "#f4a582",
  "#d6604d",
  "#b2182b",
  "#67001f"
].map((hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [n >> 16 & 255, n >> 8 & 255, n & 255];
});
function rdbu(t) {
  const x = Math.min(Math.max(t, 0), 1) * (RDBU.length - 1);
  const i = Math.min(Math.floor(x), RDBU.length - 2);
  const f = x - i;
  return RDBU[i].map((a, k) => a + (RDBU[i + 1][k] - a) * f);
}
function locate(axis, x) {
  const n = axis.length;
  if (x <= axis[0]) return [0, 0];
  if (x >= axis[n - 1]) return [n - 2, 1];
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = lo + hi >> 1;
    if (axis[mid] <= x) lo = mid;
    else hi = mid;
  }
  return [lo, (x - axis[lo]) / (axis[hi] - axis[lo])];
}
function paintModeProfile(canvas, p, width, height) {
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const img = ctx.createImageData(width, height);
  const nu = p.u.length;
  const [u0, u1] = [p.u[0], p.u[nu - 1]];
  const [v0, v1] = [p.v[0], p.v[p.v.length - 1]];
  const cols = Array.from({ length: width }, (_, x) => locate(p.u, u0 + (x + 0.5) / width * (u1 - u0)));
  for (let y = 0; y < height; y++) {
    const [j, tv] = locate(p.v, v1 - (y + 0.5) / height * (v1 - v0));
    for (let x = 0; x < width; x++) {
      const [i, tu] = cols[x];
      const a = i + nu * j;
      const b = a + nu;
      const val = (p.values[a] * (1 - tu) + p.values[a + 1] * tu) * (1 - tv) + (p.values[b] * (1 - tu) + p.values[b + 1] * tu) * tv;
      const [r, g, bl] = rdbu((val + 1) / 2);
      img.data.set([r, g, bl, 255], (x + width * y) * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
}

// src/ModePlane.tsx
var TEXTURE_WIDTH = 192;
var THUMB_WIDTH = 56;
function ProfileSurface({ size, profile, opacity }) {
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const canvas = useMemo(() => document.createElement("canvas"), []);
  const texture = useMemo(() => {
    const t = new THREE.CanvasTexture(canvas);
    t.colorSpace = THREE.SRGBColorSpace;
    return t;
  }, [canvas]);
  const height = Math.max(8, Math.round(TEXTURE_WIDTH * size[va] / Math.max(size[ua], 1e-12)));
  useEffect(() => {
    const [w0, h0] = [canvas.width, canvas.height];
    paintModeProfile(canvas, profile, TEXTURE_WIDTH, Math.min(height, 1024));
    if (w0 !== canvas.width || h0 !== canvas.height) texture.dispose();
    texture.needsUpdate = true;
  }, [canvas, texture, profile, height]);
  useEffect(() => () => texture.dispose(), [texture]);
  const geometry = useMemo(() => {
    const corner = (su, sv) => {
      const p = new THREE.Vector3();
      p.setComponent(ua, su * size[ua] / 2);
      p.setComponent(va, sv * size[va] / 2);
      return p;
    };
    const g = new THREE.BufferGeometry().setFromPoints([corner(-1, -1), corner(1, -1), corner(1, 1), corner(-1, -1), corner(1, 1), corner(-1, 1)]);
    g.setAttribute("uv", new THREE.Float32BufferAttribute([0, 0, 1, 0, 1, 1, 0, 0, 1, 1, 0, 1], 2));
    return g;
  }, [ua, va, size[ua], size[va]]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return /* @__PURE__ */ React.createElement("mesh", { geometry, renderOrder: 2 }, /* @__PURE__ */ React.createElement("meshBasicMaterial", { map: texture, side: THREE.DoubleSide, transparent: true, opacity, depthWrite: false, toneMapped: false }));
}
function Thumbnail({ profile, aspect }) {
  const ref = useRef(null);
  const height = Math.max(8, Math.min(64, Math.round(THUMB_WIDTH * aspect)));
  useEffect(() => {
    if (ref.current) paintModeProfile(ref.current, profile, THUMB_WIDTH, height);
  }, [profile, height]);
  return /* @__PURE__ */ React.createElement("canvas", { ref, style: { width: THUMB_WIDTH, height, borderRadius: 2, flex: "none" } });
}
function ModeList({
  profiles,
  selected,
  aspect,
  onSelect
}) {
  return /* @__PURE__ */ React.createElement(
    "div",
    {
      style: {
        minWidth: 220,
        background: "var(--gray-3)",
        border: "1px solid var(--border-subtle)",
        borderRadius: 6,
        padding: 4,
        font: "11px var(--font-family)",
        color: "var(--text-primary)",
        boxShadow: "var(--shadow-md)"
      },
      onPointerDown: (e) => e.stopPropagation()
    },
    profiles.map((p) => {
      const active = p.index === selected;
      return /* @__PURE__ */ React.createElement(
        "div",
        {
          key: p.index,
          role: "button",
          tabIndex: 0,
          "aria-pressed": active,
          onClick: () => onSelect(p.index),
          onKeyDown: (e) => (e.key === "Enter" || e.key === " ") && onSelect(p.index),
          style: {
            display: "flex",
            alignItems: "center",
            gap: 8,
            padding: "3px 6px",
            borderRadius: 4,
            cursor: "pointer",
            background: active ? "var(--selected-bg)" : "transparent",
            color: active ? "var(--selected-text)" : void 0
          }
        },
        /* @__PURE__ */ React.createElement(Thumbnail, { profile: p, aspect }),
        /* @__PURE__ */ React.createElement("div", { style: { display: "grid", gap: 1, fontVariantNumeric: "tabular-nums" } }, /* @__PURE__ */ React.createElement("span", { style: { fontWeight: 500 } }, modeLabel(p), p.component ? ` \xB7 ${p.component}` : ""), /* @__PURE__ */ React.createElement("span", null, "n_eff ", p.n_eff.toFixed(4)), /* @__PURE__ */ React.createElement("span", null, "TE ", (p.te_fraction * 100).toFixed(0), "%"))
      );
    })
  );
}
function ModePlane({
  scene,
  object,
  component,
  selected,
  domain,
  color,
  dashed
}) {
  const size = vec3(component, "size", [1, 1, 0]);
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const sign = value(component, "direction", "+") === "-" ? -1 : 1;
  const modeIndex = Number(value(component, "mode_index", 0));
  const profiles = readModeProfiles(component);
  const profile = profiles.find((p) => p.index === modeIndex) ?? null;
  const direction = [0, 0, 0];
  direction[normal] = sign;
  const origin = [0, 0, 0];
  const planeSide = Math.max(size[ua], size[va]);
  const selectMode = (index) => {
    void scene.updateComponentField(object.id, component.name, "mode_index", index);
  };
  const listAnchorRef = useRef(null);
  const edgeMidpoints = useMemo(
    () => [ua, va].flatMap(
      (axis) => [-1, 1].map((sign2) => {
        const p = new THREE.Vector3();
        p.setComponent(axis, sign2 * size[axis] / 2);
        return p;
      })
    ),
    [ua, va, size[ua], size[va]]
  );
  useFrame(({ camera }) => {
    const anchor = listAnchorRef.current;
    if (!anchor?.parent) return;
    const screen = new THREE.Vector3();
    let best = edgeMidpoints[0];
    let bestX = -Infinity;
    for (const p of edgeMidpoints) {
      screen.copy(p).applyMatrix4(anchor.parent.matrixWorld).project(camera);
      if (screen.x > bestX) {
        bestX = screen.x;
        best = p;
      }
    }
    if (!anchor.position.equals(best)) anchor.position.copy(best);
  });
  return /* @__PURE__ */ React.createElement("group", null, profile && /* @__PURE__ */ React.createElement(ProfileSurface, { size, profile, opacity: 0.92 }), /* @__PURE__ */ React.createElement(PlaneRect, { center: origin, size, color, dashed, dash: domain.extent * 0.012, fillOpacity: profile ? 0 : 0.14 }), /* @__PURE__ */ React.createElement(Arrow, { origin, direction, length: Math.max(planeSide * 0.6, domain.extent * 0.06), color }), selected && /* @__PURE__ */ React.createElement(PlaneDimensions, { center: origin, size, color }), selected && profiles.length > 0 && /* @__PURE__ */ React.createElement("group", { ref: listAnchorRef }, /* @__PURE__ */ React.createElement(Html, { zIndexRange: [30, 0], style: { transform: "translate(24px, -50%)" } }, /* @__PURE__ */ React.createElement(ModeList, { profiles, selected: modeIndex, aspect: size[va] / Math.max(size[ua], 1e-12), onSelect: selectMode }))));
}

// src/boundary.tsx
var FACES = ["x_low", "x_high", "y_low", "y_high", "z_low", "z_high"];
var SPEED_OF_LIGHT = 299792458;
var KIND_LABEL = {
  none: "None",
  pml: "PML",
  periodic: "Periodic",
  bloch: "Bloch",
  pec: "PEC",
  pmc: "PMC"
};
function faceKinds(solver) {
  const mode = String(value(solver, "mode", "global"));
  if (mode === "per_axis") return FACES.map((f) => String(value(solver, f[0], "pml")));
  if (mode === "per_face") return FACES.map((f) => String(value(solver, f, "pml")));
  return FACES.map(() => String(value(solver, "kind", "pml")));
}
function cellSize(solver) {
  const frequencies = (value(solver, "frequencies", []) ?? []).map(Number).filter((f2) => f2 > 0);
  const f = frequencies.length ? Math.max(...frequencies) : Number(value(solver, "frequency", 1e9)) || 1e9;
  const ppw = Math.max(4, Math.min(20, Math.floor(Number(value(solver, "ppw", 10)) + 0.5)));
  return SPEED_OF_LIGHT / f / ppw;
}
function pmlInset(solver, kinds) {
  const published = value(solver, "pml_inset", null);
  if (Array.isArray(published) && published.length === 6) return published.map(Number);
  const thickness = Number(value(solver, "num_layers", 15)) * cellSize(solver);
  return kinds.map((k) => k === "pml" ? thickness : 0);
}
function domainFaces(domain) {
  const centre = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2);
  return FACES.map((_, i) => {
    const axis = Math.floor(i / 2);
    const side = i % 2 ? 1 : -1;
    const plane = side < 0 ? domain.min[axis] : domain.max[axis];
    const center = [...centre];
    center[axis] = plane;
    const size = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]);
    size[axis] = 0;
    return { axis, side, plane, center, size };
  });
}
function chevron(face, length) {
  const u = (face.axis + 1) % 3;
  const tip = [...face.center];
  tip[face.axis] += face.side * length * 0.5;
  const segments = [];
  for (const offset of [-length * 0.25, length * 0.25]) {
    const t = [...tip];
    t[face.axis] += face.side * offset;
    for (const s of [-1, 1]) {
      const b = [...t];
      b[face.axis] -= face.side * length * 0.5;
      b[u] += s * length * 0.5;
      segments.push(t, b);
    }
  }
  return segments;
}
function hatch(face, count) {
  const [u, v] = [0, 1, 2].filter((a) => a !== face.axis);
  const lo = (a) => face.center[a] - face.size[a] / 2;
  const segments = [];
  for (let i = 1; i < count; i++) {
    const t = i / count;
    const a = [...face.center];
    const b = [...face.center];
    a[u] = lo(u) + t * face.size[u];
    a[v] = lo(v);
    b[u] = lo(u);
    b[v] = lo(v) + t * face.size[v];
    segments.push(a, b);
    const c = [...face.center];
    const d = [...face.center];
    c[u] = lo(u) + t * face.size[u];
    c[v] = lo(v) + face.size[v];
    d[u] = lo(u) + face.size[u];
    d[v] = lo(v) + t * face.size[v];
    segments.push(c, d);
  }
  return segments;
}
function FaceBoundary({ face, kind, inset, palette, dash, bench }) {
  const color = palette.boundary;
  if (kind === "pml" && inset > 0) {
    const inner = face.plane - face.side * inset;
    const min = [0, 1, 2].map((a) => face.center[a] - face.size[a] / 2);
    const max = [0, 1, 2].map((a) => face.center[a] + face.size[a] / 2);
    min[face.axis] = Math.min(face.plane, inner);
    max[face.axis] = Math.max(face.plane, inner);
    const innerCenter = [...face.center];
    innerCenter[face.axis] = inner;
    return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(BoxFill, { min, max, color, opacity: bench ? 0.035 : 0.06 }), /* @__PURE__ */ React.createElement(PlaneRect, { center: innerCenter, size: face.size, color, dashed: true, dash, lineWidth: 1 }));
  }
  if (kind === "periodic" || kind === "bloch") {
    return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(PlaneRect, { center: face.center, size: face.size, color, dashed: true, dash: dash * 0.6, lineWidth: 1.25 }), /* @__PURE__ */ React.createElement(Line, { points: chevron(face, Math.min(face.size[(face.axis + 1) % 3], face.size[(face.axis + 2) % 3]) * 0.08), segments: true, color, lineWidth: 1.5, raycast: noRaycast }));
  }
  if (kind === "pec" || kind === "pmc") {
    return /* @__PURE__ */ React.createElement(
      PlaneRect,
      {
        center: face.center,
        size: face.size,
        color,
        dashed: kind === "pmc",
        dash: dash * 0.4,
        lineWidth: 2,
        fillOpacity: kind === "pec" ? 0.3 : 0.15
      }
    );
  }
  return null;
}
function SymmetryPlane({ face, mode, palette }) {
  const segments = useMemo(() => hatch(face, 8), [face]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(PlaneRect, { center: face.center, size: face.size, color: palette.boundary, lineWidth: 2, fillOpacity: mode === "PEC" ? 0.18 : 0.1 }), /* @__PURE__ */ React.createElement(Line, { points: segments, segments: true, color: palette.boundary, lineWidth: 1, transparent: true, opacity: 0.7, raycast: noRaycast }));
}
function GridTicks({ domain, solver, palette, labelAt }) {
  const resolution = vec3(solver, "resolution", [1, 1, 1]).map((n) => Math.max(1, Math.round(n)));
  const cell = cellSize(solver);
  const segments = useMemo(() => {
    const out = [];
    const tick = domain.extent * 0.012;
    for (let a = 0; a < 3; a++) {
      const b = (a + 1) % 3;
      const n = resolution[a];
      const step = Math.max(1, Math.ceil(n / 100));
      const d = (domain.max[a] - domain.min[a]) / n;
      for (let k = 0; k <= n; k += step) {
        const p = [...domain.min];
        p[a] = domain.min[a] + k * d;
        const q = [...p];
        q[b] -= k % (step * 5) === 0 ? tick * 1.8 : tick;
        out.push(p, q);
      }
    }
    return out;
  }, [domain, ...resolution]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: segments, segments: true, color: palette.text, lineWidth: 1, transparent: true, opacity: 0.75, raycast: noRaycast }), /* @__PURE__ */ React.createElement(Label, { position: labelAt }, `Grid \u0394 ${formatLength(cell)} \xB7 ${resolution.join(" \xD7 ")}`));
}
function SolverAnnotations({ solver, domain, selected, stage, palette }) {
  const faces = useMemo(() => domainFaces(domain), [domain]);
  const kinds = faceKinds(solver);
  const inset = pmlInset(solver, kinds);
  const dash = domain.extent * 0.015;
  const bench = stage?.kind === "bench";
  const uniform = kinds.every((k) => k === kinds[0]);
  const layers = Math.round(Number(value(solver, "num_layers", 15)));
  const kindText = (k) => k === "pml" ? `PML \xB7 ${layers} layers` : KIND_LABEL[k] ?? k;
  const symmetry = [0, 1, 2].map((axis) => ({ axis, mode: String(value(solver, `symmetry_${AXIS_NAMES[axis]}`, "none")), side: String(value(solver, `symmetry_${AXIS_NAMES[axis]}_face`, "low")) })).filter((s) => s.mode !== "none");
  const top = [(domain.min[0] + domain.max[0]) / 2, domain.max[1], (domain.min[2] + domain.max[2]) / 2];
  return /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "scene" }, faces.map((face, i) => /* @__PURE__ */ React.createElement(FaceBoundary, { key: FACES[i], face, kind: kinds[i], inset: inset[i], palette, dash, bench })), symmetry.map(({ axis, mode, side }) => /* @__PURE__ */ React.createElement(SymmetryPlane, { key: axis, face: faces[axis * 2 + (side === "high" ? 1 : 0)], mode, palette })), selected && uniform && /* @__PURE__ */ React.createElement(Label, { position: top, row: 1, color: palette.boundary }, `Boundary \xB7 ${kindText(kinds[0])}`), selected && !uniform && faces.map((face, i) => {
    const at = [...face.center];
    at[face.axis] += face.side * domain.extent * 0.05;
    return /* @__PURE__ */ React.createElement(Label, { key: FACES[i], position: at, color: palette.boundary }, `${AXIS_NAMES[face.axis]} ${face.side < 0 ? "low" : "high"} \xB7 ${kindText(kinds[i])}`);
  }), selected && symmetry.map(({ axis, mode, side }) => {
    const face = faces[axis * 2 + (side === "high" ? 1 : 0)];
    const at = [...face.center];
    at[(axis + 1) % 3] += face.size[(axis + 1) % 3] * 0.3;
    return /* @__PURE__ */ React.createElement(Label, { key: `sym${axis}`, position: at, color: palette.boundary }, `${mode} symmetry \xB7 ${AXIS_NAMES[axis]} ${side}`);
  }), selected && /* @__PURE__ */ React.createElement(GridTicks, { domain, solver, palette, labelAt: top }));
}

// src/handles.tsx
var SCREEN_RADIUS = 6e-3;
var HOVER_SCALE = 1.35;
function axisParameter(ray, p, u) {
  const w0 = p.clone().sub(ray.origin);
  const b = u.dot(ray.direction);
  const c = ray.direction.dot(ray.direction);
  const d = u.dot(w0);
  const e = ray.direction.dot(w0);
  const denom = u.dot(u) * c - b * b;
  if (Math.abs(denom) < 1e-12 * c) return null;
  return (b * e - c * d) / denom;
}
function AxisHandle({
  position,
  axis,
  color,
  interaction,
  onMove,
  onEnd
}) {
  const mesh = useRef(null);
  const drag = useRef(null);
  const [hovered, setHovered] = useState(false);
  useFrame(({ camera }) => {
    const m = mesh.current;
    if (!m?.parent) return;
    const world = m.getWorldPosition(new THREE.Vector3());
    const parentScale = m.parent.getWorldScale(new THREE.Vector3()).x || 1;
    const ortho = camera.isOrthographicCamera;
    const viewHeight = ortho ? (camera.top - camera.bottom) / camera.zoom : 2 * world.distanceTo(camera.position) * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2));
    m.scale.setScalar(viewHeight * SCREEN_RADIUS / parentScale * (hovered || drag.current ? HOVER_SCALE : 1));
  });
  const localRay = (e) => {
    const parent = mesh.current?.parent;
    if (!parent) return null;
    return e.ray.clone().applyMatrix4(parent.matrixWorld.clone().invert());
  };
  const parameter = (e) => {
    const ray = localRay(e);
    return ray ? axisParameter(ray, new THREE.Vector3(...position), new THREE.Vector3().setComponent(axis, 1)) : null;
  };
  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const t = parameter(e);
    if (t === null) return;
    e.target?.setPointerCapture?.(e.pointerId);
    drag.current = { start: t };
    interaction.setGizmoDragging(true);
  };
  const onPointerMove = (e) => {
    if (!drag.current) return;
    e.stopPropagation();
    const t = parameter(e);
    if (t === null) return;
    onMove(t - drag.current.start, { snap: e.ctrlKey || e.metaKey, symmetric: e.altKey });
  };
  const finish = (e) => {
    if (!drag.current) return;
    e.stopPropagation();
    e.target?.releasePointerCapture?.(e.pointerId);
    drag.current = null;
    interaction.setGizmoDragging(false);
    onEnd();
  };
  return /* @__PURE__ */ React.createElement(
    "mesh",
    {
      ref: mesh,
      position,
      renderOrder: 20,
      userData: { isGizmo: true },
      onPointerDown,
      onPointerMove,
      onPointerUp: finish,
      onPointerCancel: finish,
      onPointerOver: (e) => {
        e.stopPropagation();
        setHovered(true);
      },
      onPointerOut: () => setHovered(false)
    },
    /* @__PURE__ */ React.createElement("sphereGeometry", { args: [1, 16, 12] }),
    /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, depthTest: false, depthWrite: false, transparent: true, toneMapped: false })
  );
}
function dragBox(start, axis, side, delta, mods, cell, minSize) {
  const d = mods.snap && cell > 0 ? Math.round(delta / cell) * cell : delta;
  const min = [...start.min];
  const max = [...start.max];
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
function BoxHandles({
  box,
  axes,
  color,
  cell,
  minSize,
  interaction,
  onPreview,
  onCommit
}) {
  const start = useRef(null);
  const latest = useRef(null);
  const centre = [0, 1, 2].map((a) => (box.min[a] + box.max[a]) / 2);
  const handles = axes.flatMap(
    (axis) => [-1, 1].map((side) => {
      const p = [...centre];
      p[axis] = side < 0 ? box.min[axis] : box.max[axis];
      return { axis, side, position: p };
    })
  );
  return /* @__PURE__ */ React.createElement("group", { userData: { isGizmo: true } }, handles.map(({ axis, side, position }) => /* @__PURE__ */ React.createElement(
    AxisHandle,
    {
      key: `${axis}${side}`,
      position,
      axis,
      color,
      interaction,
      onMove: (delta, mods) => {
        if (!start.current) start.current = box;
        latest.current = dragBox(start.current, axis, side, delta, mods, cell, minSize);
        onPreview(latest.current);
      },
      onEnd: () => {
        const next = latest.current;
        start.current = null;
        latest.current = null;
        if (next) onCommit(next);
      }
    }
  )));
}
function PositionHandle({
  position,
  axis,
  color,
  cell,
  interaction,
  onPreview,
  onCommit
}) {
  const start = useRef(null);
  const latest = useRef(null);
  return /* @__PURE__ */ React.createElement("group", { userData: { isGizmo: true } }, /* @__PURE__ */ React.createElement(
    AxisHandle,
    {
      position,
      axis,
      color,
      interaction,
      onMove: (delta, mods) => {
        if (start.current === null) start.current = position[axis];
        const d = mods.snap && cell > 0 ? Math.round(delta / cell) * cell : delta;
        latest.current = start.current + d;
        onPreview(latest.current);
      },
      onEnd: () => {
        const next = latest.current;
        start.current = null;
        latest.current = null;
        if (next !== null) onCommit(next);
      }
    }
  ));
}

// src/preview.ts
var OFFSET_KEY = "__anchor_offset";
var previews = /* @__PURE__ */ new Map();
var listeners = /* @__PURE__ */ new Set();
function emit() {
  for (const listener of listeners) listener();
}
function setPreview(objectId, values) {
  if (values) previews.set(objectId, values);
  else previews.delete(objectId);
  emit();
}
function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function usePreview(objectId) {
  return React.useSyncExternalStore(subscribe, () => previews.get(objectId) ?? null);
}
function withPreview(component, preview) {
  if (!preview || !component) return component;
  return { ...component, values: { ...component.values, ...preview } };
}

// src/sourceTime.ts
function sourceTimeLabel(component, gate = "st_enabled") {
  if (!value(component, gate, gate === "st_enabled")) return null;
  const kind = String(value(component, "st_kind", "cw"));
  const f0 = formatFrequency(Number(value(component, "st_frequency", 1e9)));
  if (kind === "gaussian_pulse") return `Gaussian pulse \xB7 ${f0} \xB1 ${formatFrequency(Number(value(component, "st_fwidth", 1e8)))}`;
  if (kind === "ricker") return `Ricker \xB7 ${f0}`;
  return `CW \xB7 ${f0}`;
}

// src/visuals.tsx
function fieldsText(component) {
  const fields = value(component, "fields", []);
  return Array.isArray(fields) && fields.length ? fields.join(", ") : "";
}
function joinLabel(...parts) {
  return parts.filter(Boolean).join(" \xB7 ");
}
function basis(direction, hint) {
  const n = new THREE.Vector3(...direction);
  if (n.lengthSq() < 1e-20) n.set(0, 0, 1);
  n.normalize();
  const e1 = new THREE.Vector3(...hint).projectOnPlane(n);
  if (e1.lengthSq() < 1e-12) e1.copy(Math.abs(n.x) < 0.9 ? new THREE.Vector3(1, 0, 0) : new THREE.Vector3(0, 1, 0)).projectOnPlane(n);
  e1.normalize();
  return { n, e1, e2: new THREE.Vector3().crossVectors(n, e1) };
}
function Wavefront({ center, direction, polarization, side, color, opacity }) {
  const { loop, fill } = useMemo(() => {
    const { e1, e2 } = basis(direction, polarization);
    const c = new THREE.Vector3(...center);
    const h = side / 2;
    const corners = [
      [-h, -h],
      [h, -h],
      [h, h],
      [-h, h]
    ].map(([a, b]) => c.clone().addScaledVector(e1, a).addScaledVector(e2, b));
    const geometry = new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]);
    return { loop: [...corners, corners[0]].map((p) => p.toArray()), fill: geometry };
  }, [...center, ...direction, ...polarization, side]);
  React.useEffect(() => () => fill.dispose(), [fill]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: loop, color, lineWidth: 1.5, transparent: opacity < 1, opacity, raycast: noRaycast }), /* @__PURE__ */ React.createElement("mesh", { geometry: fill, renderOrder: 1, raycast: noRaycast }, /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, transparent: true, opacity: 0.16 * opacity, side: THREE.DoubleSide, depthWrite: false, toneMapped: false })));
}
function polarizationOf(component) {
  const mode = String(value(component, "polarization_mode", "Ez"));
  return mode === "vector" ? vec3(component, "polarization", [0, 0, 1]) : axisVector(AXIS_INDEX[mode] ?? 2);
}
function PointDipole({ component, domain, selected, palette, origin }) {
  const r = domain.extent * 0.015;
  const p = new THREE.Vector3(...polarizationOf(component)).normalize();
  const length = domain.extent * 0.14;
  const color = insideDomain(domain, origin) ? palette.emitter : palette.warning;
  const mode = String(value(component, "polarization_mode", "Ez"));
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement("mesh", { raycast: noRaycast }, /* @__PURE__ */ React.createElement("sphereGeometry", { args: [r, 16, 12] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, toneMapped: false })), /* @__PURE__ */ React.createElement(Arrow, { origin: p.clone().multiplyScalar(-length / 2).toArray(), direction: p.toArray(), length, color }), /* @__PURE__ */ React.createElement(HitSphere, { radius: r * 3 }), selected && /* @__PURE__ */ React.createElement(Label, { position: [0, length / 2, 0], color }, joinLabel(`Dipole ${mode === "vector" ? "p" : mode}`, sourceTimeLabel(component), color === palette.warning && "Outside domain")));
}
function DirectedWave({ component, domain, selected, palette, origin, gaussian }) {
  const direction = vec3(component, "direction", [0, 0, 1]);
  const polarization = vec3(component, "polarization", [1, 0, 0]);
  const { n, e1 } = basis(direction, polarization);
  const side = domain.extent * 0.22;
  const crest = domain.extent * 0.035;
  const color = insideDomain(domain, origin) ? palette.emitter : palette.warning;
  const name = gaussian ? "Gaussian beam" : "Plane wave";
  const tfsf = value(component, "injection", "soft") === "tfsf";
  return /* @__PURE__ */ React.createElement("group", null, [0, 1, 2].map((i) => /* @__PURE__ */ React.createElement(
    Wavefront,
    {
      key: i,
      center: n.clone().multiplyScalar(i * crest).toArray(),
      direction,
      polarization,
      side,
      color,
      opacity: [1, 0.5, 0.25][i]
    }
  )), /* @__PURE__ */ React.createElement(Arrow, { origin: [0, 0, 0], direction: n.toArray(), length: domain.extent * 0.16, color }), /* @__PURE__ */ React.createElement(Arrow, { origin: [0, 0, 0], direction: e1.toArray(), length: side * 0.42, color, lineWidth: 1.25, opacity: 0.85 }), /* @__PURE__ */ React.createElement(HitSphere, { radius: side * 0.5 }), selected && /* @__PURE__ */ React.createElement(Label, { position: [0, side * 0.7, 0], color }, joinLabel(name, tfsf && "TFSF", sourceTimeLabel(component), color === palette.warning && "Outside domain")));
}
function DirectedWaveScene({ component, domain, palette, gaussian }) {
  const tfsf = value(component, "injection", "soft") === "tfsf";
  const min = vec3(component, "tfsf_min", [-0.5, -0.5, -0.5]);
  const max = vec3(component, "tfsf_max", [0.5, 0.5, 0.5]);
  const focus = vec3(component, "focus", [0, 0, 0]);
  const edges = useMemo(() => boxEdges(min, max), [...min, ...max]);
  const marker = domain.extent * 0.012;
  return /* @__PURE__ */ React.createElement("group", null, tfsf && /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: edges, segments: true, color: palette.emitter, lineWidth: 1.25, raycast: noRaycast }), /* @__PURE__ */ React.createElement(BoxFill, { min, max, color: palette.emitter, opacity: 0.035 })), gaussian && /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Ring, { center: focus, normal: vec3(component, "direction", [0, 0, 1]), radius: Math.max(Number(value(component, "beam_waist", 0.5)), 1e-12), color: palette.emitter, dashed: true, dash: domain.extent * 0.012 }), /* @__PURE__ */ React.createElement(
    Line,
    {
      points: [add(focus, [-marker, 0, 0]), add(focus, [marker, 0, 0]), add(focus, [0, -marker, 0]), add(focus, [0, marker, 0]), add(focus, [0, 0, -marker]), add(focus, [0, 0, marker])],
      segments: true,
      color: palette.emitter,
      lineWidth: 1.5,
      raycast: noRaycast
    }
  )));
}
function PointMonitor({ component, domain, selected, palette, origin }) {
  const s = domain.extent * 0.016;
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement("mesh", { raycast: noRaycast }, /* @__PURE__ */ React.createElement("octahedronGeometry", { args: [s] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, wireframe: true, toneMapped: false })), /* @__PURE__ */ React.createElement("mesh", { raycast: noRaycast, renderOrder: 1 }, /* @__PURE__ */ React.createElement("octahedronGeometry", { args: [s * 0.98] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, transparent: true, opacity: 0.25, depthWrite: false, toneMapped: false })), /* @__PURE__ */ React.createElement(HitSphere, { radius: s * 2.5 }), selected && /* @__PURE__ */ React.createElement(Label, { position: [0, s * 2.2, 0], color }, joinLabel("Point monitor", fieldsText(component), color === palette.warning && "Outside domain")));
}
function FluxArrow({ center, normal, component, domain, color }) {
  if (!value(component, "compute_flux", false)) return null;
  const sign = value(component, "normal_direction", "+") === "-" ? -1 : 1;
  return /* @__PURE__ */ React.createElement(Arrow, { origin: center, direction: axisVector(normal, sign), length: domain.extent * 0.08, color });
}
function PlaneMonitorScene({ component, domain, selected, palette }) {
  const axis = AXIS_INDEX[String(value(component, "axis", "z"))] ?? 2;
  const position = Number(value(component, "position", 0));
  const center = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2);
  center[axis] = position;
  const size = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]);
  size[axis] = 0;
  const color = insideDomain(domain, center) ? palette.sensor : palette.warning;
  const flux = !!value(component, "compute_flux", false);
  const labelAt = [...center];
  if (axis !== 1) labelAt[1] = domain.max[1];
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(PlaneRect, { center, size, color, dashed: true, dash: domain.extent * 0.012, fillOpacity: flux ? 0.12 : 0.05 }), /* @__PURE__ */ React.createElement(FluxArrow, { center, normal: axis, component, domain, color }), /* @__PURE__ */ React.createElement(HitPlane, { center, size }), selected && /* @__PURE__ */ React.createElement(Label, { position: labelAt, color }, joinLabel(flux ? "Flux monitor" : "Plane monitor", fieldsText(component), `${AXIS_NAMES[axis]} = ${formatLength(position)}`, color === palette.warning && "Outside domain")));
}
function FinitePlaneMonitor({ component, domain, selected, palette, origin }) {
  const size = vec3(component, "size", [1, 1, 0]);
  const normal = normalAxis(size);
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  const flux = !!value(component, "compute_flux", false);
  const labelAt = [0, size[1] / 2, 0];
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(PlaneRect, { center: [0, 0, 0], size, color, dashed: true, dash: domain.extent * 0.012, fillOpacity: flux ? 0.12 : 0.05 }), /* @__PURE__ */ React.createElement(FluxArrow, { center: [0, 0, 0], normal, component, domain, color }), /* @__PURE__ */ React.createElement(HitPlane, { center: [0, 0, 0], size }), selected && /* @__PURE__ */ React.createElement(Label, { position: labelAt, color }, joinLabel(flux ? "Flux monitor" : "Plane monitor", fieldsText(component), color === palette.warning && "Outside domain")));
}
function ClosedSurfaceMonitor({ component, domain, selected, palette, origin }) {
  const size = vec3(component, "size", [1, 1, 1]);
  const half = size.map((s) => s / 2);
  const min = half.map((h) => -h);
  const segments = useMemo(() => boxEdges(min, half), [...half]);
  const color = insideDomain(domain, origin) ? palette.sensor : palette.warning;
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: segments, segments: true, color, lineWidth: 1.25, dashed: true, dashSize: domain.extent * 0.012, gapSize: domain.extent * 8e-3, raycast: noRaycast }), /* @__PURE__ */ React.createElement(BoxFill, { min, max: half, color, opacity: 0.035 }), /* @__PURE__ */ React.createElement(HitBox, { min, max: half }), selected && /* @__PURE__ */ React.createElement(Label, { position: [0, half[1] + domain.extent * 0.04, 0], color }, joinLabel("Closed surface", "flux", color === palette.warning && "Outside domain")));
}
function ModePlaneVisual(props) {
  const { component, domain, selected, palette, origin, color: base, dashed, title, time } = props;
  const size = vec3(component, "size", [1, 1, 0]);
  const normal = normalAxis(size);
  const color = insideDomain(domain, origin) ? base : palette.warning;
  const labelAt = [0, size[1] / 2, 0];
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(ModePlane, { scene: props.scene, object: props.object, component, selected, domain, color, dashed }), /* @__PURE__ */ React.createElement(HitPlane, { center: [0, 0, 0], size }), selected && /* @__PURE__ */ React.createElement(Label, { position: labelAt, color }, joinLabel(title, `mode ${Number(value(component, "mode_index", 0))}`, time, color === palette.warning && "Outside domain")));
}
function ModePort(props) {
  const { component, domain, palette } = props;
  const exciting = !!value(component, "is_source", false);
  const size = vec3(component, "size", [1, 1, 0]);
  const normal = normalAxis(size);
  const offset = Number(value(component, "monitor_offset", 0));
  const monitorCenter = axisVector(normal, offset);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(
    ModePlaneVisual,
    {
      ...props,
      color: exciting ? palette.emitter : palette.sensor,
      dashed: false,
      title: exciting ? "Port \xB7 source" : "Port",
      time: exciting ? sourceTimeLabel(component, "is_source") : null
    }
  ), exciting && offset !== 0 && /* @__PURE__ */ React.createElement(PlaneRect, { center: monitorCenter, size, color: palette.sensor, dashed: true, dash: domain.extent * 0.012 }));
}
function MaterialRegion({ component, selected, palette }) {
  const n = [value(component, "density_nx", 8), value(component, "density_ny", 8), value(component, "density_nz", 8)].map((v) => Math.max(1, Math.min(32, Math.round(Number(v)))));
  const edges = useMemo(() => boxEdges([-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]), []);
  const lattice = useMemo(() => {
    const out = [];
    for (let face = 0; face < 3; face++) {
      const [u, v] = [0, 1, 2].filter((a) => a !== face);
      for (const [along, across] of [
        [u, v],
        [v, u]
      ]) {
        for (let k = 1; k < n[across]; k++) {
          const a = [-0.5, -0.5, -0.5];
          a[across] = -0.5 + k / n[across];
          const b = [...a];
          b[along] = 0.5;
          out.push(a, b);
        }
      }
    }
    return out;
  }, [...n]);
  const name = String(value(component, "region_name", "")) || "Design region";
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: edges, segments: true, color: palette.region, lineWidth: 1.75, raycast: noRaycast }), selected && /* @__PURE__ */ React.createElement(Line, { points: lattice, segments: true, color: palette.region, lineWidth: 1, transparent: true, opacity: 0.55, raycast: noRaycast }), selected && /* @__PURE__ */ React.createElement(Label, { position: [0, 0.62, 0], color: palette.region }, joinLabel(name, `${n.join(" \xD7 ")} density`)));
}
var VISUALS = [
  { component: "PointDipoleSource", local: (c) => /* @__PURE__ */ React.createElement(PointDipole, { ...c }) },
  { component: "PlaneWaveSource", local: (c) => /* @__PURE__ */ React.createElement(DirectedWave, { ...c, gaussian: false }), scene: (c) => /* @__PURE__ */ React.createElement(DirectedWaveScene, { ...c, gaussian: false }) },
  { component: "GaussianBeamSource", local: (c) => /* @__PURE__ */ React.createElement(DirectedWave, { ...c, gaussian: true }), scene: (c) => /* @__PURE__ */ React.createElement(DirectedWaveScene, { ...c, gaussian: true }) },
  { component: "ModeSource", local: (c) => /* @__PURE__ */ React.createElement(ModePlaneVisual, { ...c, color: c.palette.emitter, dashed: false, title: "Mode source", time: sourceTimeLabel(c.component) }) },
  { component: "PointMonitor", local: (c) => /* @__PURE__ */ React.createElement(PointMonitor, { ...c }) },
  { component: "PlaneMonitor", scene: (c) => /* @__PURE__ */ React.createElement(PlaneMonitorScene, { ...c }) },
  { component: "FinitePlaneMonitor", local: (c) => /* @__PURE__ */ React.createElement(FinitePlaneMonitor, { ...c }) },
  { component: "ClosedSurfaceMonitor", local: (c) => /* @__PURE__ */ React.createElement(ClosedSurfaceMonitor, { ...c }) },
  { component: "ModeMonitor", local: (c) => /* @__PURE__ */ React.createElement(ModePlaneVisual, { ...c, color: c.palette.sensor, dashed: true, title: "Mode monitor" }) },
  { component: "ModePort", local: (c) => /* @__PURE__ */ React.createElement(ModePort, { ...c }) }
];
var SIZED = /* @__PURE__ */ new Set(["FinitePlaneMonitor", "ModeMonitor", "ModeSource", "ModePort", "ClosedSurfaceMonitor"]);
function solverOf(scene) {
  for (const object of Object.values(scene.getObjects())) {
    const solver = findComponent(object, "MaxwellSolver");
    if (solver) return solver;
  }
  return null;
}
function offsetOf(preview) {
  const v = preview?.[OFFSET_KEY];
  return Array.isArray(v) ? v : void 0;
}
function MaxwellHandles({ host, scene, object, name, domain, palette }) {
  const preview = usePreview(object.id);
  const component = withPreview(findComponent(object, name), preview);
  const solver = solverOf(scene);
  const cell = solver ? cellSize(solver) : 0;
  const minSize = cell > 0 ? cell : domain.extent * 1e-3;
  const interaction = host.interaction;
  const offset = offsetOf(preview);
  const done = (writes) => {
    void Promise.allSettled(writes).then(() => setPreview(object.id, null));
  };
  if (SIZED.has(name)) {
    const size = vec3(component, "size", [1, 1, 1]);
    const plane = name !== "ClosedSurfaceMonitor";
    const normal = normalAxis(size);
    const axes = plane ? [0, 1, 2].filter((a) => a !== normal) : [0, 1, 2];
    const shift = offset ?? [0, 0, 0];
    const box = { min: size.map((s, a) => shift[a] - s / 2), max: size.map((s, a) => shift[a] + s / 2) };
    const toFields = (b) => {
      const nextSize = [0, 1, 2].map((a) => plane && a === normal ? 0 : b.max[a] - b.min[a]);
      const centre = [0, 1, 2].map((a) => plane && a === normal ? 0 : (b.min[a] + b.max[a]) / 2);
      return { nextSize, centre };
    };
    return /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "object" }, /* @__PURE__ */ React.createElement(
      BoxHandles,
      {
        box,
        axes,
        color: palette.accent,
        cell,
        minSize,
        interaction,
        onPreview: (b) => {
          const { nextSize, centre } = toFields(b);
          setPreview(object.id, { size: nextSize, [OFFSET_KEY]: centre });
        },
        onCommit: (b) => {
          const { nextSize, centre } = toFields(b);
          const writes = [scene.updateComponentField(object.id, name, "size", nextSize)];
          if (centre.some((c) => Math.abs(c) > 1e-12)) {
            writes.push(scene.updateObjectTransform(object.id, { position: add(positionOf(object), centre) }));
          }
          done(writes);
        }
      }
    ));
  }
  if ((name === "PlaneWaveSource" || name === "GaussianBeamSource") && value(component, "injection", "soft") === "tfsf") {
    const box = { min: vec3(component, "tfsf_min", [-0.5, -0.5, -0.5]), max: vec3(component, "tfsf_max", [0.5, 0.5, 0.5]) };
    return /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "scene" }, /* @__PURE__ */ React.createElement(
      BoxHandles,
      {
        box,
        axes: [0, 1, 2],
        color: palette.accent,
        cell,
        minSize,
        interaction,
        onPreview: (b) => setPreview(object.id, { tfsf_min: b.min, tfsf_max: b.max }),
        onCommit: (b) => done([scene.updateComponentField(object.id, name, "tfsf_min", b.min), scene.updateComponentField(object.id, name, "tfsf_max", b.max)])
      }
    ));
  }
  if (name === "PlaneMonitor") {
    const axis = AXIS_INDEX[String(value(component, "axis", "z"))] ?? 2;
    const at = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2);
    at[axis] = Number(value(component, "position", 0));
    return /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "scene" }, /* @__PURE__ */ React.createElement(
      PositionHandle,
      {
        position: at,
        axis,
        color: palette.accent,
        cell,
        interaction,
        onPreview: (coordinate) => setPreview(object.id, { position: coordinate }),
        onCommit: (coordinate) => done([scene.updateComponentField(object.id, name, "position", coordinate)])
      }
    ));
  }
  return null;
}
var HANDLED = [...SIZED, "PlaneWaveSource", "GaussianBeamSource", "PlaneMonitor"];
function registerMaxwellVisuals(host) {
  const scene = host.services.get("scene");
  for (const visual of VISUALS) {
    let MaxwellVisual = function({ object, selected, stage }) {
      const domain = useDomain(scene);
      const preview = usePreview(object.id);
      const raw = findComponent(object, visual.component);
      if (!raw || object.visible === false) return null;
      const component = withPreview(raw, preview);
      const offset = offsetOf(preview);
      const origin = offset ? add(positionOf(object), offset) : positionOf(object);
      const ctx = { scene, object, component, domain, selected, stage, palette: paletteOf(stage), origin };
      return /* @__PURE__ */ React.createElement(React.Fragment, null, visual.local && /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "object", offset }, visual.local(ctx)), visual.scene && /* @__PURE__ */ React.createElement(SceneFrame, { anchor: "scene" }, visual.scene(ctx)));
    };
    host.registerVisualizer({
      id: `witwin.maxwell.${visual.component}`,
      priority: 80,
      skipStandardGeometry: true,
      match: (object) => !!findComponent(object, visual.component),
      component: MaxwellVisual
    });
  }
  function MaxwellSolverGizmo({ object, selected, stage }) {
    const domain = useDomain(scene);
    const solver = findComponent(object, "MaxwellSolver");
    if (!solver || object.visible === false || !domain.real) return null;
    return /* @__PURE__ */ React.createElement(SolverAnnotations, { solver, domain, selected, stage, palette: paletteOf(stage) });
  }
  host.registerGizmo({
    id: "witwin.maxwell.pml",
    priority: 80,
    match: (object) => !!findComponent(object, "MaxwellSolver"),
    component: MaxwellSolverGizmo
  });
  function MaterialRegionGizmo({ object, selected, stage }) {
    const component = findComponent(object, "MaterialRegion");
    if (!component || object.visible === false) return null;
    return /* @__PURE__ */ React.createElement(MaterialRegion, { component, selected, palette: paletteOf(stage) });
  }
  host.registerGizmo({
    id: "witwin.maxwell.region",
    priority: 80,
    match: (object) => !!findComponent(object, "MaterialRegion"),
    component: MaterialRegionGizmo
  });
  function MaxwellHandlesGizmo({ object, selected, stage, tool }) {
    const domain = useDomain(scene);
    if (!selected || object.visible === false || tool !== void 0 && tool !== "bounds") return null;
    const name = HANDLED.find((n) => findComponent(object, n));
    if (!name) return null;
    return /* @__PURE__ */ React.createElement(MaxwellHandles, { host, scene, object, name, domain, palette: paletteOf(stage) });
  }
  host.registerGizmo({
    id: "witwin.maxwell.handles",
    priority: 90,
    match: (object) => HANDLED.some((n) => !!findComponent(object, n)),
    component: MaxwellHandlesGizmo
  });
}

// src/viewport.ts
var sdkVersion = "2.0.0";
var plugin = {
  id: "witwin.maxwell",
  inject: ["scene"],
  activate(host) {
    registerMaxwellVisuals(host);
  }
};
var viewport_default = plugin;
export {
  viewport_default as default,
  sdkVersion
};
