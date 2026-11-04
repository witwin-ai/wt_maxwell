import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const pluginRoot = path.resolve(webRoot, '..');
const studioDir = process.env.WITWIN_STUDIO_DIR ?? path.resolve(pluginRoot, '..', '..', 'witwin-studio', 'studio');

test('manifest declares the viewport host bundle', () => {
  const manifest = fs.readFileSync(path.join(pluginRoot, 'witwin.toml'), 'utf8');
  assert.match(manifest, /\[contributes\.viewport\.host\]\s*\nentry = "viewport\.js"/);
  assert.match(manifest, /root = "web"/);
  assert.match(manifest, /frontend = true/);
  assert.match(manifest, /entry = "viewport\.js"\s*\nsdkVersion = "2\.0\.0"/);
});

test('bundle is an SDK 2 plugin definition', () => {
  const bundle = fs.readFileSync(path.join(webRoot, 'viewport.js'), 'utf8');
  assert.match(bundle, /sdkVersion = "2\.0\.0"/);
  assert.match(bundle, /id: "witwin\.maxwell"/);
  assert.match(bundle, /as default/);
  assert.doesNotMatch(bundle, /sceneWrites|export function activate/);
});

test('bundle is self-contained and registers every Maxwell visual', () => {
  const bundle = fs.readFileSync(path.join(webRoot, 'viewport.js'), 'utf8');
  assert.doesNotMatch(bundle, /^import /m);
  assert.doesNotMatch(bundle, /react\/jsx-runtime/);
  for (const name of ['PointDipoleSource', 'PlaneWaveSource', 'GaussianBeamSource', 'ModeSource', 'PointMonitor',
    'PlaneMonitor', 'FinitePlaneMonitor', 'ClosedSurfaceMonitor', 'ModeMonitor']) {
    assert.match(bundle, new RegExp(`component: "${name}"`));
  }
  assert.match(bundle, /witwin\.maxwell\.pml/);
});

test('readModeProfiles keeps only profiles whose values fill the u x v grid', async () => {
  const esbuild = createRequire(path.join(studioDir, 'package.json'))('esbuild');
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'wt-maxwell-')), 'modeProfile.mjs');
  await esbuild.build({ entryPoints: [path.join(webRoot, 'src/modeProfile.ts')], bundle: true, format: 'esm', outfile: out, logLevel: 'silent' });
  const { readModeProfiles, modeLabel } = await import(pathToFileURL(out).href);
  const good = { index: 0, n_eff: 2.4, te_fraction: 0.9, u: [0, 1], v: [0, 1], values: [1, 0, 0, -1] };
  const bad = { ...good, index: 1, values: [1, 0] };
  const profiles = readModeProfiles({ values: { mode_profiles: [good, bad, null] } });
  assert.deepEqual(profiles.map((p) => p.index), [0]);
  assert.deepEqual(readModeProfiles({ values: {} }), []);
  assert.equal(modeLabel(good), 'Mode 0');
  assert.equal(modeLabel({ ...good, label: 'TE0' }), 'TE0');
});

test('bundle registers ModePort, the solver, region and handle gizmos', () => {
  const bundle = fs.readFileSync(path.join(webRoot, 'viewport.js'), 'utf8');
  assert.match(bundle, /component: "ModePort"/);
  for (const id of ['witwin.maxwell.pml', 'witwin.maxwell.region', 'witwin.maxwell.handles']) assert.ok(bundle.includes(id), id);
  // Colours come from the stage palette; literals only as the fallback for old hosts.
  assert.match(bundle, /palette/);
});

