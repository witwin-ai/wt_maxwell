import type { ViewportHost } from './sdk/types';
import { registerMaxwellVisuals } from './visuals';

export const sdkVersion = '1.0.0';

export function activate(host: ViewportHost): void {
  registerMaxwellVisuals(host);
}
