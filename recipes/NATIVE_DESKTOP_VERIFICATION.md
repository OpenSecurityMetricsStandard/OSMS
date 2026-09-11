# Native Microsoft Excel and DAX verification

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

Website artifact comparison is separate. After external deployment, retain its
catalog, schema, execution profiles and a JSON attestation with `source_commit`,
`catalog_url`, `schema_url`, `profiles_url`, `deployment_evidence_ref`. Run
`tools/verify_website_contract.py --help` for comparison arguments. This checks the
supplied artifacts and attestation, not their authenticity or live browser behavior;
retain the actual deployment and browser evidence for F-28 as well.
