# WP-01 foundation evidence

- `node-dependencies.yaml` records exact runtime, package-manager, production
  dependency, and test-tool selections from official release/registry metadata.
- `python-dependencies.yaml` records the exact Python 3.12, uv, Pydantic stack,
  build, test, audit, and SBOM selections.
- `node-compatibility.yaml` and `python-compatibility.yaml` record the passing
  exact Pydantic AI 2.36.0 to AI SDK 7 text, custom-data, and deferred-approval
  cross-runtime gates. No adapter or fallback was introduced.
- `version-license-sbom-manifest.yaml` binds the exact locks, direct/tool
  licenses, normalized CycloneDX generation, and POC-preservation hashes.
- `ci-security-foundation.yaml` records the fail-closed CI, schema, security,
  and reproducibility controls and their local-versus-CI execution boundary.
- `runtime-smoke.yaml` records the built Next.js standalone startup, page and
  client-asset HTTP probes, clean shutdown, and import-only Python boundaries.
- `runtime/` commits the exact page and asset responses, startup/shutdown log,
  machine-readable trace, original failure/retest record, and checksum manifest.
- `hosted-ci.yaml` preserves the four immutable failed old-handoff run IDs, exact
  causes, partial artifacts, owner-setting blockers, and the exact-SHA rerun rule
  without relabeling any failed run or local result as green hosted evidence.
- `ownership-scope.yaml` reconciles primary WP-01 paths, explicitly authorized
  empty scaffolds, test/schema/CI policy paths, and the four excluded integration paths.
- `fixtures/legacy-poc/` preserves the original POC dependency manifest while
  the original npm lock remains frozen at the repository root.
