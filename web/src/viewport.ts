import type { PluginDefinition } from '@witwin/host';
import { registerMaxwellVisuals } from './visuals';

export const sdkVersion = '2.0.0';

const plugin: PluginDefinition = {
  id: 'witwin.maxwell',
  inject: ['scene'],
  activate(host) {
    registerMaxwellVisuals(host);
  },
};

export default plugin;
