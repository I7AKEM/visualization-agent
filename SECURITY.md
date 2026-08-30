# Security policy

Do not report suspected secrets, cross-tenant access, unsafe execution, or data
disclosure in a public issue. Use the repository host's private vulnerability
reporting channel when it is enabled. If it is unavailable, use an existing
private channel to the repository owner and omit exploit payloads until the
organization assigns the security contact tracked by WP-00; this document does
not invent an address or response-time promise.

The production system is not enabled. All owner-dependent capabilities listed
in `docs/governance/disabled-features.yaml` remain disabled. A security report
does not authorize deployment, model access, production data access, or any
other capability.

For dependency reports, include the ecosystem, package and exact version,
advisory identifier, affected lockfile, and a minimal reproduction that contains
no real credential or private data. For application reports, include only
synthetic identifiers and redact tokens, rows, prompts, signed URLs, and internal
paths.
