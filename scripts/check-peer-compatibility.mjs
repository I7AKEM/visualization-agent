import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

import semver from "semver";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const webRoot = path.join(repositoryRoot, "apps", "web");
const webManifest = JSON.parse(readFileSync(path.join(webRoot, "package.json"), "utf8"));
const requireFromWeb = createRequire(path.join(webRoot, "package.json"));

const expected = Object.freeze({
  "@ai-sdk/react": "4.0.86",
  "@ant-design/x": "2.8.0",
  ai: "7.0.83",
  antd: "6.4.5",
  next: "16.3.3",
  react: "19.2.8",
  "react-dom": "19.2.8",
  zod: "4.1.8",
});

function installedManifest(packageName) {
  let directory = path.dirname(requireFromWeb.resolve(packageName));
  for (;;) {
    const candidate = path.join(directory, "package.json");
    if (existsSync(candidate)) {
      const manifest = JSON.parse(readFileSync(candidate, "utf8"));
      if (manifest.name === packageName) return manifest;
    }
    const parent = path.dirname(directory);
    assert.notEqual(parent, directory, `Could not locate installed manifest for ${packageName}`);
    directory = parent;
  }
}

const installed = Object.fromEntries(
  Object.entries(expected).map(([name, version]) => {
    assert.equal(webManifest.dependencies[name], version, `${name} must be directly and exactly pinned`);
    const manifest = installedManifest(name);
    assert.equal(manifest.version, version, `${name} installed version drifted`);
    return [name, manifest];
  }),
);

function assertPeer(consumer, dependency) {
  const range = installed[consumer].peerDependencies?.[dependency];
  assert.ok(range, `${consumer} must declare a ${dependency} peer`);
  assert.ok(
    semver.satisfies(installed[dependency].version, range, { includePrerelease: false }),
    `${consumer} peer ${dependency}@${range} rejects ${installed[dependency].version}`,
  );
}

assertPeer("next", "react");
assertPeer("next", "react-dom");
assertPeer("react-dom", "react");
assertPeer("@ai-sdk/react", "react");
assertPeer("@ant-design/x", "antd");
assertPeer("@ant-design/x", "react");
assertPeer("@ant-design/x", "react-dom");
assertPeer("antd", "react");
assertPeer("antd", "react-dom");

assert.equal(installed["@ai-sdk/react"].dependencies?.ai, expected.ai);
assert.ok(semver.satisfies(process.version, installed.ai.engines.node));
assert.ok(semver.satisfies(process.version, installed.next.engines.node));

console.log("installed Node/React/AI SDK/Ant Design peer graph verified");
