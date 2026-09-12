# Native Microsoft Excel and DAX verification

For the F-03/F-06 acceptance scope, the checked wrapper runs the eight finding
cards and verifies every expected case/output before reporting success:

```powershell
./recipes/ci/run_desktop_acceptance.ps1 -Engine excel -Scope audit-critical
./recipes/ci/run_desktop_acceptance.ps1 -Engine dax -Scope audit-critical -Server localhost:PORT -TomAssembly PATH_TO_TABULAR_DLL -AdomdAssembly PATH_TO_ADOMD_DLL
```

Use `-Scope all` for all 327 profiles. This requires an actual Windows host with
the licensed products and pinned Python dependencies already installed. No native
Excel or DAX execution is claimed by providing these commands. The wrapper stops
on engine or acceptance failure. Preserve the original reports before another run.

The platform-independent planning command below emits an explicitly unexecuted
fixture manifest. The verification command checks exact source/fixture hashes,
case/output completeness, duplicates, timestamps, status and actual output values;
an incomplete, stale, aborted or emulated report fails.

```sh
python tools/desktop_acceptance.py --plan-only --scope all --out desktop-case-manifest.json
python tools/desktop_acceptance.py --engine excel --scope audit-critical --report recipes/out/profile-report-desktop-excel.json --out desktop-acceptance.json
```

These optional test adapters require installed native products. They have no
simulator fallback. Their presence is not a passing runtime report. Use a disposable
local Analysis Services test instance with permission to create/delete test models;
the runner creates only unique `osms_test_<guid>` databases and removes those models
after each fixture. Production models are not used. Excel runs generated fixture
workbooks with macros, events and external link updates disabled and checks full
recalculation again after save/reopen.

From the candidate checkout on Windows, install the pinned Python dependencies and
generate the bundle. With Microsoft Excel installed:

```powershell
python recipes/gen_recipes.py --emit-candidates --out recipes/out
python recipes/ci/desktop_runner.py --engine excel --cards SOC-003,STD-001,STD-003
python recipes/ci/desktop_runner.py --engine excel
```

For a local Analysis Services tabular test server and matching installed TOM/ADOMD
client assemblies, supply their actual paths and port:

```powershell
python recipes/ci/desktop_runner.py --engine dax --server localhost:PORT --tom-assembly PATH_TO_TABULAR_DLL --adomd-assembly PATH_TO_ADOMD_DLL --cards SOC-003,STD-001,STD-003
python recipes/ci/desktop_runner.py --engine dax --server localhost:PORT --tom-assembly PATH_TO_TABULAR_DLL --adomd-assembly PATH_TO_ADOMD_DLL
python recipes/ci/collect_profile_reports.py --bundle recipes/out
```

Reports identify the engine version, exact source bundle, card/profile, case and
outputs. Preserve reports under separate directories when testing multiple versions
or subsets; the collector accepts `--reports DIRECTORY` and rejects stale bundle
hashes. The full run covers all 327 calculation profiles. Scope and reporting-period
tables are intentionally disconnected in the provided measure models; generated
queries bind those parameters explicitly. This does not certify arbitrary Power BI
visual filters, imported production models, DirectQuery, relationships or capacity.

The model builder uses [DAX table constructors](https://learn.microsoft.com/en-us/dax/table-constructor)
for typed fixture expressions and [TOM calculated-table columns](https://learn.microsoft.com/en-us/dotnet/api/microsoft.analysisservices.tabular.calculatedtablecolumn)
for the model schema. Timestamp precision and missing-data behavior must pass the
actual output tolerances; an adapter must not round them into an apparent pass.

Use a fresh checkout that honors the repository's LF attributes. The Windows
wrapper enables Python UTF-8 mode; when invoking the generator manually on Windows,
use `python -X utf8 recipes/gen_recipes.py --emit-candidates --out recipes/out`.
Source paths in the profile bundle use forward slashes and its JSON bytes use
UTF-8/LF on both platforms. A checkout with changed source bytes is intentionally
rejected, rather than weakening the source-hash comparison.

Website artifact comparison is separate. After external deployment, retain its
catalog, schema, execution profiles and a JSON attestation with `source_commit`,
`catalog_url`, `schema_url`, `profiles_url`, `deployment_evidence_ref`. Run
`tools/verify_website_contract.py --help` for comparison arguments. This checks the
supplied artifacts and attestation, not their authenticity or live browser behavior;
retain the actual deployment and browser evidence for F-28 as well.

## Required DAX model collation

The disposable TOM model uses `Latin1_General_100_BIN2` collation before loading
the fixture tables. Preserve this setting in any model claiming these exact
identifier semantics. With a case-insensitive model dictionary, source values
such as `prod` and `PROD` can be merged on import; `EXACT` cannot recover lost
case information afterward. Changing the DAX comparison or accepting the wrong
scope is not a conforming workaround.

Native Power BI Analysis Services 17.0.83.18 reproduced this issue on all eight
audit-critical cards (91 pass / 8 fail with default collation). The unchanged
APP-010 query passed with binary collation. The full corrected runs and their
source bindings are retained in `review/evidence/native-desktop-2026-09-11`.

The native adapters use Windows PowerShell-compatible TOM and ADOMD.NET client
assemblies. For the Power BI Desktop 2.157.1354.0 verification, Microsoft NuGet
packages `Microsoft.AnalysisServices` and `Microsoft.AnalysisServices.AdomdClient`
19.117.0 supplied the net472 assemblies; their MSAL dependencies must be present.
Use only a disposable local test session. This does not certify existing imported
models with a different collation, relationships, visual filters or source adapters.