/** Bundle one source module with stand-ins for the host singletons it reads at import time. */
async function importWithHost(entry) {
  const requireFromStudio = createRequire(path.join(studioDir, 'package.json'));
  const esbuild = requireFromStudio('esbuild');
  globalThis.__witwin = {
    react: requireFromStudio('react'),
    three: requireFromStudio('three'),
    fiber: { useFrame: () => {}, useThree: () => ({}) },
    drei: { Html: () => null, Line: () => null, Text: () => null },
  };
  const out = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'wt-maxwell-')), `${path.basename(entry)}.mjs`);
  await esbuild.build({
    entryPoints: [path.join(webRoot, entry)], bundle: true, format: 'esm', outfile: out, logLevel: 'silent',
    jsx: 'transform', jsxFactory: 'React.createElement', jsxFragment: 'React.Fragment',
  });
  return import(pathToFileURL(out).href);
}

test('dragBox moves one face, both with Alt, snaps with Ctrl and keeps a minimum size', async () => {
  const { dragBox } = await importWithHost('src/handles.tsx');
  const start = { min: [-1, -1, 0], max: [1, 1, 0] };
  const plain = { snap: false, symmetric: false };
  assert.deepEqual(dragBox(start, 0, 1, 0.5, plain, 0, 0.01), { min: [-1, -1, 0], max: [1.5, 1, 0] });
  assert.deepEqual(dragBox(start, 0, 1, 0.5, { snap: false, symmetric: true }, 0, 0.01), { min: [-1.5, -1, 0], max: [1.5, 1, 0] });
  assert.deepEqual(dragBox(start, 1, -1, 0.26, { snap: true, symmetric: false }, 0.1, 0.01).min, [-1, -0.7, 0]);
  const collapsed = dragBox(start, 0, 1, -5, plain, 0, 0.2);
  assert.ok(Math.abs(collapsed.max[0] - collapsed.min[0] - 0.2) < 1e-12);
});

test('faceKinds and cellSize follow adapter/grid.py', async () => {
  const { faceKinds, cellSize } = await importWithHost('src/boundary.tsx');
  const solver = (values) => ({ values });
  assert.deepEqual(faceKinds(solver({ mode: 'global', kind: 'pec' })), Array(6).fill('pec'));
  assert.deepEqual(faceKinds(solver({ mode: 'per_axis', x: 'periodic', y: 'pml', z: 'pmc' })), ['periodic', 'periodic', 'pml', 'pml', 'pmc', 'pmc']);
  assert.deepEqual(faceKinds(solver({ mode: 'per_face', x_low: 'pml', x_high: 'pec', y_low: 'none', y_high: 'none', z_low: 'bloch', z_high: 'bloch' })),
    ['pml', 'pec', 'none', 'none', 'bloch', 'bloch']);
  // c / f_max / ppw, with ppw clamped to 4..20.
  assert.ok(Math.abs(cellSize(solver({ frequencies: [1e9, 2e9], ppw: '10' })) - 299792458 / 2e9 / 10) < 1e-12);
  assert.ok(Math.abs(cellSize(solver({ frequencies: [], frequency: 1e9, ppw: '40' })) - 299792458 / 1e9 / 20) < 1e-12);
});

test('labels name the temporal profile and units', async () => {
  const { sourceTimeLabel } = await importWithHost('src/sourceTime.ts');
  const { formatFrequency, formatLength, insideDomain } = await importWithHost('src/emStyle.ts');
  assert.equal(sourceTimeLabel({ values: { st_enabled: true, st_kind: 'gaussian_pulse', st_frequency: 1e9, st_fwidth: 2e8 } }), 'Gaussian pulse · 1 GHz ± 200 MHz');
  assert.equal(sourceTimeLabel({ values: { st_enabled: true, st_kind: 'cw', st_frequency: 2.4e9 } }), 'CW · 2.4 GHz');
  assert.equal(sourceTimeLabel({ values: { st_enabled: false } }), null);
  assert.equal(sourceTimeLabel({ values: { is_source: false } }, 'is_source'), null);
  assert.equal(formatFrequency(193.4e12), '193 THz');
  assert.equal(formatLength(0.0428), '4.28 cm');
  const domain = { min: [-1, -1, -1], max: [1, 1, 1], extent: 2, real: true };
  assert.equal(insideDomain(domain, [0, 0, 1]), true);
  assert.equal(insideDomain(domain, [0, 0, 1.5]), false);
});
