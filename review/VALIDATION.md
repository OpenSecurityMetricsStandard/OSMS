# Validation record — 2026-09-10

Scope: local remediation working tree based on
`747cd28fb0b6728ebadbe6c477722d166b5b40b5`. The patch and source snapshot supplied
with this record identify the candidate. No remote CI execution, upstream merge,
website deployment or board approval is claimed.

| Check | Observed result | What it establishes |
|---|---|---|
| Independent regression suite | 32 tests PASS, including adversarial subcases | Targeted corrected behavior; not exhaustive card conformance |
| Full card JSON schema and export | 327 cards PASS; all original card fields preserved | Structural completeness and lossless export |
| Catalog validator | 0 errors, 4 warnings | Selected invariants; warnings remain visible |
| Formula audit | 0 findings | Implemented reference/cycle/literal-zero and example-pattern checks |
| Reference mechanics | 12 arithmetic demo cases and tamper rejection PASS; ranking explicitly unimplemented | Arithmetic/reference identity, not all card semantics |
| Readiness taxonomy | 327 cards, 59 classes, 632 mapped source strings PASS | Taxonomy coverage |
| Recipe lints | 1,666 snippets PASS | Implemented static checks only |
| SQL/Python empty or blocked execution | 277/277 each PASS | Empty behavior or explicit mapping-required refusal |
| Composite example gates | 3/3 plus negative gates PASS | Supported subscore arithmetic |
| Numeric candidate fixtures | 8/8 SQL, 8/8 Python, 8/8 formulas PASS | Positive numeric examples for eight cards |
| Kusto analyzer | 277/277 PASS | Syntax/type analysis, not Kusto query execution |
| LibreOffice numeric fixtures | 8/8 exact, CSV results independently compared | Second spreadsheet engine for the same eight positive examples |

The eight numeric fixture cards are STD-001, STD-075, STD-068, STD-069, RES-007,
LOG-015, STD-016 and SOC-002. Six duration examples are preserved separately as
`template-fixtures.json` because the underlying templates still require complete
population/period/unit mapping. Final implementation populations are 2 curated
candidates, 6 generated concrete candidates, 269 blocked skeletons and 50 pending.
The denominator for numeric candidate example coverage is 327, not 8.

The four remaining validator warnings concern >4-step lineages for STD-001,
STD-008 and VAL-001, and the catalog-wide absence of a lifecycle field. They were
not hidden, waived or reclassified as proof of compliance.

## Environment and reproduction

Python 3.12; direct package versions are pinned in `requirements-checks.txt`.
Kusto language-service-next 12.4.1. LibreOfficeDev 26.8.0.0.alpha0,
build `2c87e51eeaa2b413ff4ae097b2705eea1995d8e5` (the supplied runtime's development
build). This is not proof of Microsoft Excel or every production Calc version.

```bash
python -m unittest discover -s tests -v
python tools/osms_validate.py catalog/osms-catalog.yaml --expect-count 327
python tools/formula_audit.py catalog/osms-catalog.yaml
python reference/drill_engine.py --coverage
python reference/drill_engine.py --demo
python tools/readiness/build_readiness_bundle.py --check
python recipes/gen_recipes.py --emit-candidates --out recipes/out
python recipes/gates.py --bundle recipes/out
npm install @kusto/language-service-next@12.4.1
node recipes/kql_check.js recipes/out/kql_jobs.json
python recipes/ci/excel_runner.py --out recipes/out --soffice soffice --max-empty 3
```

The new Excel negative regression cases cover missing treatment dates, timely and
late mitigation, missing composite values and duplicate penalty IDs in formulas.
The LibreOffice run exercises the positive candidate fixtures; it does not claim
those additional negative cases were executed in Calc.

Not run here: real PostgreSQL, Kusto execution, Elasticsearch, Splunk, DAX/Power BI,
Microsoft Excel or Google Sheets. PostgreSQL-flavored SQL was executed on DuckDB,
which cannot establish PostgreSQL runtime compatibility. ES|QL SOC-002 is explicitly
blocked due to multiset percentile semantics. Full per-output, per-card and
per-engine conformance remains open; see F-15/F-17 in `REMEDIATION.md`.

The archive manifest records every included source file. The generated recipe
bundle records its catalog hash; the handoff package also includes the actual
fixture/recipe hashes and logs. This is technical evidence, not a vote or approval.
