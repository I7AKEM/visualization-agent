# WP-00 evidence

This directory contains the machine-readable handoff for WP-00. The integration decision is recorded separately in `docs/evidence/integration/wp-00-acceptance.yaml`.

Evidence scope:

- governance packet paths exist and parse as YAML;
- owner-input and disabled-feature references are internally consistent;
- POC/prohibited-path records are based on repository inspection;
- WP-00 changes stay within its owned documentation paths;
- no runtime, migration, dependency, configuration, secret, telemetry, or eval-corpus change is claimed.

The governance packet is **not approved for production** because organization inputs and named reviewers were absent. This is an explicit safe outcome, not a substituted decision. `handoff.yaml` distinguishes the substantive delivery commit from its handoff-only commit, lists the gates actually verified, and retains the owner-dependent blocks. Its conditional integration acceptance permits only the owner-independent WP-01 foundation after WP-01 ownership is assigned.
