# OSMS Recipe Layer

The catalog defines **what** every metric means (the contract). This layer
turns each card contract into runnable implementations — the recipes shown in
the Formula Lab — and proves them by machine before anything is published.

## Structure

    recipes/
      gen_recipes.py     generator: catalog -> recipes (all templates inline)
      gates.py           gate battery: lints, DuckDB, CPython, self-fixtures, Excel
      kql_check.js       Microsoft Kusto analyzer over every KQL snippet
      curated/           hand-verified recipes (source of truth, byte-pinned)
      xlsx_dialect.py    Excel range-model dialect: spec, render, workbook, engines
      ci/                engine runners for ES|QL, SPL and Excel (LibreOffice)
      out/               generated output (gitignored; rebuilt on every run)

## Recipe statuses

- `curated_verified` — hand-built, machine-recomputed in the pilot run
- `generated_concrete` — generated from the contract, engine-checked
- `generated_skeleton` — executable scaffolding; population hooks are
  deliberate, the generator never guesses a data model
- `pending` — mechanics not yet covered; the card contract itself is complete

## Publication rule

A dialect appears on the website only after a machine has verified it.
Published today: Generic SQL (DuckDB), Python (CPython), KQL (Kusto
analyzer). SPL and ES|QL exist as **CI candidates** (`ci_candidates.json`)
and are verified by the `Recipe CI` workflow against real engines; once the
engine jobs are green on `main`, the dialects are added to the published
bundle in a release commit.

## The Excel dialect (range model)

One formula = one KPI value over a sheet named `data` (raw rows, header in row 1),
with scope and period on a `result` sheet. It is limited to the Excel 2007 function
set (`COUNTIFS`/`SUMIFS`/`SUMPRODUCT`/`SMALL`/`MEDIAN`/`CEILING`/`IF`/`N`) so the same
formula runs unchanged in Excel, LibreOffice Calc and Google Sheets. Fail-closed uses
`NA()`; percentiles are an explicit nearest rank (`SMALL(range, CEILING(0.9*n,1))`), so
no interpolating estimator is involved. It is the only dialect verified against **two**
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
  its spec and recomputes it in Calc: the 14 fixtures must match the card
  examples exactly, and every candidate must resolve fail-closed on an empty
  sheet. This is the independent second engine behind gate `[9]`.

## Expected first-run findings (by design)

The curated SPL/ES|QL duration snippets use engine percentile functions
(`exactperc90`, `PERCENTILE(...,90)`). The fixtures enforce the card-mandated
nearest-rank values (SOC-002: P90 = 30 h). If an engine's method differs, the
job turns red — that is the track doing its job; the fix is an explicit
nearest-rank construction with a recipe version bump, as already used in the
generated duration templates.

Non-normative. The YAML card is the contract. Catalog CC BY 4.0, code MIT.
