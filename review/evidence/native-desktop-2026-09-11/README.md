# Native desktop verification - 2026-09-11/12

## Native Excel results

Microsoft Excel 16.0.20228 (32-bit) executed the unchanged generated formulas on source commit b19a91e778eaaa61a71a3fd78e72439eec2d707d.

- 99/99 existing audit-critical cases passed; the strict acceptance validator reports ok=true.
- 34/34 supplemental cases passed: exact SOC-002 median 15 h and CFG-002 nearest-rank 9 d examples, duplicate/singleton/two-value samples, every missing composite numeric component, nonfinite text and above-range scores.
- 9/9 actual IEEE NaN/positive-Infinity/negative-Infinity injection checks blocked a numeric composite score (native #N/A).

The 133 formula cases were fully recalculated, saved, reopened and recalculated by actual Excel. The additional 9 IEEE probes are input/rejection checks, not 9 additional full formula-profile executions. Fixtures are synthetic.

Original JSON bytes are retained; .gitattributes disables text normalization for this evidence directory. Reports include actual values, fixture/source hashes, product versions and UTC timestamps. desktop-case-manifest.json supplies the independent expected outputs and tolerances for the initial 99 cases. Supplemental reports contain their own fixtures and hand-specified expectations.

The supplemental source snapshot is audit_issue_examples-original.py; the runnable repository entry point is recipes/ci/audit_issue_examples.py. The IEEE helpers prepare_nonfinite.py and probe_nonfinite.ps1 reproduce the extra injection probes.

## DAX checkpoint

Native DAX acceptance is pending. The installed legacy Excel Power Pivot engine accepted a simple model smoke query but rejected the actual generated OSMS strict-equality syntax. That diagnostic is not an OSMS conformance pass. The separate Power BI Desktop runtime is being installed for actual acceptance; recipes have not been weakened to fit the legacy engine.

## Responsibility and scope

Executed by Codex / Alya through Remote Desktop Commander at maintainer Nico Wiegand's request. Automated technical verification is distinguished from independent human review and board approval; neither is claimed. These results certify the stated fixtures and source bindings, not production data or a full release. F-03/#4 and F-06/#7 remain open until the native DAX evidence and final disposition are complete.
