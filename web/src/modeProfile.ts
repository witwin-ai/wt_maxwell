/**
 * Mode profiles as the backend publishes them on ModeSource / ModeMonitor
 * (components/mode_profiles.py has the contract), and painting one into a
 * canvas. Ported from @instamax/field-viewer.
 */
export interface ModeProfile {
  index: number;
  n_eff: number;
  /** TE-like energy share, 0..1. */
  te_fraction: number;
  /** Ascending in-plane coordinates relative to the plane centre, metres. */
  u: number[];
  v: number[];
  /** len(u) * len(v) signed samples, u fastest, max |value| = 1. */
  values: number[];
  label?: string;
  component?: string;
}

export function readModeProfiles(component: any): ModeProfile[] {
  const raw = component?.values?.mode_profiles;
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (p: any) => p && Array.isArray(p.u) && Array.isArray(p.v) && Array.isArray(p.values) && p.values.length === p.u.length * p.v.length,
  );
}

export function modeLabel(p: ModeProfile): string {
  return p.label || `Mode ${p.index}`;
}

// ColorBrewer RdBu reversed (negative blue, neutral middle), the same stops
// as wt_volume's 'rdbu' colormap so profiles and field slices read alike.
const RDBU = [
  '#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#f7f7f7',
  '#fddbc7', '#f4a582', '#d6604d', '#b2182b', '#67001f',
].map((hex) => {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}); /* allow-color: scientific diverging colormap */

function rdbu(t: number): number[] {
  const x = Math.min(Math.max(t, 0), 1) * (RDBU.length - 1);
  const i = Math.min(Math.floor(x), RDBU.length - 2);
  const f = x - i;
  return RDBU[i].map((a, k) => a + (RDBU[i + 1][k] - a) * f);
}

/** Lower grid index and weight of `x` on an ascending axis, clamped to the ends. */
function locate(axis: number[], x: number): [number, number] {
  const n = axis.length;
  if (x <= axis[0]) return [0, 0];
  if (x >= axis[n - 1]) return [n - 2, 1];
  let lo = 0;
  let hi = n - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (axis[mid] <= x) lo = mid;
    else hi = mid;
  }
  return [lo, (x - axis[lo]) / (axis[hi] - axis[lo])];
}

/**
 * Paints `p` into `canvas` at width x height, resampling the (possibly
 * non-uniform) grid bilinearly; -1..1 maps onto RdBu. Row 0 is the largest v,
 * as on screen; texture users flip it with `flipY`.
 */
export function paintModeProfile(canvas: HTMLCanvasElement, p: ModeProfile, width: number, height: number): void {
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  const img = ctx.createImageData(width, height);
  const nu = p.u.length;
  const [u0, u1] = [p.u[0], p.u[nu - 1]];
  const [v0, v1] = [p.v[0], p.v[p.v.length - 1]];
  const cols = Array.from({ length: width }, (_, x) => locate(p.u, u0 + ((x + 0.5) / width) * (u1 - u0)));
  for (let y = 0; y < height; y++) {
    const [j, tv] = locate(p.v, v1 - ((y + 0.5) / height) * (v1 - v0));
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
