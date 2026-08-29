# WP-00 governance packet

Status: **input required; not approved for production**

Baseline date: 2026-08-29

Scope: WP-00 only

This directory records the governance baseline required before production work can rely on organization-specific facts. It deliberately does not select a cloud, account, region, identity provider, boundary dataset, semantic layer, named owner, model provider, or retention period.

The production-spec package remains normative. These records expose missing decisions, acceptance state, and safe disabled behavior; they do not amend the specification.

## Packet contents

| Record | Purpose |
|---|---|
| `governance-packet.yaml` | packet index and overall acceptance state |
| `owner-input-checklist.yaml` | every organization input that must be supplied by an accountable owner |
| `poc-inventory.yaml` | current research POC components, dependencies, evidence, and gaps |
| `prohibited-production-paths.yaml` | POC paths that must never be promoted into production unchanged |
| `data-classification-acceptance.yaml` | frozen classification vocabulary and pending policy acceptance |
| `retention-acceptance.yaml` | retention decisions still requiring owner input |
| `slo-acceptance.yaml` | normative controlled-beta objectives and acceptance state |
| `limit-acceptance.yaml` | normative beta defaults and change controls |
| `disabled-features.yaml` | capabilities kept off until their blocking input is accepted |
| `requirements-traceability.yaml` | WP-00 requirement-to-evidence skeleton for later test ownership |

The related decision records are in `docs/adr/`. Evidence and the work-package handoff are in `docs/evidence/wp-00/`.

## Interpretation

- `recorded` means the normative engineering baseline was transcribed without change.
- `input_required` means the organization has not supplied the fact.
- `acceptance_required` means named accountable roles must approve a recorded baseline.
- `disabled` means production code/configuration must fail closed or omit the capability until all blockers are resolved.
- Empty `owner`, `reviewer`, and `approver` values are never replaced with invented people.

WP-01 may use these paths to scaffold owner-independent foundations. No record here authorizes production traffic, external data egress, map boundaries, governed metrics, retention enforcement, or deployment.
