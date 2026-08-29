# ADR-004 — Deployment platform and organization-selected region

Status: **accepted engineering direction; owner input required**

Date: 2026-08-29

Decision owners: unassigned (`OI-001`, `OI-002`, `OI-003`, `OI-004`)

Reviewers: security and operations, unassigned

## Context

The production specification freezes the runtime topology as OCI containers on managed Kubernetes with managed Postgres, Redis, S3-compatible object storage, a private registry, secret manager, WAF/ingress, and an OpenTelemetry Collector. The organization—not an implementer—must select the provider/account, data region, domains, network ownership, and identity ownership.

## Decision

The engineering topology above is retained without modification. No cloud provider, account, subscription/project, region, disaster-recovery region, domain, network boundary, or named owner is selected by WP-00.

Until all linked inputs are accepted:

- production deployment and traffic are disabled (`DF-001`);
- production map/model/storage/background-job routes that depend on residency or network decisions remain disabled;
- local and CI scaffolding may use isolated development equivalents only and cannot be described as production evidence.

## Required owner evidence

- approved provider and account/project identifiers;
- primary/DR regions and data-residency constraints;
- domains, ingress exposure, certificates, WAF, and DNS ownership;
- namespace, service-account, workload-identity, egress, proxy, and private-endpoint ownership;
- architecture/security review reference and decision date.

## Consequences

WP-01 can create provider-neutral manifests and local Compose equivalents. WP-14 cannot create or promote a production environment until this record is amended by the accountable owners. A later provider selection must not weaken the fixed network, isolation, encryption, observability, recovery, or release gates.

## Rollback

Before production, rollback is removal of any unapproved environment configuration. After approval, provider/region changes require a superseding ADR and migration/recovery evidence; this record is never silently edited to imply historical approval.
