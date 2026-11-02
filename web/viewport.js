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
var SOURCE_COLOR = "#2f7fe0";
var MONITOR_COLOR = "#2fa565";
var PML_COLOR = "#8f959c";
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
var DEFAULT_DOMAIN = { min: [-1, -1, -1], max: [1, 1, 1], extent: 2 };
function domainKey(host) {
  for (const object of Object.values(host.scene.getObjects())) {
    const solver = findComponent(object, "MaxwellSolver");
    if (solver) return JSON.stringify([vec3(solver, "min_bound", [-1, -1, -1]), vec3(solver, "max_bound", [1, 1, 1])]);
  }
  return "";
}
function useDomain(host) {
  const key = React.useSyncExternalStore(host.scene.subscribe, () => domainKey(host));
  return React.useMemo(() => {
    if (!key) return DEFAULT_DOMAIN;
    const [min, max] = JSON.parse(key);
    const extent = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2], 1e-12);
    return { min, max, extent };
  }, [key]);
}
var UNITS = [
  [1, "m"],
  [1e-3, "mm"],
  [1e-6, "\xB5m"],
  [1e-9, "nm"]
];
function formatLength(metres) {
  const a = Math.abs(metres);
  const [scale, name] = UNITS.find(([s]) => a >= s) ?? UNITS[UNITS.length - 1];
  return `${Number((metres / scale).toPrecision(3))} ${name}`;
}
function worldToLocal(object) {
  const t = object.transform ?? {};
  const position = new THREE.Vector3(...t.position ?? [0, 0, 0]);
  const r = t.rotation ?? [0, 0, 0];
  const quaternion = r.length === 4 ? new THREE.Quaternion(r[0], r[1], r[2], r[3]) : new THREE.Quaternion().setFromEuler(new THREE.Euler(r[0], r[1], r[2]));
  const scale = new THREE.Vector3(...t.scale ?? [1, 1, 1]);
  return new THREE.Matrix4().compose(position, quaternion, scale).invert();
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

// src/primitives.tsx
function Arrow({ origin, direction, length, color }) {
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
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Line, { points: [origin, tip], color, lineWidth: 2 }), /* @__PURE__ */ React.createElement("mesh", { position: headCenter, quaternion }, /* @__PURE__ */ React.createElement("coneGeometry", { args: [head.radius, head.height, 18] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, toneMapped: false })));
}
function PlaneRect({
  center,
  size,
  color,
  dashed = false,
  dash,
  fillOpacity = 0
}) {
  const corners = rectCorners(center, size);
  const fill = useMemo(() => {
    if (fillOpacity <= 0) return null;
    const g = new THREE.BufferGeometry().setFromPoints(
      [corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]].map((c) => new THREE.Vector3(...c))
    );
    return g;
  }, [JSON.stringify(corners), fillOpacity > 0]);
  React.useEffect(() => () => fill?.dispose(), [fill]);
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(
    Line,
    {
      points: [...corners, corners[0]],
      color,
      lineWidth: 1.5,
      dashed,
      dashSize: dash,
      gapSize: dash ? dash * 0.6 : void 0
    }
  ), fill && /* @__PURE__ */ React.createElement("mesh", { geometry: fill, renderOrder: 1 }, /* @__PURE__ */ React.createElement("meshBasicMaterial", { color, transparent: true, opacity: fillOpacity, side: THREE.DoubleSide, depthWrite: false, toneMapped: false })));
}
function Label({ position, children }) {
  return /* @__PURE__ */ React.createElement(Html, { position, center: true, zIndexRange: [20, 0], style: { pointerEvents: "none" } }, /* @__PURE__ */ React.createElement(
    "div",
    {
      style: {
        padding: "1px 5px",
        borderRadius: 3,
        background: "var(--bg-tooltip, var(--gray-5))",
        color: "var(--text-primary)",
        font: "11px var(--font-family)",
        whiteSpace: "nowrap"
      }
    },
    children
  ));
}
function PlaneDimensions({ center, size, color }) {
  const normal = normalAxis(size);
  const [ua, va] = [0, 1, 2].filter((d) => d !== normal);
  const offset = Math.max(size[ua], size[va]) * 0.08;
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
  return /* @__PURE__ */ React.createElement("group", null, dims.map((d, i) => /* @__PURE__ */ React.createElement("group", { key: i }, /* @__PURE__ */ React.createElement(Line, { points: d.segments, segments: true, color, lineWidth: 1 }), /* @__PURE__ */ React.createElement(Label, { position: d.mid }, d.text))));
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
  host,
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
    void host.sceneWrites.updateComponentField(object.id, component.name, "mode_index", index);
  };
  const listAnchor = [0, 0, 0];
  listAnchor[ua] = size[ua] / 2 + planeSide * 0.12;
  return /* @__PURE__ */ React.createElement("group", null, profile && /* @__PURE__ */ React.createElement(ProfileSurface, { size, profile, opacity: 0.92 }), /* @__PURE__ */ React.createElement(PlaneRect, { center: origin, size, color, dashed, dash: domain.extent * 0.012, fillOpacity: profile ? 0 : 0.14 }), /* @__PURE__ */ React.createElement(Arrow, { origin, direction, length: Math.max(planeSide * 0.6, domain.extent * 0.06), color }), selected && /* @__PURE__ */ React.createElement(PlaneDimensions, { center: origin, size, color }), selected && profiles.length > 0 && /* @__PURE__ */ React.createElement(Html, { position: listAnchor, zIndexRange: [30, 0], style: { transform: "translate(8px, -50%)" } }, /* @__PURE__ */ React.createElement(ModeList, { profiles, selected: modeIndex, aspect: size[va] / Math.max(size[ua], 1e-12), onSelect: selectMode })));
}

