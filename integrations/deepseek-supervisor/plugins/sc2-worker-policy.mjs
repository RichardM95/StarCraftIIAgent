// Named SC2 profile entry point. The shared policy owns guard ordering; this
// file selects that implementation through the task contract profile field.
import {apply as applyBase, resolveWithin} from './task-policy.mjs';

export const name = 'sc2-worker-policy';
export const inject = ['tools', 'agents', 'compaction', 'sessionPersistence'];
export {resolveWithin};
export function apply(ctx, config) { applyBase(ctx, config); }
