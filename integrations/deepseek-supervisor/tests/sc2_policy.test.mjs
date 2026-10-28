import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {apply} from '../plugins/sc2-worker-policy.mjs';

async function fixture(body) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'sc2-worker-policy-'));
  const root = path.join(base, 'workspace');
  fs.mkdirSync(path.join(root, '.sc2-mcp'), {recursive: true});
  fs.writeFileSync(path.join(root, 'MapInfo'), 'opaque');
  const hooks = new Map();
  const dispose = [];
  let guard;
  const config = Object.fromEntries(['contract', 'audit', 'checkpoint', 'control', 'controlResult']
    .map(name => [name + 'Path', path.join(base, name + '.json')]));
  config.enhanced = true;
  fs.writeFileSync(config.contractPath, JSON.stringify({workspace: root, profile: 'sc2',
    allowed_files: ['.sc2-mcp/request.json', '.sc2-mcp/response.json', 'sample.SC2Map', 'MapInfo'], max_tool_calls: 20, goal: 'sc2 worker',
    constraints: [], acceptance: 'preserve component bytes'}));
  const agent = {id: 'task', ctx: {tools: {restrict() {}}}};
  apply({on(name, callback) {hooks.set(name, callback);}, tools: {guard(callback) {guard = callback;}},
    effect(callback) {dispose.push(callback());}}, config);
  hooks.get('agent/created')({agent, source: 'test'});
  try { await body({root, hooks, agent, attempt: (name, file, extra = {}) => guard({agent, name, arguments: {file_path: file, ...extra}})}); }
  finally { for (const callback of dispose.reverse()) await callback(); fs.rmSync(base, {recursive: true}); }
}

test('SC2 profile protects shell files and archives', async () => {
  await fixture(async ({root, attempt}) => {
    assert.match(attempt('write', 'MapInfo', {content: 'changed'}), /shell/);
    const archive = path.join('sample.SC2Map');
    fs.writeFileSync(path.join(root, archive), 'archive');
    assert.match(attempt('write', archive, {content: 'changed'}), /read-only/);
  });
});

test('SC2 profile validates bridge requests and blocks cliff operations', async () => {
  await fixture(async ({attempt}) => {
    const valid = JSON.stringify({protocol: 'sc2-worker-bridge/1', id: 'req-1', operation: 'capabilities', arguments: {}});
    assert.equal(attempt('write', '.sc2-mcp/request.json', {content: valid}), undefined);
    const cliff = JSON.stringify({protocol: 'sc2-worker-bridge/1', id: 'req-2', operation: 'cliff_write', arguments: {}});
    assert.match(attempt('write', '.sc2-mcp/request.json', {content: cliff}), /blocked/);
    assert.match(attempt('write', '.sc2-mcp/response.json', {content: '{}'}), /Only/);
  });
});
