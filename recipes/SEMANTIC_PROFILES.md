# Prepared observation profiles

The additional `prepared_observations_v1` profiles bind the 119 cards outside the
207 canonical quotient profiles and the SOC-003 incident snapshot. Together they
cover all 327 catalog cards at an explicit calculation stage. This does not attest
the completeness or authenticity of an application's source adapters.

Generate `execution-profiles.json` with `python recipes/gen_recipes.py
--emit-candidates --out recipes/out`. Each profile contains a typed plan, its card
version and contract hash, platform expressions, an Excel specification, and
independent arithmetic examples. The same retained eight dialects are used.

| Dialect | Implementation |
|---|---|
| Python | Standalone standard-library calculation over typed observations |
| DuckDB / PostgreSQL | Typed `osms_input`, bound parameters, exact ordered-set quantiles |
| KQL | Typed table, explicit sorted multisets, 1,048,576-record capacity gate |
| SPL | Prepared UTC epoch-second fields, exact sorted ranks, 10,000-record capacity gate |
| ES\|QL | Complete immutable count/row export, then exact Python reduction; no native percentile claim |
| Excel | Native formulas, separate helper columns and calculation cells; English/German display |
| DAX | Complete query over a typed model table; explicit selectors and exact order statistics |

Engine execution status is supplied by matching reports, never by this table.
KQL analysis proves syntax/types only. Excel-library execution is not native Excel
execution. Native DAX and SPL execution must be evidenced on those engines before
claiming their conformance. Engine limits and rejected/partial responses must not
be bypassed by truncating the input.

## Input and output contract

Observations bind card ID/version, contract hash, scope, exact reporting-period
boundaries, segment, record identity, source identity, snapshot and evidence
references. A complete-population attestation is an explicit execution parameter;
it is false by default in templates. Selectors do not establish that attestation.
Different scopes, periods or segments are excluded before arithmetic. Duplicate
identities, invalid required fields, unsupported enumerations, conflicting method
versions and invalid domains block results. Date/time inputs are UTC; date-only
input in the Python interface explicitly denotes midnight UTC.

Prepared factors, source registers, population membership, anchors, baselines and
their approvals still need traceable application evidence. A nonempty reference
does not prove that the referenced document exists or is approved. Local method
changes require a new contract/version and must not reuse an old verification
report. Count outputs have exact tolerances. Numeric tolerance is applied before
display rounding; minute-valued Excel clocks allow 1e-7 minutes for date-serial
floating-point resolution.

Reference method parameter versions use the explicit allowlist
`osms-reference/0.9.2`. This identifies the reference method, not an application
approval. A local method/baseline/weight-register version must be bound explicitly
in its own versioned contract before exporting and testing that implementation;
unknown version strings are rejected. Different parameter sets must not reuse a
reference contract's execution evidence as proof of their approval.

`ok`, `partial`, `not_applicable`, `invalid_input`, `population_unverified`, and
platform capacity failures describe calculation validity. They do not grant Green
reporting eligibility. Confidence and approved risk-appetite gates remain required.
Multi-part cards export separate values, bases and applicable bands. Empty parts
remain n/a; independent critical overrides remain visible. Band codes are 0 Target,
1 Amber, 2 Red, null n/a. Pending unobserved benefits have no Target band.

STD-003 exports a service array in Python/SQL/KQL and rows in DAX/SPL. Excel exposes
the named ranking helper columns; filter nonblank `ranked_service_id`, order by
competition rank, then service ID. The exact full population must be validated
before grouping, ranking or selecting a top N. Zero complete populations of risk
values receive zero display scores and tied ranks; an empty population has no ranks.

## Export and test commands

```bash
python recipes/export_implementation.py --bundle recipes/out --card STD-006 --dialect pg --out exports/STD-006.sql
python recipes/export_implementation.py --bundle recipes/out --card VAL-001 --dialect xlsx --workbook --template-rows 1000 --out exports/VAL-001.xlsx
python recipes/ci/semantic_runner.py --bundle recipes/out --engine python
python recipes/ci/semantic_runner.py --bundle recipes/out --engine duckdb
python recipes/ci/semantic_runner.py --bundle recipes/out --engine formulas
python recipes/ci/semantic_runner.py --bundle recipes/out --engine postgresql
python recipes/ci/semantic_runner.py --bundle recipes/out --engine libreoffice
```

PostgreSQL uses the standard `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`
connection variables. Fixture runners create temporary data only. Reports record
the actual engine version, source-bundle hash, requested subset and case outcomes.
Independent expected results are in `recipes/semantic/cases.py`; the report runner
never generates its expected values using the calculation being tested.

## Historical evidence

`reference/execution_store.py` captures a frozen plan, observations, parameters,
result and interpreter identity. Retain the returned manifest hash independently.
`replay` verifies every file and recalculates against that receipt. `export_report`
and `restore` support a complete file inventory and independent archive replay.
Missing or additional files, changed inputs/results, mixed scope/version identity
and a different interpreter fail explicitly. An archived card's later deactivation
does not alter its report. Source authenticity and authorization require their own
evidence; a matching hash is not a substitute.

The older SQLite mechanics demo remains a structural diagnostic. Its generic
component sums are not accepted as full card conformance. The CLI demo now also
executes card-specific DSPS, weighted mean, duration, ranking and multi-part profiles
with retained input evidence.

## Units and simulation reporting

Every scalar output declares its own unit and numeric type. Counts, rating codes
and eligibility flags compare exactly. Duration, currency, percentage and
unscaled ratios have separate unit labels and absolute/relative tolerances.
Survey outputs identify their variant-specific unit. A diagnostic weight sum
is a weight quantity, not a score or percentage.

STD-002a distinguishes calculation from reporting eligibility. Its arithmetic
fixture deliberately contains four joint draws and reports reporting_eligible=0;
reporting requires at least 100,000 complete joint draws plus the other model,
source and confidence gates. Python/SQL and suitably provisioned BI/Kusto engines
can evaluate that population. The default bounded SPL, ES export and Excel
profiles do not accommodate that reporting population; use a complete frozen
calculation on a capable engine and retain its evidence. Do not truncate the
simulation to the platform limit or represent the small fixture as reportable.
The synthetic benchmark provides four reproducible 100,000-draw scenarios.