// src/visuals.tsx
var AXIS_INDEX = { x: 0, y: 1, z: 2, Ex: 0, Ey: 1, Ez: 2 };
function axisVector(axis) {
  const v = [0, 0, 0];
  v[axis] = 1;
  return v;
}
function toLocal(object, points) {
  const m = worldToLocal(object);
  return points.map((p) => new THREE.Vector3(...p).applyMatrix4(m).toArray());
}
function DashedBox({ object, min, max, color, dash, opacity = 1 }) {
  const points = useMemo(() => toLocal(object, boxEdges(min, max)), [object, ...min, ...max]);
  return /* @__PURE__ */ React.createElement(Line, { points, segments: true, color, lineWidth: 1.25, dashed: true, dashSize: dash, gapSize: dash * 0.7, transparent: true, opacity });
}
function polarizationOf(component) {
  const mode = String(value(component, "polarization_mode", "Ez"));
  return mode === "vector" ? vec3(component, "polarization", [0, 0, 1]) : axisVector(AXIS_INDEX[mode] ?? 2);
}
function PointDipole({ component, domain }) {
  const r = domain.extent * 0.012;
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement("mesh", null, /* @__PURE__ */ React.createElement("sphereGeometry", { args: [r, 16, 12] }), /* @__PURE__ */ React.createElement("meshBasicMaterial", { color: SOURCE_COLOR, toneMapped: false })), /* @__PURE__ */ React.createElement(Arrow, { origin: [0, 0, 0], direction: polarizationOf(component), length: domain.extent * 0.1, color: SOURCE_COLOR }));
}
function DirectedWave({ object, component, domain, selected }) {
  const tfsf = value(component, "injection", "soft") === "tfsf";
  return /* @__PURE__ */ React.createElement("group", null, /* @__PURE__ */ React.createElement(Arrow, { origin: [0, 0, 0], direction: vec3(component, "direction", [0, 0, 1]), length: domain.extent * 0.15, color: SOURCE_COLOR }), /* @__PURE__ */ React.createElement(Arrow, { origin: [0, 0, 0], direction: vec3(component, "polarization", [1, 0, 0]), length: domain.extent * 0.06, color: SOURCE_COLOR }), tfsf && /* @__PURE__ */ React.createElement(
    DashedBox,
    {
      object,
      min: vec3(component, "tfsf_min", [-0.5, -0.5, -0.5]),
      max: vec3(component, "tfsf_max", [0.5, 0.5, 0.5]),
      color: SOURCE_COLOR,
      dash: domain.extent * 0.015,
      opacity: selected ? 1 : 0.6
    }
  ));
}
function PointMonitor({ domain }) {
  const s = domain.extent * 0.015;
  const segments = [
    [-s, 0, 0],
    [s, 0, 0],
    [0, -s, 0],
    [0, s, 0],
    [0, 0, -s],
    [0, 0, s]
  ];
  return /* @__PURE__ */ React.createElement(Line, { points: segments, segments: true, color: MONITOR_COLOR, lineWidth: 2 });
}
function PlaneMonitor({ object, component, domain }) {
  const axis = AXIS_INDEX[String(value(component, "axis", "z"))] ?? 2;
  const position = Number(value(component, "position", 0));
  const corners = useMemo(() => {
    const center = [0, 1, 2].map((a) => (domain.min[a] + domain.max[a]) / 2);
    center[axis] = position;
    const size = [0, 1, 2].map((a) => domain.max[a] - domain.min[a]);
    size[axis] = 0;
    return { center, size };
  }, [axis, position, domain]);
  const m = worldToLocal(object);
  const local = new THREE.Vector3(...corners.center).applyMatrix4(m).toArray();
  return /* @__PURE__ */ React.createElement(
    PlaneRect,
    {
      center: local,
      size: corners.size,
      color: MONITOR_COLOR,
      dashed: true,
      dash: domain.extent * 0.012,
      fillOpacity: value(component, "compute_flux", false) ? 0.12 : 0.04
    }
  );
}
function FinitePlaneMonitor({ component, domain }) {
  return /* @__PURE__ */ React.createElement(
    PlaneRect,
    {
      center: [0, 0, 0],
      size: vec3(component, "size", [1, 1, 0]),
      color: MONITOR_COLOR,
      dashed: true,
      dash: domain.extent * 0.012,
      fillOpacity: value(component, "compute_flux", false) ? 0.12 : 0.04
    }
  );
}
function ClosedSurfaceMonitor({ component, domain }) {
  const size = vec3(component, "size", [1, 1, 1]);
  const half = size.map((s) => s / 2);
  const segments = useMemo(() => boxEdges([-half[0], -half[1], -half[2]], half), [...half]);
  return /* @__PURE__ */ React.createElement(Line, { points: segments, segments: true, color: MONITOR_COLOR, lineWidth: 1.25, dashed: true, dashSize: domain.extent * 0.012, gapSize: domain.extent * 8e-3 });
}
function PmlBox({ object, component, domain }) {
  const inset = value(component, "pml_inset", null);
  if (!Array.isArray(inset) || inset.length !== 6 || inset.every((t) => !(t > 0))) return null;
  const min = vec3(component, "min_bound", domain.min);
  const max = vec3(component, "max_bound", domain.max);
  const innerMin = [0, 1, 2].map((a) => min[a] + inset[2 * a]);
  const innerMax = [0, 1, 2].map((a) => max[a] - inset[2 * a + 1]);
  if ([0, 1, 2].some((a) => innerMin[a] >= innerMax[a])) return null;
  return /* @__PURE__ */ React.createElement(DashedBox, { object, min: innerMin, max: innerMax, color: PML_COLOR, dash: domain.extent * 0.015, opacity: 0.8 });
}
var SOURCE_AND_MONITOR_VISUALS = [
  { component: "PointDipoleSource", render: ({ component, domain }) => /* @__PURE__ */ React.createElement(PointDipole, { component, domain }) },
  { component: "PlaneWaveSource", render: (a) => /* @__PURE__ */ React.createElement(DirectedWave, { ...a }) },
  { component: "GaussianBeamSource", render: (a) => /* @__PURE__ */ React.createElement(DirectedWave, { ...a }) },
  { component: "ModeSource", render: (a) => /* @__PURE__ */ React.createElement(ModePlane, { ...a, color: SOURCE_COLOR, dashed: false }) },
  { component: "PointMonitor", render: ({ domain }) => /* @__PURE__ */ React.createElement(PointMonitor, { domain }) },
  { component: "PlaneMonitor", render: (a) => /* @__PURE__ */ React.createElement(PlaneMonitor, { ...a }) },
  { component: "FinitePlaneMonitor", render: (a) => /* @__PURE__ */ React.createElement(FinitePlaneMonitor, { ...a }) },
  { component: "ClosedSurfaceMonitor", render: (a) => /* @__PURE__ */ React.createElement(ClosedSurfaceMonitor, { ...a }) },
  { component: "ModeMonitor", render: (a) => /* @__PURE__ */ React.createElement(ModePlane, { ...a, color: MONITOR_COLOR, dashed: true }) }
];
function registerMaxwellVisuals(host) {
  for (const visual of SOURCE_AND_MONITOR_VISUALS) {
    let MaxwellVisual = function({ object, selected }) {
      const domain = useDomain(host);
      const component = findComponent(object, visual.component);
      if (!component || object.visible === false) return null;
      return /* @__PURE__ */ React.createElement(React.Fragment, null, visual.render({ host, object, component, domain, selected }));
    };
    host.registerVisualizer({
      id: `witwin.maxwell.${visual.component}`,
      priority: 80,
      skipStandardGeometry: true,
      match: (object) => !!findComponent(object, visual.component),
      component: MaxwellVisual
    });
  }
  function MaxwellPml({ object }) {
    const domain = useDomain(host);
    const component = findComponent(object, "MaxwellSolver");
    return component && object.visible !== false ? /* @__PURE__ */ React.createElement(PmlBox, { object, component, domain }) : null;
  }
  host.registerGizmo({
    id: "witwin.maxwell.pml",
    priority: 80,
    match: (object) => !!findComponent(object, "MaxwellSolver"),
    component: MaxwellPml
  });
}

// src/viewport.ts
var sdkVersion = "1.0.0";
function activate(host) {
  registerMaxwellVisuals(host);
}
export {
  activate,
  sdkVersion
};
