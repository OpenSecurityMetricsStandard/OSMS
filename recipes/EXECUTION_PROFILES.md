# Versioned execution profiles

The existing eight dialects are retained: `py`, `gsql`, `pg`, `kql`, `spl`, `esql`,
`xlsx` and `dax`. `gsql` is the DuckDB-tested SQL profile; its name does not assert
GoogleSQL compatibility. No additional platform is introduced.

Generate the legacy bundle and the additional profiles together:

```sh
python recipes/gen_recipes.py --emit-candidates --out recipes/out
```

`execution-profiles.json` includes 207 literal quotient cards, the SOC-003 incident
snapshot and 119 explicit [prepared-observation profiles](SEMANTIC_PROFILES.md).
`execution-coverage.json` lists all 327 cards against all eight dialects (2,616
rows), with native-expression and exact export/reducer modes identified separately.
Existing source adapters remain separately identified. A generated profile is a candidate, not a runtime
verification record. `profile-report-ENGINE.json` is produced only by an actual
requested run and identifies its source hash, engine version and case population.

## Canonical quotient inputs

`canonical_quotient_v1` calculates the literal quotient already defined by the
card, from two named, reconciled measures. It does not implement raw-event
population selection. `source_adapter_status: required` is intentional. The
contract includes the card's cohort and additional gates verbatim so implementers
cannot substitute scope-only counts for the real numerator and denominator.

The `metric_inputs` table has one row per `(card_id, scope_id, period_start,
period_end)`. Card version, contract hash, operand names, both evidence references,
source system and source snapshot hash are mandatory. Period fields are UTC typed
timestamps in SQL/KQL/ES|QL/DAX and UTC epoch seconds in SPL; Python accepts ISO
strings or typed datetimes and compares equivalent UTC instants. Excel stores UTC
serial datetimes. Normalize local business timestamps before loading them.

The input numeric domain is explicit. Amount ratios STD-005, STD-076 and STD-073
allow signed numerators so an adverse return is retained. HRM-004 is unscaled;
STD-073, SOC-063 and SOC-065 are not subset proportions and are not capped at 100%.
Other selected proportions reject numerator > denominator. Zero denominator is
not_applicable, missing row is missing_input, and duplicate/invalid rows are
invalid_input. Output `ok` establishes calculation validity only. It does not
establish reporting Green, source authenticity or satisfaction of other card gates.

Adapters must preserve numerator and denominator population IDs, reconcile their
measures and units, and retain selection/classification rules and versions. A count
being in range does not prove subset membership. Confidence, uncertainty,
normalization and reporting gates are separate explicit stages.

## SOC-003

`incident_snapshot_v1` selects incidents resolved in `[period_start, period_end)`.
It independently computes MTTR (resolved minus detected), MTTA (acknowledged minus
alerted) and MTTC (contained minus detected). P50 is the arithmetic median including
both middle observations; P90 uses rank `ceil(0.9*n)` on the full multiset. Means
are supplementary. Hours preserve sub-second precision available in the platform.
Each output has valid/invalid counts; a missing, negative or post-resolution pair
invalidates that output. Other complete duration outputs remain available.

The snapshot has one incident per scope/incident ID. Within the selected scope,
IDs that differ only in letter case are rejected as collisions in this portable
profile. Case-sensitive source systems must provide lossless stable surrogate
identities and retain the original IDs in lineage. Scope selection is case-sensitive. A missing ID/evidence reference
or duplicate identity prevents numeric duration publication. Open stock is counted
immediately before period_end: detected before end and unresolved or resolved at/
after end. A future detected case is excluded. Source completeness and unresolved
records with missing detection time remain the adapter's mandatory quality checks.
The method cannot infer a complete incident universe from an empty table.

SQL, Python, KQL, SPL and Excel implementations and complete DAX query definitions
are supplied. DAX requires a UTC-typed `Incidents` table plus disconnected
`Scope[scope_id]` and `ReportingPeriod[period_start, period_end]` selectors. The
provided DEFINE/EVALUATE query selects an explicit example scope/period; change
those literals to the intended reporting context. Implicit visual filters are not
allowed to redefine the metric. SOC-002 DAX now also provides all five named outputs.

