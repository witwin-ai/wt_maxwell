import { formatFrequency, value } from './emStyle';

/*
 * One-line summary of a source's temporal profile (the shared `st_*`
 * fields, components/source_time.py), for the label of a selected source.
 * Null when the source has no profile: `st_enabled` off on a source, or
 * `is_source` off on a ModePort.
 */
export function sourceTimeLabel(component: any, gate: 'st_enabled' | 'is_source' = 'st_enabled'): string | null {
  if (!value<boolean>(component, gate, gate === 'st_enabled')) return null;
  const kind = String(value(component, 'st_kind', 'cw'));
  const f0 = formatFrequency(Number(value(component, 'st_frequency', 1e9)));
  if (kind === 'gaussian_pulse') return `Gaussian pulse · ${f0} ± ${formatFrequency(Number(value(component, 'st_fwidth', 1e8)))}`;
  if (kind === 'ricker') return `Ricker · ${f0}`;
  return `CW · ${f0}`;
}
