import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const environment = { ...process.env };
delete environment.NODE_PATH;

const result = spawnSync(
  process.execPath,
  [
    path.join(repositoryRoot, "node_modules", "@cyclonedx", "cdxgen", "bin", "cdxgen.js"),
    "-t",
    "pnpm",
    "--no-recurse",
    "--no-install-deps",
    "--fail-on-error",
    "--spec-version",
    "1.6",
    "-o",
    path.join(repositoryRoot, "artifacts", "sbom", "node.cdx.json"),
    repositoryRoot,
  ],
  { cwd: repositoryRoot, env: environment, stdio: "inherit" },
);

if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
