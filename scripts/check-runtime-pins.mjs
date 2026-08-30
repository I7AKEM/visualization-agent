import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const expected = Object.freeze({
  node: "24.20.0",
  pnpm: "10.34.5",
});

const manifest = JSON.parse(await readFile(new URL("../package.json", import.meta.url), "utf8"));
const nodeVersion = process.version.replace(/^v/u, "");

assert.equal(nodeVersion, expected.node, `Node ${expected.node} is required; found ${nodeVersion}`);
assert.deepEqual(manifest.engines, expected);
assert.equal(manifest.packageManager, `pnpm@${expected.pnpm}`);

const userAgent = process.env.npm_config_user_agent;
if (userAgent) {
  const pnpmMatch = /(?:^|\s)pnpm\/([^\s]+)/u.exec(userAgent);
  assert.ok(pnpmMatch, `Expected pnpm lifecycle user-agent; found ${userAgent}`);
  assert.equal(pnpmMatch[1], expected.pnpm, `pnpm ${expected.pnpm} is required`);
}

console.log(`runtime pins verified: node ${expected.node}, pnpm ${expected.pnpm}`);
