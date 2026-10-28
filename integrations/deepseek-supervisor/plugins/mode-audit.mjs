// Measurement-only observer. No enhanced guidance or five-file-tool restriction.
import fs from 'node:fs';
import path from 'node:path';
export const name = 'mode-audit';
export const inject = ['tools', 'agents', 'agentPresets'];
export function apply(ctx, config) {
  let calls = 0;
  const root = path.resolve(config.workspace);
  const log = item => fs.appendFileSync(config.auditPath, JSON.stringify({time: Date.now(), ...item}) + '\n');
  ctx.on('agent/created', async ({agent}) => {
    // SDK creates a bare agent; the desktop normally performs this binding.
    // agent/created is serial and awaited before the first prompt is admitted.
    await ctx.agentPresets.select(agent, config.preset);
    log({type: 'agent.created', session: agent.id, expected_preset: config.preset,
      actual_preset: ctx.agentPresets.composedPreset(agent.ctx)});
  });
  ctx.tools.guard(exec => {
    let reason;
    if (++calls > 80) reason = 'Evaluation tool-call limit reached';
    const args = exec.arguments ?? {};
    const target = args.file_path ?? args.path;
    if (typeof target === 'string') {
      const relative = path.relative(root, path.resolve(root, target));
      if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
        reason = 'Evaluation file access is outside the disposable workspace';
      }
    }
    // A common evaluation boundary, not a claim of full shell confinement.
    if (['web_search', 'web_fetch', 'plugin_manager', 'subagent', 'subagent_fork', 'workflow'].includes(exec.name)) {
      reason = 'Networking, installing plugins and recursive delegation are outside this local comparison';
    }
    if (exec.name === 'pwsh' || exec.name === 'bash') {
      const command = String(args.command ?? '');
      if (/\.credentials|\.codex|\.dsh|api[_-]?key|access[_-]?token|Invoke-WebRequest|Invoke-RestMethod|\bcurl\b|\bwget\b|Remove-Item|\brmdir\b|\brm\s|Format-Volume|Set-ItemProperty|\.\.[\\/]/i.test(command)) {
        reason = 'Command is outside the local synthetic task boundary';
      }
    }
    log({type: 'tool.attempt', name: exec.name, arguments: args, denied: !!reason, reason});
    return reason;
  });
  ctx.on('tools/result', (exec, result) => log({type: 'tool.result', name: exec.name, isError: result.isError}));
  ctx.on('agent/pre-step', async (_event, next) => calls > 80 ? {kind: 'reject'} : next());
}
