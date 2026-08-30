# Frozen legacy Node POC manifest

This `package.json` is a byte-for-byte copy of the repository-root manifest at
assignment base `0aca58ba95d5afd725834496e98d165b5b210a15`. Its SHA-256 is
`a2eabe04488069f70642240e8ec35f15652797875c3fd6d158fb74effabee404`.

The matching legacy POC lock remains at `/package-lock.json`, byte-for-byte,
with SHA-256
`5222d716a8480a61d417ec2efef1d5da44741f1c3d2a12ea87a778e3339650ff`.
It is intentionally not copied because keeping the original file at its
historical path makes drift detectable and preserves POC tooling assumptions.

Do not run `npm install` at the repository root and do not regenerate the npm
lock. pnpm 10.34.5 and `/pnpm-lock.yaml` are the sole production Node package
manager and lock. `tests/compatibility/node/foundation.test.mjs` enforces this
exception.
