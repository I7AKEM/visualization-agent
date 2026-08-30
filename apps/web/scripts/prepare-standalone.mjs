import { access, cp, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const standaloneRoot = path.join(appRoot, ".next", "standalone", "apps", "web");

async function copyRequired(source, destination) {
  await access(source);
  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination, { recursive: true, force: true });
}

async function copyOptional(source, destination) {
  try {
    await access(source);
  } catch {
    return;
  }

  await mkdir(path.dirname(destination), { recursive: true });
  await cp(source, destination, { recursive: true, force: true });
}

await copyRequired(
  path.join(appRoot, ".next", "static"),
  path.join(standaloneRoot, ".next", "static"),
);
await copyOptional(path.join(appRoot, "public"), path.join(standaloneRoot, "public"));

console.log("standalone runtime assets prepared");
