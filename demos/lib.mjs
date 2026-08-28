import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
export const OUT = join(ROOT, 'out');

// Minimal CSV reader for our own well-formed files (no quoted fields).
export function readCsv(relPath) {
  const raw = readFileSync(join(ROOT, relPath), 'utf8').trim();
  const [header, ...lines] = raw.split('\n');
  const cols = header.split(',');
  return lines.map((line) => {
    const cells = line.split(',');
    const row = {};
    cols.forEach((c, i) => {
      const v = cells[i];
      row[c] = v !== '' && !Number.isNaN(Number(v)) ? Number(v) : v;
    });
    return row;
  });
}

export function savePng(name, buffer) {
  mkdirSync(OUT, { recursive: true });
  const file = join(OUT, name);
  writeFileSync(file, buffer);
  console.log(`saved ${file} (${(buffer.length / 1024).toFixed(0)} KB)`);
  return file;
}

export function sumBy(rows, keyField, valueField) {
  const acc = new Map();
  for (const r of rows) {
    acc.set(r[keyField], (acc.get(r[keyField]) ?? 0) + r[valueField]);
  }
  return [...acc.entries()].map(([k, v]) => ({ [keyField]: k, [valueField]: v }));
}
