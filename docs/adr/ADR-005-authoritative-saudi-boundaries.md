# ADR-005 — Authoritative Saudi boundary source

Status: **input required; feature disabled**

Date: 2026-08-29

Decision owner: data owner, unassigned (`OI-009`)

Reviewers: legal/licensing and geo-domain reviewers, unassigned

## Context

Release-1 boundary joins and authoritative Saudi choropleths require a licensed, versioned boundary source with stable bilingual identifiers. Display-name matching, guessed geometry, and an unlicensed substitute are prohibited.

## Decision

No boundary dataset, provider, license, version, administrative-level mapping, or update owner is selected because the repository contains no owner-supplied evidence.

`authoritative_saudi_choropleths_and_boundary_joins` remains disabled (`DF-006`). A request that depends on these boundaries must return `input_required` or typed unsupported behavior. It must not fall back to fuzzy Arabic/English display-name joins.

## Required owner evidence

- source/provider and acquisition method;
- license text and permitted interactive/export/derivative uses;
- immutable version/content hash and valid-from/valid-to policy;
- stable identifiers plus Arabic and English names for each supported level;
- source CRS, WGS84 conversion/validation provenance, and known topology limitations;
- privacy/aggregation constraints and an update/incident owner.

## Consequences

WP-09 may prepare contracts, fixtures, and failure states independent of a real source, but it cannot enable authoritative boundary functionality or claim Saudi regional correctness. Point/route data also cannot imply an administrative join without this evidence.

## Rollback

Disable the boundary version through its kill switch and reject dependent artifacts. Preserve immutable prior provenance; never swap geometry under an existing published artifact.
