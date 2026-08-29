# ADR-006 — Governed semantic source

Status: **input required; feature disabled**

Date: 2026-08-29

Decision owner: data owner, unassigned (`OI-010`)

Reviewers: domain steward and security, unassigned

## Context

The first governed integration must use the customer's existing approved semantic layer. If none exists, governed connectors are deferred rather than allowing the product or a model to invent metrics, joins, denominators, access policy, or stewardship.

## Decision

No semantic platform, warehouse, connector, metric catalog, business definition, relationship, or steward is selected. `governed_database_analysis_and_semantic_connectors` remains disabled (`DF-007`). The governed source/model catalog is empty by default.

Ad-hoc upload analysis may later use explicit typed `AdHocMeasure` definitions within its own work-package gates; it must not be mislabeled as governed semantics.

## Required owner evidence

- approved semantic source/platform and version;
- named metrics, dimensions, grains, relationships, filters, units, and owners;
- row/column policy and delegated-user/service access model;
- read-only connector, region, credentials/workload identity, timeout, quota, and audit owner;
- golden queries/results plus lineage, dry-run, revocation, and incident expectations.

## Consequences

WP-11 is blocked for source-dependent behavior. No generic SQL, filesystem, or shell tool may be offered as a workaround, and no model-generated metric can be promoted to a governed definition.

## Rollback

Disable the connector/semantic version, prevent new runs, and preserve immutable lineage for prior artifacts. Re-enablement requires the exact source/version and access-policy evidence to pass again.
