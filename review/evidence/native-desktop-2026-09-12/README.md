# Native Excel / DAX acceptance for F-03 and F-06

The eight requested calculation profiles pass on actual Microsoft Excel and Power BI Analysis Services. The technical findings are verified for this declared calculation-stage scope. Independent human review and board approval remain separate, unperformed activities.

## Source and observed results

Tested calculation source: [68a9a36e8443285a0018466b2846913c9c8ef803](https://github.com/OpenSecurityMetricsStandard/OSMS/commit/68a9a36e8443285a0018466b2846913c9c8ef803).
Profile bundle SHA-256: `e9164dd43862d7a9e50ad6a2e69bf93e3b66f3c0828e76eabb3208c75d6b6327`.

| Native engine | Required audit cases | Independent issue examples | Extra nonfinite probes |
| --- | ---: | ---: | --- |
| Microsoft Excel 16.0.20228, x86 | 99/99 pass; strict acceptance passes | 34/34 pass | 9/9 actual IEEE NaN/Infinity probes block numeric scores |
| Power BI Desktop 2.157.1354.0, x64; Analysis Services 17.0.83.18 | 99/99 pass; strict acceptance passes | 25/25 pass | 18/18 probes pass, plus 3/3 valid controls |

Every Excel formula case includes full recalculation, save, reopen and another full recalculation. The separate IEEE Excel probes test native input/rejection, and are not counted as full save/reopen formula cases.

DAX nonfinite probes distinguish nine text inputs, which produce a native calculated-table data rejection at query time, from nine native arithmetic expressions producing NaN or positive/negative Infinity, which return `invalid_input` and no numeric score. A valid control for each composite must pass. Missing libraries, connection failures and unrelated query errors are not accepted as input rejection.

A read-only GitHub CI job verifies the retained original bytes and runs the strict desktop acceptance validator against the regenerated current bundle. Original reports are retained in this repository. Linux validates evidence here; it does not execute Excel or DAX.

All original JSON bytes are preserved. `SHA256SUMS.txt` binds the retained evidence files. Reports retain engine versions, UTC timestamps, exact source and fixture hashes, actual outputs and independent expected values. Output-specific tolerances are in `desktop-case-manifest.json`; numeric discrepancies are not rounded into apparent passes.

## Native defect found and corrected

The first native DAX run on the preceding source passed 91 cases and failed eight case-sensitive scope exclusions. The default model dictionary merged `prod` and `PROD` before the existing `EXACT` comparison.

The runner now sets `Latin1_General_100_BIN2` model collation before loading data. Compatibility level is 1500 and culture is en-US. The unchanged queries now pass all 99 cases. The [91/8 baseline and focused collation diagnostic](../native-desktop-2026-09-11/) are retained, including the earlier successful Excel checkpoint. Deployments claiming these exact identifier semantics must preserve the model collation. Arbitrary existing imported Power BI models are outside this evidence scope.

The Windows wrapper also checks the native operating-system API rather than relying on an optional `OS` environment variable. The calculation formulas and independent expected results were not weakened.

## F-03 disposition

SOC-002 returns 15 hours for [2, 10, 20, 30]; CFG-002 returns nearest-rank 9 days for [1, 9, 20, 30]. Duplicate, singleton and two-value examples also pass on both engines. The required population includes SOC-002, APP-010, CFG-002, SOC-078 and STD-055 with all named outputs and their declared tolerances.

Technical disposition: verified and resolved for the requested calculation profiles, based on native execution and unchanged independent numerical expectations.

## F-06 disposition and weight interface

STD-068, STD-069 and STD-075 reject incomplete or invalid composite inputs without a numeric management score. Every numeric component is separately removed in the supplemental fixtures. Native NaN/Infinity, nonfinite text, out-of-range scores, missing/duplicate identities, wrong card versions and wrong contract hashes are covered by the reports.

These typed Excel/DAX profiles contain the normative weights as immutable expressions. They do not expose a dynamic `weight` input or silently apply caller-supplied weighting. Their `card_version` and `contract_hash` bind the complete profile, including its weight set; unknown bindings return n/a. The native evidence does not claim to have injected a negative dynamic weight into an API that has no such field.

| Profile | Fixed component weights |
| --- | --- |
| STD-068 | network_isolation 0.25; identity_separation 0.20; admin_separation 0.20; monitoring 0.15; restore_access_control 0.20 |
| STD-069 | exercise_frequency, scenario_realism, stakeholder_participation, lessons_learned_closure: 0.25 each |
| STD-075 | plan_quality 0.25; dependency_status 0.20; resource_availability 0.15; evidence_progress 0.25; risk_to_delivery 0.15 |

Technical disposition: verified and resolved for the requested typed calculation profiles. Raw-source preparation, arbitrary additional fields, legacy non-normative examples and independent semantic review are not newly certified by these native runs.

## Reproduction

Use the evidence commit checkout to obtain the supplemental probe tools; its calculation-source hashes must match the tested source and bundle above. Activate the isolated Python environment with the pinned repository dependencies before invoking the commands below. Installed Excel and a disposable local Power BI/Analysis Services session are required. TOM and ADOMD.NET net472 assemblies and required MSAL dependencies must be present; exact package and assembly hashes are in `execution-environment.json`.

Generate the bundle, then use the native wrapper for the two engines:

```powershell
python -X utf8 recipes/gen_recipes.py --emit-candidates --out recipes/out
./recipes/ci/run_desktop_acceptance.ps1 -Engine excel -Scope audit-critical
./recipes/ci/run_desktop_acceptance.ps1 -Engine dax -Scope audit-critical -Server localhost:PORT -TomAssembly PATH_TO_TABULAR_DLL -AdomdAssembly PATH_TO_ADOMD_DLL
python -X utf8 recipes/ci/audit_issue_examples.py --bundle recipes/out --out recipes/out/audit-issue-examples-excel.json
python -X utf8 tools/native_dax_issue_examples.py --bundle recipes/out --server localhost:PORT --tom-assembly PATH_TO_TABULAR_DLL --adomd-assembly PATH_TO_ADOMD_DLL --out recipes/out/audit-issue-examples-dax.json
python -X utf8 tools/native_dax_input_probe.py --bundle recipes/out --server localhost:PORT --tom-assembly PATH_TO_TABULAR_DLL --adomd-assembly PATH_TO_ADOMD_DLL --out recipes/out/native-nonfinite-dax.json
python -X utf8 review/evidence/native-desktop-2026-09-11/prepare_nonfinite.py
powershell.exe -NoProfile -File review/evidence/native-desktop-2026-09-11/probe_nonfinite.ps1 -RequestsPath recipes/out/nonfinite-requests.json -OutPath recipes/out/native-nonfinite-excel.json
```

Preserve original outputs before another run. The Windows execution used the isolated repository virtual environment with Python 3.13.7. The supplied 99-case acceptance profile does not certify all 327 cards or production adapters, relationships, visual filters, DirectQuery or capacity.

## Execution and responsibility

Date: 2026-09-12. Execution and technical assessment: Codex / Alya through Remote Desktop Commander, under Nico Wiegand's request to resolve F-03/F-06. Responsible maintainer: Nico Wiegand.

This is automated technical verification and disposition. It does not impersonate a human reviewer or claim independent review, charter adoption, board votes, production pilot outcomes or a full release. The other open audit issues retain their own external acceptance criteria.
