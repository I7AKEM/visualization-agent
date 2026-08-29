# ADR-008 — Identity provider and policy ownership

Status: **input required; feature disabled**

Date: 2026-08-29

Decision owner: identity owner, unassigned (`OI-005`)

Reviewers: security and application-policy reviewers, unassigned

## Context

The fixed identity pattern is OIDC Authorization Code with PKCE, a short-lived server session, secure/HTTP-only/SameSite cookies, CSRF/origin controls, session rotation, and server-derived tenant/workspace/user authority. The organization must select the IdP and authoritative claims/policy ownership.

## Decision

No IdP vendor, tenant, issuer, client registration, claim names, group mapping, session lifetime, MFA rule, conditional-access rule, or named policy owner is chosen by WP-00.

Production authentication, publication/sharing, and delegated external-agent flows remain disabled (`DF-002`). Client-supplied tenant, user, role, approval, or history is never accepted as authority.

## Required owner evidence

- OIDC issuer/metadata and environment-specific client registrations;
- redirect/logout URLs, key rotation, outage, and break-glass policy;
- stable subject/tenant/workspace/role claim mapping and membership source;
- MFA/conditional-access/session/revocation requirements;
- workload identity and delegated external-agent token audience/scope/expiry policy;
- named identity owner, application policy owner, reviewer, and support/escalation path.

Secret values are not recorded in this ADR or committed configuration.

## Consequences

WP-03 may implement provider-neutral interfaces and denial behavior only after its dependencies. Production readiness must fail when required identity configuration is absent. A development-only fake identity cannot be promoted or used as authorization evidence.

## Rollback

Disable affected client registrations and delegated-token issuance, revoke sessions as policy requires, and route user traffic to an unavailable/maintenance state. Never fall back to anonymous or client-asserted identity.
