// Common test containment and audit. Enhanced guidance is activated only after baseline.
import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

export const name = 'supervisor-task-policy';
export const inject = ['tools', 'agents', 'compaction', 'sessionPersistence'];

const SC2_BRIDGE_PROTOCOL = 'sc2-worker-bridge/1';
const SC2_BRIDGE_REQUEST = '.sc2-mcp/request.json';
const SC2_BRIDGE_OPERATIONS = new Set([
  'capabilities', 'workspace_inspect', 'map_shell_audit', 'dependencies_inspect',
  'catalog_inspect', 'catalog_search', 'script_inspect', 'trigger_inspect',
  'data_warnings_audit', 'data_warnings_plan', 'static_validate',
  'cliff_capability_status'
]);
const SC2_SHELL_FILES = new Set(['MapInfo', 'DocumentHeader', 'DocumentInfo', 'BankList.xml', 'ComponentList.SC2Components']);

export function resolveWithin(root, candidate) {
  const absolute = path.resolve(root, candidate);
  const relative = path.relative(root, absolute);
  if (relative.startsWith('..' + path.sep) || relative === '..' || path.isAbsolute(relative)
      || relative.includes(':')) throw new Error('Path is outside the task workspace');
  let current = root;
  for (const segment of relative.split(path.sep).filter(Boolean)) {
    current = path.join(current, segment);
    if (fs.existsSync(current)) {
      const stat = fs.lstatSync(current);
      if (stat.isSymbolicLink() || (stat.isFile() && stat.nlink > 1)) {
        throw new Error('Linked paths are not admitted');
      }
      const real = path.relative(root, fs.realpathSync(current));
      if (real.startsWith('..' + path.sep) || path.isAbsolute(real)) throw new Error('Resolved path escapes workspace');
    }
  }
  return absolute;
}

function relativeTo(root, absolute) {
  return path.relative(root, absolute).split(path.sep).join('/');
}

function bridgeRequest(args) {
  if (typeof args?.content !== 'string') return null;
  try { return JSON.parse(args.content); } catch { return null; }
}

function validateBridgeRequest(request) {
  if (request && ['cliff_write', 'ramp_write', 'apply', 'commit', 'rollback', 'export'].includes(request.operation)) {
    return 'Bridge operation is blocked: cliff/ramp writes and source apply operations are disabled';
  }
  if (!request || request.protocol !== SC2_BRIDGE_PROTOCOL || typeof request.id !== 'string'
      || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(request.id)
      || typeof request.operation !== 'string' || !SC2_BRIDGE_OPERATIONS.has(request.operation)) {
    return 'Bridge request has an invalid protocol, id, or operation; operation is blocked';
  }
  return undefined;
}

