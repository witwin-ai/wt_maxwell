import { React } from './runtime';

/*
 * Field values a handle drag shows before the scene has them. The handles
 * are a gizmo (they need the viewport tool) and the look is a visualizer,
 * so they share this store, keyed by object id. A drag writes here on
 * every move; the release commits through the scene service and clears
 * the entry once the writes resolve, so the shape does not flash back to
 * its old size for a round trip.
 *
 * Keys are component field names, plus OFFSET_KEY: a scene-space shift of
 * the object's anchor while a resize moves its centre.
 */

export const OFFSET_KEY = '__anchor_offset';

type Values = Record<string, unknown>;

const previews = new Map<string, Values>();
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

export function setPreview(objectId: string, values: Values | null): void {
  if (values) previews.set(objectId, values);
  else previews.delete(objectId);
  emit();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The drag preview of one object, or null. Same entry gives the same object. */
export function usePreview(objectId: string): Values | null {
  return React.useSyncExternalStore(subscribe, () => previews.get(objectId) ?? null);
}

/** `component` with the previewed field values laid over its own. */
export function withPreview(component: any, preview: Values | null): any {
  if (!preview || !component) return component;
  return { ...component, values: { ...component.values, ...preview } };
}
