# Open Security Metrics Standard (OSMS™)

[![Validate](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/validate.yml/badge.svg)](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/validate.yml)
[![Recipe CI](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/recipes-ci.yml/badge.svg)](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/recipes-ci.yml)

**Security metrics as code.** OSMS is an open, machine-readable standard for
security KPIs: over 300 metric cards (this release: 327, enforced by the
validator), each a complete decision contract - formula, data requirements,
thresholds, decision links, drill-down path and evidence fields in one YAML
card.

Website: <https://opensecuritymetrics.org> ·
Formula Lab: <https://opensecuritymetrics.org/formula-lab/> ·
Card Studio: <https://opensecuritymetrics.org/card-studio/>

## What makes a card a contract

- **Fail-closed arithmetic** - an empty case base is n/a, never a fabricated 0
- **Decision-linked thresholds** - every threshold names the decision it triggers
- **Data-confidence gates** - low input confidence blocks operational Green
- **Drill-down lineage** - every board number decomposes in at most 4 steps
- **Versioned cards** - weight or threshold changes are visible trend breaks

Framework mappings are included for NIST CSF 2.0, ISO/IEC 27001:2022,
CIS Controls v8.1 (Safeguard IDs only - see <https://www.cisecurity.org/controls>),
MITRE ATT&CK, DORA and NIS2. Mappings are informative aids, not conformity
claims.

## Repository layout

    catalog/    osms-catalog.yaml (the standard), taxonomy, domains, principles
    schema/     JSON schema and field conventions
    tools/      validator, formula audit, review KPIs, release tooling
    reference/  star schema, seed data, drill engine (reference implementation)
    recipes/    recipe layer: generated + curated query implementations, engine CI
    tests/      validator test fixtures

## Validate it yourself

OSMS claims to be a *reproducible decision contract* - so don't take our word
for it:

```bash
git clone https://github.com/OpenSecurityMetricsStandard/OSMS && cd OSMS
pip install pyyaml jsonschema
python tools/osms_validate.py catalog/osms-catalog.yaml \
  --taxonomy catalog/taxonomy.yaml --domains catalog/domains.yaml \
  --expect-count 327
python tools/formula_audit.py catalog/osms-catalog.yaml
```

The validator enforces the card contract plus 16 semantic rules (ID
uniqueness, parent/child integrity, rollup cycle detection, helper cards never
board-reportable, direction/threshold consistency, fail-closed denominators,
data-confidence gates, decision chains, version-break rules, evidence fields,
<=4-step drilldown lineage). The formula audit recomputes every calculation
example and enforces the field conventions. Every push runs the same checks
in CI, and the recipe CI verifies generated query implementations against
real engines (DuckDB, CPython, Kusto analyzer, Elasticsearch, Splunk) - see
[recipes/README.md](recipes/README.md).

## Review (v0.9.x)

The public review runs 6 July - 15 August 2026; freeze target for 1.0 is
30 August 2026. The review is governed by its own KPIs with a published
go/no-go rule: see [REVIEW_PROCESS.md](REVIEW_PROCESS.md). Submit findings as
a [Review Finding issue](https://github.com/OpenSecurityMetricsStandard/OSMS/issues/new/choose)
or via <review@opensecuritymetrics.org>.

## Licensing

| Asset | License |
|---|---|
| Specification, catalog (YAML), taxonomy, principles, crosswalks | [CC BY 4.0](LICENSE) |
| Validator, scripts (`tools/`), JSON schema (`schema/`) | [MIT](LICENSE-CODE) |
| The book (official guide) | All rights reserved - not part of this repository's licenses |

Attribution format and trademark notice: see [NOTICE](NOTICE).
"OSMS" is an EU trade mark application (No. 019380729). The open licenses do
not grant trademark rights.
