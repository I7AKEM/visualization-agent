# Local foundation environment

WP-01 deliberately defines an inert Compose project (`services: {}`). It is a
machine-readable refusal to start guessed databases, object stores, identity,
model, map, job, upload, publication, or export services before their owner
inputs and owning work packages are accepted.

Validate it with `docker compose -f infra/dev/compose.yaml config`. Adding a
service requires its owning work package, an immutable image digest, documented
network/volume/secret boundaries, and corresponding security and recovery
tests. Mutable image tags are forbidden.

`ci-tools.lock.json` is the review record for external GitHub Actions. Language
tools come only from the root pnpm/uv locks; CI must not install tools globally.
