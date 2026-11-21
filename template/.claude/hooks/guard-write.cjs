#!/usr/bin/env node
// PreToolUse(Write): refuse to overwrite an existing CRLF file inside the repo. Write saves LF, so the
// whole file would show as changed, and a multi-line string literal can change meaning until the next
// checkout. New files, LF files and files outside the repo pass.
const fs = require('fs');
const path = require('path');

let input = '';
process.stdin.on('data', (c) => (input += c));
process.stdin.on('end', () => {
  try {
    const data = JSON.parse(input);
    const file = data?.tool_input?.file_path;
    if (!file) return;
    const root = path.resolve(process.env.CLAUDE_PROJECT_DIR || data.cwd || process.cwd());
    const target = path.resolve(file);
    const rel = path.relative(root, target);
    if (rel.startsWith('..') || path.isAbsolute(rel)) return;
    if (!fs.existsSync(target)) return;
    const head = fs.readFileSync(target).subarray(0, 64 * 1024);
    if (!head.includes('\r\n')) return;
    process.stdout.write(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: 'PreToolUse',
        permissionDecision: 'deny',
        permissionDecisionReason: `${rel} exists with CRLF line endings: change it with Edit, not Write (Write saves LF).`,
      },
    }));
  } catch {
    // A broken hook must never block work.
  }
});