For SOC-003 ES|QL, run the exported count and row queries against the same sealed
input snapshot, retaining the JSON responses, then execute:

```sh
python recipes/esql_exact.py --count-json count.json --rows-json rows.json \
  --period-start 2026-06-01T00:00:00Z --period-end 2026-07-01T00:00:00Z \
  --scope-id prod --snapshot-hash YOUR_SNAPSHOT_SHA256 --out result.json
```

This is an explicit ES|QL export plus exact Python reduction. It is not a native
ES|QL percentile. Duplicate duration values are preserved. Partial/warned responses,
missing columns and count mismatch fail; the query exports at most 10,000 rows.
Larger populations need a complete separately materialized snapshot, not silent
truncation. Capture HTTP Warning headers as `warnings` in the exported response;
JSON responses alone cannot establish the absence of HTTP warnings. An immutable
snapshot hash is input evidence; the reducer cannot prove the server was sealed.

## Verification commands

```sh
python -m unittest discover -s tests -v
python recipes/ci/profile_runner.py --bundle recipes/out --engine python
python recipes/ci/profile_runner.py --bundle recipes/out --engine duckdb
python recipes/ci/profile_runner.py --bundle recipes/out --engine postgresql
python recipes/ci/profile_runner.py --bundle recipes/out --engine formulas
python recipes/ci/profile_runner.py --bundle recipes/out --engine libreoffice
npm ci --prefix recipes
node recipes/kql_check.js recipes/out/profile-kql-jobs.json
```

The PostgreSQL runner uses the standard PG environment variables and temporary
transaction-local tables. Requested unavailable engines fail. `--cards` and
`--case-ids` explicitly record a subset; a subset pass cannot establish full coverage.
The positive 3/4, zero, empty, duplicate, signed-return, above-one, invalid-value,
wrong-version/operand/contract/evidence, scope and period oracles are independent
of the snippet generator. Statistical tolerances apply to raw numeric results;
counts and statuses are exact. A syntax check, a pure-Python Excel evaluator,
LibreOffice and native Microsoft Excel are distinct evidence types.

Native Kusto, Power BI/Analysis Services and Microsoft Excel execution remain
unverified. Earlier SPL/Elasticsearch CI runs do not verify the new profile layer.

## Export a selected implementation

```sh
python recipes/export_implementation.py --card SOC-003 --dialect pg --out exports/SOC-003.pg.sql
python recipes/export_implementation.py --card SOC-003 --dialect dax --out exports/SOC-003.dax
python recipes/export_implementation.py --card SOC-003 --dialect xlsx --out exports/SOC-003-formulas.txt
python recipes/export_implementation.py --card SOC-003 --dialect xlsx --workbook --template-rows 1000 --out exports/SOC-003.xlsx
python recipes/export_implementation.py --card SOC-023 --dialect xlsx --workbook --out exports/SOC-023.xlsx
```

Every exported file has a companion contract/source manifest. The workbook starts
empty: it contains no measured business result. It prepares 1,000 input rows and
matching helper formulas by default. Set `--template-rows` to the needed capacity
(1..99,999) before exporting. Paste values into the input columns, preserving
helpers and sheet names. Input below the prepared rows blocks the results with
`template_input_valid=0`; generate a larger template instead of extending its range
manually. Invalid scope/period parameters also block the template. A valid template
capacity is not a source-quality or reporting approval. Workbook export rejects
source files that differ from the selected bundle. Formula text includes English and
German helper and result formulas. The exported ES|QL profile for SOC-003 is a multi-step
protocol JSON; execute its query/reducer sequence, not the JSON as a query.

The native ES|QL and SPL CI profile runners use inline typed synthetic rows. They
test arithmetic, identities and invalid inputs without altering source indices.
They do not test ingestion. SPL additionally applies case-sensitive `where` filters
for card and scope identity, consistent with the
[Splunk where contract](https://help.splunk.com/en/splunk-enterprise/search/spl-search-reference/9.4/search-commands/where).
Use `--engine esql` or `--engine spl` against the disposable local CI services;
SPL authentication comes from environment variables. Native availability is
required; a requested run cannot silently fall back to a different engine.