export function apply(ctx, config) {
  const contract = JSON.parse(fs.readFileSync(config.contractPath, 'utf8'));
  const root = fs.realpathSync(contract.workspace);
  const auditPath = config.auditPath;
  const enhanced = config.enhanced === true;
  const sc2Profile = contract.profile === 'sc2';
  const allowShellWrite = (contract.constraints || []).includes('allow_shell_write');
  const tools = ['read', 'write', 'edit', 'grep', 'glob'];
  const agents = new Map();
  const counts = new Map();
  const repeats = new Map();
  const failures = new Map();
  const stopped = new Set();
  const noTools = new Set();
  const checkpoint = fs.existsSync(config.checkpointPath)
    ? JSON.parse(fs.readFileSync(config.checkpointPath, 'utf8')) : {verified_operations: [], latest_directive: ''};
  let revision = fs.existsSync(config.controlPath) ? JSON.parse(fs.readFileSync(config.controlPath, 'utf8')).revision : 0;
  const handles = [];
  const audit = (record) => fs.appendFileSync(auditPath, JSON.stringify({time: Date.now(), ...record}) + '\n');
  ctx.on('agent/created', ({agent, source}) => {
    agents.set(agent.id, agent);
    agent.ctx.tools.restrict({allow: tools});
    audit({type: 'agent.created', session: agent.id, source, enhanced});
  });
  ctx.tools.guard((exec) => {
    const session = exec.agent?.id ?? 'unknown';
    const count = (counts.get(session) ?? 0) + 1;
    counts.set(session, count);
    let denial;
    let absolute;
    try {
      if (!tools.includes(exec.name)) throw new Error('Tool is outside the supported task capability set');
      if (enhanced && noTools.has(session)) throw new Error('Supervisor stopped tool activity for this turn');
      if (count > contract.max_tool_calls) {
        stopped.add(session);
        throw new Error('Task tool-call limit reached');
      }
      const args = exec.arguments;
      absolute = resolveWithin(root, args.file_path ?? args.path ?? '.');
      if (exec.name === 'glob' && (path.isAbsolute(args.pattern) || /(^|[\\/])\.\.([\\/]|$)/.test(args.pattern))) {
        throw new Error('Glob pattern escapes the workspace');
      }
      if (enhanced && ['write', 'edit'].includes(exec.name)) {
        const relative = path.relative(root, absolute).split(path.sep).join('/');
        if (!contract.allowed_files.includes(relative)) throw new Error('Write is outside the authorized file list');
        if (sc2Profile) {
          if (absolute !== root && fs.existsSync(absolute) && fs.statSync(absolute).isFile()
              && ['.sc2map', '.sc2mod'].includes(path.extname(absolute).toLowerCase())) {
            throw new Error('SC2Map/SC2Mod archive is read-only; use a component folder');
          }
          if (relative.startsWith('.sc2-mcp/') && relative !== SC2_BRIDGE_REQUEST) {
            throw new Error('Only .sc2-mcp/request.json may be written by the worker');
          }
          if (SC2_SHELL_FILES.has(relative) && !allowShellWrite) {
            throw new Error('Map shell files are protected; use a host transaction');
          }
          if (relative === SC2_BRIDGE_REQUEST) {
            if (exec.name !== 'write') throw new Error('Bridge requests must use the write tool');
            const bridgeError = validateBridgeRequest(bridgeRequest(args));
            if (bridgeError) throw new Error(bridgeError);
          }
          const content = typeof args.content === 'string' ? args.content : (typeof args.new === 'string' ? args.new : null);
          if (content !== null && (relative.toLowerCase().endsWith('.galaxy') || relative.endsWith('GameStrings.txt'))
              && (content.startsWith('\ufeff') || content.includes('\u0000'))) {
            throw new Error('Galaxy/GameStrings must remain UTF-8 without BOM or NUL');
          }
        }
      }
      const signature = JSON.stringify([exec.name, exec.arguments]);
      const previous = repeats.get(session);
      const repeatCount = previous?.signature === signature ? previous.count + 1 : 1;
      repeats.set(session, {signature, count: repeatCount});
      if (enhanced && repeatCount === 3) {
        checkpoint.progress_warning = 'Change approach: three identical tool calls made no new progress. Reuse existing evidence or explain the blocker; two more identical calls will stop this task.';
        audit({type: 'progress.warning', session, reason: 'repeated-identical-tools'});
      }
      if (enhanced && repeatCount >= 5) {
        stopped.add(session);
        throw new Error('Repeated identical operations; returning control to supervisor');
      }
    } catch (error) { denial = error.message; }
    audit({type: 'tool.attempt', session, name: exec.name, arguments: exec.arguments,
           path: absolute, denied: Boolean(denial), reason: denial});
    return denial;
  });
  ctx.on('tools/result', (exec, result) => {
    audit({type: 'tool.result', session: exec.agent?.id, name: exec.name,
           isError: result.isError});
    if (sc2Profile && !result.isError && ['write', 'edit'].includes(exec.name)) {
      const requested = exec.arguments?.file_path ?? exec.arguments?.path;
      if (requested) {
        try {
          const absolute = resolveWithin(root, requested);
          const relative = relativeTo(root, absolute);
          if (relative.toLowerCase().endsWith('.galaxy') || relative.endsWith('GameStrings.txt')) {
            const bytes = fs.readFileSync(absolute);
            if (bytes.includes(0) || (bytes[0] === 0xef && bytes[1] === 0xbb && bytes[2] === 0xbf)) {
              stopped.add(exec.agent?.id);
              checkpoint.sc2_violation = {path: relative, reason: 'post-write encoding guard detected BOM or NUL'};
              fs.writeFileSync(config.checkpointPath + '.tmp', JSON.stringify(checkpoint));
              fs.renameSync(config.checkpointPath + '.tmp', config.checkpointPath);
              audit({type: 'sc2.violation', path: relative, reason: checkpoint.sc2_violation.reason});
            }
          }
        } catch (error) {
          audit({type: 'sc2.post_write_check_failed', path: requested, reason: error.message});
        }
      }
    }
    if (!enhanced) return;
    const id = exec.agent?.id;
    const failed = result.isError === true ? (failures.get(id) ?? 0) + 1 : 0;
    failures.set(id, failed);
    if (failed === 3) {
      checkpoint.progress_warning = 'Change approach: three consecutive tool failures. Correct the arguments or report the blocker; two more failures will stop this task.';
      audit({type: 'progress.warning', session: id, reason: 'consecutive-tool-failures'});
    }
    if (failed >= 5) stopped.add(id);
    if (!result.isError) {
      checkpoint.verified_operations.push({tool: exec.name, path: exec.arguments.file_path ?? exec.arguments.path ?? '.',
        checked: 'tool completed; semantic acceptance remains the supervisor responsibility'});
      checkpoint.verified_operations = checkpoint.verified_operations.slice(-12);
      fs.writeFileSync(config.checkpointPath + '.tmp', JSON.stringify(checkpoint));
      fs.renameSync(config.checkpointPath + '.tmp', config.checkpointPath);
    }
  });
  ctx.on('agent/pre-step', async ({agent, messages}, next) => {
    const directive = [...messages].reverse().find(message => message.source.kind === 'user');
    if (enhanced && directive) {
      const text = directive.content.filter(block => block.type === 'text').map(block => block.text).join('\n');
      checkpoint.latest_directive = text.slice(0,2000);
      if (/^\s*(STOP(?:\s|[.!])|停止|停下)/i.test(text)) noTools.add(agent.id);
      else noTools.delete(agent.id);
      repeats.delete(agent.id);
      failures.delete(agent.id);
      delete checkpoint.progress_warning;
      fs.writeFileSync(config.checkpointPath + '.tmp', JSON.stringify(checkpoint));
      fs.renameSync(config.checkpointPath + '.tmp', config.checkpointPath);
    }
    if (stopped.has(agent.id)) return {kind: 'reject'};
    const decision = await next();
    if (!enhanced || decision.kind !== 'enter') return decision;
    const message = {
      id: randomUUID(), role: 'user', source: {kind: name, form: 'instructions'},
      content: [{type: 'text', text: 'Supervisor task contract (authoritative scope; worker cannot expand it):\n'
        + JSON.stringify({goal: contract.goal, allowed_files: contract.allowed_files,
          constraints: contract.constraints, acceptance: contract.acceptance, checkpoint})
        + '\nPreserve all existing code except the requested change. Report what was actually checked. '
        + 'The latest supervisor directive selects the current step and supersedes earlier steps; do not repeat completed work. '
        + 'If JSON is requested, return the requested JSON object only. Verify every numeric field against the supplied observations; '
        + 'structured output must agree with your actual reasoning. Do not claim tests ran when no test tool was available. '
        + 'If blocked, report evidence and stop.'
        + (sc2Profile ? '\nSC2 worker contract: edit component folders and preserve bytes, comments, IDs, order, encoding, and unrelated lines. '
          + 'Never simplify, compress, reorder, inline, or approximate Galaxy code. '
          + 'Use .sc2-mcp/request.json for bridge requests; wait for .sc2-mcp/response.json and cite its request id. '
          + 'The bridge is diagnostic/candidate-only: it cannot apply changes, write map shells, or generate cliffs/ramps. '
          + 'Static validation is not compiler, editor, runtime, or visual acceptance. Report each evidence level separately.' : '')}]
    };
    return {...decision, messages: [...decision.messages, message]};
  });
  // Supervisor-only file control; not exposed as a model tool or writable task file.
  let busy = false;
  const timer = setInterval(async () => {
    if (busy || !fs.existsSync(config.controlPath)) return;
    const command = JSON.parse(fs.readFileSync(config.controlPath, 'utf8'));
    if (command.revision <= revision) return;
    revision = command.revision;
    busy = true;
    try {
      let result;
      if (command.operation === 'resume') {
        const handle = await ctx.agents.resume({resumeSessionId: command.session_id,
          agentOptions: command.agent_options});
        handles.push(handle);
        result = {resumed: true};
        audit({type: 'session.resumed', session: command.session_id});
      } else {
        const agent = agents.get(command.session_id);
        if (!agent) throw new Error('Session is not live');
        if (command.operation === 'compact') {
          const compacted = await ctx.compaction.compactNow(agent, new AbortController().signal);
          result = {compacted: compacted !== null, result: compacted};
        } else if (command.operation === 'prompt') {
          const message = {id: randomUUID(), role: 'user', source: {kind: 'user'},
            content: [{type: 'text', text: command.prompt}]};
          await agent.followup(message);
          result = {messageId: message.id};
        } else throw new Error('Unsupported control operation');
      }
      fs.writeFileSync(config.controlResultPath + '.tmp', JSON.stringify({revision, ok: true, ...result}));
      fs.renameSync(config.controlResultPath + '.tmp', config.controlResultPath);
    } catch (error) {
      fs.writeFileSync(config.controlResultPath + '.tmp', JSON.stringify({revision, ok: false, error: error.message}));
      fs.renameSync(config.controlResultPath + '.tmp', config.controlResultPath);
    } finally { busy = false; }
  }, 100);
  ctx.effect(() => () => clearInterval(timer));
  ctx.effect(() => async () => { for (const handle of handles) await handle.dispose(); });
}
