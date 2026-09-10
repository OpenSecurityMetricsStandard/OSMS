# Engine support and verification scope

OSMS definitions and principles in this repository are authoritative. An engine
profile implements named card outputs; it does not redefine their formula, cohort,
units, estimator, risk-appetite thresholds or missing-data rules.

## Historical inventory before the additional profiles

This inventory describes the source at
`e3fda1c1a78f5052253b28e3626f5f78d13a9ea5`. The cited execution evidence is
[Recipe CI run 34476234972](https://github.com/OpenSecurityMetricsStandard/OSMS/actions/runs/34476234972)
on correction head `20fde5a4b37586bf8122b842dd2425aa1f3b4442`. Subsequent commits
changed documentation and importer wording, not recipe arithmetic or engine runners.
This historical run must not be used to verify later changed implementations.

The bundle contains eight recipe dialect identifiers. A dialect identifier, a
runtime engine, a syntax check and a passing numeric fixture are different things.

| Dialect | Available source | Executed runtime / evidence | Remaining gap |
|---|---|---|---|
| `py` | 277 snippets | CPython 3.12 / pandas; 8 numeric card fixtures and 277 empty/blocked checks pass | Broader output-specific, boundary and invalid-input coverage |
| `gsql` | 277 snippets | DuckDB 1.5.5; 8 numeric card fixtures and 277 empty/blocked checks pass | Runtime-specific SQL profiles and wider card coverage; this is not BigQuery verification |
| `pg` | 2 maintained recipes | Selected PostgreSQL-flavored snippets are exercised on DuckDB by the regression suite | No native PostgreSQL runner or native execution report |
| `kql` | 277 snippets | Kusto language-service-next 12.4.1 syntax/type analysis passes for 277 snippets | No query-engine execution or numeric KQL conformance report |
| `spl` | 277 snippets | Splunk 9.4 and 10.2; 8 numeric card fixtures and 277 empty/blocked checks pass per version | Wider negative/edge-case coverage and pinned image digests |
| `esql` | 277 snippets | Elasticsearch 8.17.4; 7 numeric card fixtures and 277 empty/blocked checks pass | SOC-002 has no numeric ES|QL implementation; complete percentile population semantics remain unresolved |
| `xlsx` | 277 formula snippets | `formulas` 1.3.4: 8 numeric fixtures; LibreOffice Calc: 8 numeric fixtures and 277 empty/blocked checks pass | No native Microsoft Excel or Google Sheets execution; no Google Sheets-specific profile |
| `dax` | 2 maintained recipes | Static lint checks only | No Power BI/Analysis Services execution; SOC-002 implements P90 only |

SQLite is also used by `reference/drill_engine.py` and the database regression
suite. It validates the reference schema, constraints and selected mechanics;
it is not proof that all card calculations work in a production warehouse.

### Coverage denominator

There are 327 catalog cards: 2 maintained candidates, 6 generated concrete
candidates, 269 blocked templates and 50 pending implementations. A passing
empty/blocked check establishes refusal or empty-input behavior; it does not mean
that the corresponding metric has an implemented, validated calculation.

The numeric fixture cards are STD-001, STD-075, STD-068, STD-069, RES-007, LOG-015,
STD-016 and SOC-002. ES|QL currently executes the first seven only. These are
positive examples for 8 of 327 cards, with selected additional regression cases;
they are not an exhaustive per-output conformance suite. SOC-002's ES|QL
refusal counts as blocked behavior, never as a numeric fixture pass.

## Completion priorities

1. Establish per-card/output execution contracts and independent expected results:
   types, units, keys, scope, time anchors, estimator, status, tolerance and profiles.
   Bind every runtime report to the exact source, card and profile versions.
2. Complete the portable Python reference and add a native PostgreSQL runner
   against the same independent fixtures. Keep the existing SQLite and DuckDB
   checks for their explicitly stated purposes.
3. Add functional KQL engine execution. The
   [Kusto emulator](https://learn.microsoft.com/en-us/azure/data-explorer/kusto-emulator-overview)
   supports local automated query tests. Its limitations and version must be
   recorded; it does not certify Sentinel/Defender ingestion or service behavior.
4. Extend Splunk, Elasticsearch and spreadsheet cases to negative values, missing
   evidence, duplicated IDs, invalid profiles, period boundaries and multi-output
   results. Resolve or explicitly retain unsupported output statuses.
5. Add native DAX/Power BI and Microsoft Excel verification for their declared
   profiles before asserting compatibility. DAX verification needs an executable
   semantic model, including data types, relationships and filter context.
6. Retain the eight existing dialects and complete their card/output contracts.
   No platform expansion is part of this remediation.

This order follows OSMS-10. The normative card contract is vendor-neutral;
implementation support and evidence are published per card, output and engine.
Confidence dimensions and validity gates follow OSMS-03. P50/P90 estimator choices
follow the card and OSMS-05. Thresholds remain versioned risk-appetite decisions
under OSMS-06, not constants inferred from a particular engine. Version and lineage
records follow OSMS-08/09. Pilot evidence and website deployment are separate
acceptance evidence and are not generated by an engine test.

## Additional candidate source

The current working changes add SOC-003's resolved-cohort multi-output contract,
complete SOC-002 DAX outputs, 207 canonical quotient profiles and 119 explicit
prepared-observation profiles. The numeric legacy fixture set is nine cards; 268 raw templates stay
blocked and 50 legacy cards remain pending. Canonical arithmetic does not resolve
those source adapters. Every card now has an additional calculation profile; native
execution evidence and source-adapter validation remain separate requirements.

The new PostgreSQL runner requests native execution and records the server version.
The existing ES|QL/SPL CI jobs additionally run canonical calculation profiles with
inline typed fixtures, separating arithmetic/validation from ingestion. Positive
coverage and broader boundary subsets have separate reports. Python, DuckDB,
formulas and LibreOffice use the same independent oracles. KQL has an additional
326-profile analyzer batch. Prepared observations also have native PostgreSQL,
LibreOffice, ES|QL export and optional SPL CI jobs. Microsoft Excel, Kusto and Power
BI numeric execution remain unverified unless a corresponding report is supplied.

See [current working verification](../review/EXECUTION_VALIDATION.md). The historical
CI run above does not verify these changes. `collect_profile_reports.py` accepts
only reports matching the exact exported profile bundle hash and retains case and
output coverage; generation never produces passing engine evidence.
