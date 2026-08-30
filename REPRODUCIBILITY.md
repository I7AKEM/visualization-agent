# Reproducibility contract

WP-01 pins Python, Node, pnpm, uv, application dependencies, CI actions, and
security/SBOM tools. Frozen installs must succeed before any build. The CI
rebuild gate copies the same source/input identity into two distinct clean temporary
workspaces. Each workspace independently performs frozen uv and pnpm installs, the
complete Next/TypeScript build, and all Python package builds. The artifact creator
then sorts inputs bytewise, normalizes ownership, modes and mtimes, sets the gzip
timestamp to zero, and emits per-file SHA-256 values. The gate compares the complete
generated-file manifests and normalized archives, not two archives of one build.

Run the local foundation check with:

```text
scripts/ci/reproducible_foundation.sh
```

`SOURCE_DATE_EPOCH` and a SHA-256 identity of all non-ignored source inputs are held
constant across the two builds. That input identity is also the explicit Next build
ID and the source for Next's build-only preview/server-action entropy. These public,
deterministic build inputs are used only by this reproducibility gate; they are not
production secrets or runtime configuration. Next also embeds the absolute checkout
path in several generated manifests, so the artifact and generated-tree comparison
canonicalize only that exact isolated workspace prefix to `/workspace`. No generated
file is omitted because of content differences. Thus `.next/BUILD_ID`, prerendered
HTML, standalone output, and static build-ID paths are compared instead of being
regenerated randomly or differing merely by temporary directory name. The workflow
also generates CycloneDX SBOMs from the exact locks. `scripts/ci/normalize_sbom.py` replaces
generator timestamps/UUIDs with lock-derived stable identities and sorts the
component/dependency graph before checksumming. Platform markers can make the
Python environment SBOM differ between operating systems; each recorded host
must still reproduce its normalized SBOM byte-for-byte. `artifacts/` is
ephemeral CI evidence and must not be treated as a source-controlled release.

This WP-01 check proves two independent clean builds and deterministic packaging of
the built/scaffolded foundation on one runner. Build workspaces are temporary and
are not uploaded; logs, generated manifests, checksums, and normalized archives are
the evidence artifacts. A cross-host container rebuild, signed
provenance/attestation, and promoted-image digest comparison remain WP-14 release
gates and are not claimed here.
