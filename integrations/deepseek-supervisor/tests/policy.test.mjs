import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {resolveWithin, apply} from '../plugins/task-policy.mjs';

test('reject traversal, alternate streams, and hard links; allow new nested files', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'supervisor-policy-'));
  try {
    assert.throws(() => resolveWithin(root, '../outside'));
    assert.throws(() => resolveWithin(root, 'file:stream'));
    assert.equal(resolveWithin(root, 'new/file.txt'), path.join(root, 'new/file.txt'));
    fs.writeFileSync(path.join(root, 'original'), 'value');
    fs.linkSync(path.join(root, 'original'), path.join(root, 'linked'));
    assert.throws(() => resolveWithin(root, 'linked'));
  } finally {
    fs.rmSync(root, {recursive: true});
  }
});

async function policyFixture(enhanced, body) {
  const base = fs.mkdtempSync(path.join(os.tmpdir(), 'supervisor-guards-'));
  const root = path.join(base, 'workspace');
  fs.mkdirSync(root);
  fs.writeFileSync(path.join(root, 'KEEP.txt'), 'original');
  const hooks = new Map();
  const dispose = [];
  let guard;
  const config = Object.fromEntries(['contract', 'audit', 'checkpoint', 'control', 'controlResult']
    .map(name => [name + 'Path', path.join(base, name + '.json')]));
  config.enhanced = enhanced;
  fs.writeFileSync(config.contractPath, JSON.stringify({workspace: root, allowed_files: ['allowed.txt'],
    max_tool_calls: 20, goal: 'bounded test', constraints: [], acceptance: 'preserve KEEP.txt'}));
  const agent = {id: 'task', ctx: {tools: {restrict() {}}}};
  apply({on(name, callback) {hooks.set(name, callback);}, tools: {guard(callback) {guard = callback;}},
    effect(callback) {dispose.push(callback());}}, config);
  hooks.get('agent/created')({agent, source: 'test'});
  const attempt = (name, file, extra = {}) => guard({agent, name, arguments: {file_path: file, ...extra}});
  try { await body({root, config, hooks, agent, attempt}); }
  finally { for (const callback of dispose.reverse()) await callback(); fs.rmSync(base, {recursive: true}); }
}

test('enhanced denies unauthorized write and outside read, audit distinguishes denied attempt from mutation', async () => {
  await policyFixture(true, async ({root, config, attempt}) => {
    assert.match(attempt('write', 'KEEP.txt', {content: 'changed'}), /authorized/);
    assert.match(attempt('read', '../contract.json'), /outside/);
    assert.equal(attempt('write', 'allowed.txt', {content: 'candidate'}), undefined);
    assert.equal(fs.readFileSync(path.join(root, 'KEEP.txt'), 'utf8'), 'original');
    const audit = fs.readFileSync(config.auditPath, 'utf8').trim().split('\n').map(JSON.parse);
    assert.equal(audit.filter(row => row.type === 'tool.attempt' && row.denied).length, 2);
  });
});

test('baseline shares outer containment but permits root-internal writes for comparison', async () => {
  await policyFixture(false, async ({attempt}) => {
    assert.equal(attempt('write', 'KEEP.txt', {content: 'candidate'}), undefined);
    assert.match(attempt('write', '../outside', {content: 'candidate'}), /outside/);
  });
});

test('STOP prevents tools and later authorized step can resume', async () => {
  await policyFixture(true, async ({hooks, agent, attempt}) => {
    const step = text => hooks.get('agent/pre-step')({agent, messages: [{id: text, source: {kind: 'user'},
      content: [{type: 'text', text}]}]}, async () => ({kind: 'enter', messages: []}));
    await step('STOP all tools.');
    assert.match(attempt('read', 'KEEP.txt'), /stopped/);
    await step('Read the existing file now.');
    assert.equal(attempt('read', 'KEEP.txt'), undefined);
  });
});

test('repeated identical calls stop after bounded attempts', async () => {
  await policyFixture(true, async ({hooks, agent, attempt}) => {
    for (let index = 0; index < 4; index++) assert.equal(attempt('read', 'KEEP.txt'), undefined);
    assert.match(attempt('read', 'KEEP.txt'), /Repeated/);
    const decision = await hooks.get('agent/pre-step')({agent, messages: []}, async () => ({kind: 'enter', messages: []}));
    assert.equal(decision.kind, 'reject');
  });
});

test('no-progress warning reaches the model before hard stop', async () => {
  await policyFixture(true, async ({hooks, agent, attempt}) => {
    for (let index = 0; index < 3; index++) attempt('read', 'KEEP.txt');
    const decision = await hooks.get('agent/pre-step')({agent, messages: []}, async () => ({kind: 'enter', messages: []}));
    assert.equal(decision.kind, 'enter');
    assert.ok(decision.messages.some(message => message.content.some(block =>
      block.text?.includes('Change approach'))), 'Model must receive a corrective instruction before rejection');
  });
});

test('five failed tool results stop progress', async () => {
  await policyFixture(true, async ({hooks, agent}) => {
    for (let index = 0; index < 5; index++) hooks.get('tools/result')({agent, name: 'read',
      arguments: {file_path: 'missing-' + index}}, {isError: true});
    const decision = await hooks.get('agent/pre-step')({agent, messages: []}, async () => ({kind: 'enter', messages: []}));
    assert.equal(decision.kind, 'reject');
  });
});
