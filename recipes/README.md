# OSMS Recipe Layer

This is a remediation working draft. The generator produces candidate recipes,
complete card exports and explicitly blocked templates. It does not prove a
formula or authorize website publication. See [execution contracts](CONTRACTS.md)
for implemented corrections, adapter requirements and remaining limitations.
See [engine support and verification scope](ENGINE_SUPPORT.md) for the current
runtime evidence, numeric fixture counts and completion priorities.

The additional [execution profiles](EXECUTION_PROFILES.md) provide 207 canonical
quotient calculators, the SOC-003 incident contract and all 119 remaining cards as
explicit prepared-observation calculations. Their 2,616-row inventory identifies
native expressions, exact export/reducer paths and each engine's verification state.
They are exported separately from raw-source adapters and legacy templates.

## Structure

    recipes/
      gen_recipes.py     generator: catalog -> recipes (all templates inline)
      gates.py           gate battery: lints, DuckDB, CPython, self-fixtures, Excel
      kql_check.js       Microsoft Kusto analyzer over every KQL snippet
      curated/           candidate recipes (source of truth, byte-pinned)
      xlsx_dialect.py    Excel range-model dialect: spec, render, workbook, engines
      ci/                engine runners for ES|QL, SPL and Excel (LibreOffice)
      out/               generated output (gitignored; rebuilt on every run)

## Recipe statuses and evidence

- `curated_candidate`: manually maintained implementation, awaiting evidence for
  this exact revision.
- `generated_concrete`: arithmetic implementation whose full source, period and
  profile contract must still be assessed; generation is not engine verification.
- `generated_skeleton`: `mapping_required`; templates remain available separately
  while executable outputs cannot return a plausible KPI value.
- `pending`: implementation unavailable.

`coverage.json` reports the actual card populations and numeric candidate fixture
count. `template-fixtures.json` preserves examples for incomplete templates.
The nine retained numeric candidate fixtures are not conformance coverage of all
327 cards. KQL analyzer success is syntax/type evidence, not a Kusto execution.
External engine reports must identify versions and exact source/recipe hashes.
No website deployment or stable-release approval occurs in the generator.

## The Excel dialect (range model)

One formula = one KPI value over a sheet named `data` (raw rows, header in row 1),
with scope and period on a `result` sheet. It is limited to the Excel 2007 function
set (`COUNTIFS`/`SUMIFS`/`SUMPRODUCT`/`SMALL`/`MEDIAN`/`CEILING`/`IF`/`N`) for portability. Actual compatibility requires an engine run; Excel and Google Sheets
have not been executed in this remediation. Fail-closed uses
`NA()`; percentiles are an explicit nearest rank (`SMALL(range, CEILING(0.9*n,1))`), so
P50 is the arithmetic median and P90 uses nearest rank. CI includes two
engines: the pure-Python `formulas` library (gate `[9]`, every push) and LibreOffice
Calc (the `excel` job). `xlsx_dialect.py` is the single source — the generator renders
the published snippet from the same spec both engines execute.

## Run locally

    python3 recipes/gen_recipes.py --emit-candidates --out recipes/out
    python3 recipes/gates.py --bundle recipes/out
    node recipes/kql_check.js recipes/out/kql_jobs.json   # npm i @kusto/language-service-next
    python3 recipes/ci/excel_runner.py --out recipes/out --dry-run   # Excel logic (formulas)
    python3 recipes/ci/excel_runner.py --out recipes/out             # Excel second engine (LibreOffice)

## CI jobs (.github/workflows/recipes-ci.yml)

- **gates** — full local battery plus runner dry-runs; runs on every push
  touching `catalog/` or `recipes/`.
- **esql** — real Elasticsearch service container; loads each fixture card's
  rows, runs the candidate query, compares against the card's own example
  values; every candidate must also execute against an empty, typed index.
- **spl** — same idea with a real Splunk container. **Opt-in**: set the
  repository variable `ENABLE_SPL_CI=true` and the secret
  `SPLUNK_CI_PASSWORD` only after verifying the current Splunk Docker image
  license terms for CI use.
- **excel** — installs headless LibreOffice, rebuilds every Excel workbook from
  its spec and recomputes it in Calc: the nine retained numeric fixtures must match the card
  examples exactly, and every candidate must resolve fail-closed on an empty
  sheet. This is the independent second engine behind gate `[9]`.

## Known verification gaps

The legacy numeric fixture set contains nine cards. The ES|QL scalar runner
executes seven; SOC-002 remains blocked and SOC-003 uses a separate export/reducer
protocol for its exact outputs. Median and percentile semantics must
follow each named card output, including repeated values and even sample sizes.
Do not infer an implemented duration recipe from a preserved template example.

KQL currently has syntax/type analysis only. PostgreSQL-flavored snippets are
checked on DuckDB, not native PostgreSQL. The maintained DAX query definitions have no native
runtime report; SOC-002 and SOC-003 now include their named numeric outputs. Spreadsheet execution uses
`formulas` and LibreOffice; Microsoft Excel and Google Sheets remain unverified.
The [engine inventory](ENGINE_SUPPORT.md) records these distinctions and links
the actual CI execution evidence.

Non-normative. The YAML card is the contract. Catalog CC BY 4.0, code MIT.
