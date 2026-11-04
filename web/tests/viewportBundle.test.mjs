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
