// Demo 3 — drive @antv/mcp-server-chart over the real MCP protocol (stdio),
// exactly as Claude Desktop / Claude Code would, but with rendering redirected to
// the local self-hosted server (VIS_REQUEST_SERVER) so no data leaves the machine.
import { spawn } from 'node:child_process';
import { join } from 'node:path';
import { startRenderServer } from './render-server.mjs';
import { ROOT, readCsv, sumBy } from './lib.mjs';

const PORT = 3100;
const server = await startRenderServer(PORT);

const child = spawn('node', [join(ROOT, 'node_modules/@antv/mcp-server-chart/build/index.js')], {
  env: { ...process.env, VIS_REQUEST_SERVER: `http://127.0.0.1:${PORT}` },
  stdio: ['pipe', 'pipe', 'inherit'],
});

let nextId = 1;
const pending = new Map();
let buf = '';
child.stdout.on('data', (d) => {
  buf += d.toString();
  let idx;
  while ((idx = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, idx).trim();
    buf = buf.slice(idx + 1);
    if (!line) continue;
    const msg = JSON.parse(line);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    }
  }
});

function request(method, params) {
  const id = nextId++;
  const p = new Promise((resolve) => pending.set(id, resolve));
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  return p;
}
function notify(method, params) {
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method, params }) + '\n');
}

// --- MCP handshake ----------------------------------------------------------
const init = await request('initialize', {
  protocolVersion: '2025-03-26',
  capabilities: {},
  clientInfo: { name: 'insightor-e2e-test', version: '0.1.0' },
});
console.log(`server: ${init.result.serverInfo.name} v${init.result.serverInfo.version}`);
notify('notifications/initialized', {});

const tools = await request('tools/list', {});
const names = tools.result.tools.map((t) => t.name);
console.log(`tools exposed: ${names.length}`);
console.log(names.join(', '));

// --- call two chart tools with Arabic government data -----------------------
const rows = readCsv('data/monthly_transactions.csv');
const totals = sumBy(rows, 'region', 'transactions')
  .sort((a, b) => b.transactions - a.transactions)
  .map((r) => ({ category: r.region, value: r.transactions }));

const call1 = await request('tools/call', {
  name: 'generate_column_chart',
  arguments: {
    data: totals,
    title: 'إجمالي المعاملات حسب المنطقة (عبر MCP)',
    axisXTitle: 'المنطقة',
    axisYTitle: 'عدد المعاملات',
  },
});
console.log('\ngenerate_column_chart →', JSON.stringify(call1.result?.content?.[0] ?? call1, null, 2));

const call2 = await request('tools/call', {
  name: 'generate_line_chart',
  arguments: {
    data: rows
      .filter((r) => r.region === 'مكة المكرمة')
      .map((r) => ({ time: r.month, value: r.transactions })),
    title: 'مكة المكرمة: أثر موسم الحج على المعاملات (عبر MCP)',
    axisXTitle: 'الشهر',
    axisYTitle: 'عدد المعاملات',
  },
});
console.log('\ngenerate_line_chart →', JSON.stringify(call2.result?.content?.[0] ?? call2, null, 2));

child.kill();
server.close();
console.log('\ndemo 3 done');
