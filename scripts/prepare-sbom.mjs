import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const legacyLock = await readFile(path.join(repositoryRoot, "package-lock.json"));
const legacyHash = createHash("sha256").update(legacyLock).digest("hex");

assert.equal(
  legacyHash,
  "5222d716a8480a61d417ec2efef1d5da44741f1c3d2a12ea87a778e3339650ff",
  "The frozen legacy POC package-lock.json changed",
);
await readFile(path.join(repositoryRoot, "pnpm-lock.yaml"));
await mkdir(path.join(repositoryRoot, "artifacts", "sbom"), { recursive: true });
