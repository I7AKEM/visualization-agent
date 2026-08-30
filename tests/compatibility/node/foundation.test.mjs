import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");
const read = (relativePath) => readFileSync(path.join(repositoryRoot, relativePath));
const json = (relativePath) => JSON.parse(read(relativePath).toString("utf8"));
const sha256 = (relativePath) => createHash("sha256").update(read(relativePath)).digest("hex");

const versions = Object.freeze({
  "@ai-sdk/react": "4.0.86",
  "@ant-design/x": "2.8.0",
  ai: "7.0.83",
  antd: "6.4.5",
  next: "16.3.3",
  react: "19.2.8",
  "react-dom": "19.2.8",
  zod: "4.1.8",
});

test("runtime and production workspace pins are exact", () => {
  const root = json("package.json");
  assert.equal(root.private, true);
  assert.equal(root.engines.node, "24.20.0");
  assert.equal(root.engines.pnpm, "10.34.5");
  assert.equal(root.packageManager, "pnpm@10.34.5");
  assert.deepEqual(root.workspaces, ["apps/*", "packages/*"]);
  assert.equal(read(".node-version").toString("utf8").trim(), "24.20.0");
  assert.equal(read(".nvmrc").toString("utf8").trim(), "24.20.0");

  const workspace = read("pnpm-workspace.yaml").toString("utf8");
  assert.match(workspace, /- apps\/\*/u);
  assert.match(workspace, /- packages\/\*/u);

  const web = json("apps/web/package.json");
  for (const [name, version] of Object.entries(versions)) {
    assert.equal(web.dependencies[name], version, `${name} is not exactly pinned`);
  }
  assert.equal(web.scripts.build, "next build && node scripts/prepare-standalone.mjs");
  assert.equal(web.scripts.start, "node .next/standalone/apps/web/server.js");
  assert.ok(existsSync(path.join(repositoryRoot, "apps/web/scripts/prepare-standalone.mjs")));
});

test("legacy POC npm artifacts remain frozen while pnpm owns production", () => {
  assert.equal(
    sha256("package-lock.json"),
    "5222d716a8480a61d417ec2efef1d5da44741f1c3d2a12ea87a778e3339650ff",
  );
  assert.equal(
    sha256("docs/evidence/wp-01/fixtures/legacy-poc/package.json"),
    "a2eabe04488069f70642240e8ec35f15652797875c3fd6d158fb74effabee404",
  );
  assert.ok(existsSync(path.join(repositoryRoot, "pnpm-lock.yaml")), "production pnpm lock is missing");
  assert.equal(existsSync(path.join(repositoryRoot, "yarn.lock")), false);
  assert.equal(existsSync(path.join(repositoryRoot, "bun.lock")), false);
  assert.equal(existsSync(path.join(repositoryRoot, "bun.lockb")), false);
});

test("contract and renderer packages remain empty scaffolds", () => {
  assert.deepEqual(json("packages/contracts_ts/package.json").exports, { ".": "./src/index.ts" });
  assert.match(read("packages/contracts_ts/src/index.ts").toString("utf8"), /^\/\/[^\n]+\nexport \{\};\n$/u);
  assert.match(read("packages/renderer_registry/src/index.ts").toString("utf8"), /^\/\/[^\n]+\nexport \{\};\n$/u);
});

test("protocol reference covers custom data and HITL terminal states", () => {
  const source = read("tests/compatibility/fixtures/ai-sdk-7-reference.sse").toString("utf8");
  const data = [...source.matchAll(/^data: (.+)$/gmu)].map((match) => match[1]);
  assert.equal(data.at(-1), "[DONE]");
  const chunks = data.slice(0, -1).map((value) => JSON.parse(value));
  assert.ok(chunks.some((part) => part.type === "data-run-status"));
  assert.ok(chunks.some((part) => part.type === "tool-approval-request"));
  assert.ok(chunks.some((part) => part.type === "tool-output-denied"));
  assert.equal(chunks.at(-1).type, "finish");
});
