# Open Security Metrics Standard (OSMS™)

[![Validate](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/validate.yml/badge.svg)](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/validate.yml)
[![Recipe CI](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/recipes-ci.yml/badge.svg)](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/workflows/recipes-ci.yml)

**Security metrics as code.** OSMS is an open, machine-readable standard for
security KPIs: over 300 metric cards (this release: 327, enforced by the
validator), each a structured candidate decision contract - formula, data requirements,
thresholds, decision links, drill-down path and evidence fields in one YAML
card.

Website: <https://opensecuritymetrics.org> ·
Formula Lab: <https://opensecuritymetrics.org/formula-lab/> ·
Card Studio: <https://opensecuritymetrics.org/card-studio/>

## What makes a card a contract

- **Fail-closed arithmetic** - an empty case base is n/a, never a fabricated 0
- **Decision-linked thresholds** - every threshold names the decision it triggers
- **Data-confidence gates** - low input confidence blocks operational Green
- **Drill-down lineage** - drill paths are specified; depth exceptions remain tracked
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

The validator checks schema structure and selected documented invariants. The
formula audit checks references/cycles, literal zero denominators and explicitly
supported example patterns; it does not prove every free-text formula. The drill
engine's strategy coverage is not per-card mathematical conformance.

Run the independent audit regressions and recipe gates with pinned direct dependencies:

```bash
pip install -r requirements-checks.txt
python -m unittest discover -s tests -v
python recipes/gen_recipes.py --emit-candidates --out recipes/out
python recipes/gates.py --bundle recipes/out
```

Incomplete templates fail closed and remain available for implementation. Numeric
fixture coverage, unresolved methods and external engines not run must be reported
separately. See [execution contracts](recipes/CONTRACTS.md) and the
[remediation record](review/REMEDIATION.md).

## Review (v0.9.x)

The current source version is **OSMS 0.9.2 — maintainer draft**, developed from
0.9.1. The maintainer may correct, merge and release 0.x versions while the board
is being assembled. See the [0.9.2 change record](review/RELEASE_0.9.2.md).
At formal board review start, select an immutable baseline and a new timetable.
The earlier July/August dates are historical planning, not evidence of a completed
review. See [REVIEW_PROCESS.md](REVIEW_PROCESS.md) and the
[candidate method decisions](review/METHOD_DECISIONS.md). Submit findings as
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
