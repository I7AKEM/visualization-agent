// Self-hosted chart rendering service — the "private deployment" that replaces
// AntV's public cloud endpoint (antv-studio.alipay.com). mcp-server-chart POSTs a
// chart spec here (VIS_REQUEST_SERVER) and gets back { success, resultObj: <url> }.
// Nothing leaves the machine — required posture for government data.
import http from 'node:http';
import { readFileSync, mkdirSync, writeFileSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { render } from '@antv/gpt-vis-ssr';
import { OUT } from './lib.mjs';

const PORT = Number(process.env.PORT || 3100);
let seq = 0;

export function startRenderServer(port = PORT) {
  mkdirSync(OUT, { recursive: true });
  seq = readdirSync(OUT).filter((f) => f.startsWith('mcp-')).length;
  const server = http.createServer(async (req, res) => {
    try {
      if (req.method === 'GET' && req.url.startsWith('/images/')) {
        const file = join(OUT, req.url.slice('/images/'.length));
        if (!existsSync(file)) { res.writeHead(404); return res.end(); }
        res.writeHead(200, { 'content-type': 'image/png' });
        return res.end(readFileSync(file));
      }
      if (req.method === 'POST') {
        let body = '';
        for await (const chunk of req) body += chunk;
        const { source, ...options } = JSON.parse(body);
        const vis = await render(options);
        const name = `mcp-${String(++seq).padStart(2, '0')}-${options.type}.png`;
        writeFileSync(join(OUT, name), vis.toBuffer());
        vis.destroy();
        res.writeHead(200, { 'content-type': 'application/json' });
        return res.end(JSON.stringify({
          success: true,
          resultObj: `http://127.0.0.1:${port}/images/${name}`,
        }));
      }
      res.writeHead(405); res.end();
    } catch (err) {
      res.writeHead(200, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ success: false, errorMessage: String(err?.message || err) }));
    }
  });
  return new Promise((resolve) => server.listen(port, '127.0.0.1', () => {
    console.log(`render server on http://127.0.0.1:${port}`);
    resolve(server);
  }));
}

// pathToFileURL handles percent-encoding (spaces etc.) — a plain
// `file://${process.argv[1]}` comparison silently fails in paths with spaces.
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) startRenderServer();
