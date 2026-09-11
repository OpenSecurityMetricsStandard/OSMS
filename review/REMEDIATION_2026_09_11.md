# Review preparation — 2026-09-11

This revision addresses the remaining repository work for F-03, F-06, F-23, F-26,
F-27 and F-32. F-28 is handled externally. It does not create a release or record
an actual Board approval.

| Finding | Added in this revision | Remaining acceptance evidence |
|---|---|---|
| F-03 / F-06 | Native desktop case fingerprints, source freshness checks, execution timestamps, a Windows runner wrapper and strict verification of complete case/output evidence | Actual Excel and DAX runs on the declared native products, versions and scope; retained original reports and verification/disposition record |
| F-23 | Reconciled binary-outcome pilot intake; small-base statements, pending/mature outcomes, late arrivals, corrections and cohort/campaign standardization; sampling intervals only under a justified model | Actual pilot snapshots, source reconciliation and independent evaluation of plausible composition changes, usability and stability |
| F-26 | Executable charter/adoption/decision-record checks; each mandatory gate must pass; recusals, quorum, timetable, follow-up and evidence binding | Actual members, adopted charter and gate contract, decision session and recorded dispositions |
| F-27 | 186 additional primary-source assessments, giving 948 assessed and 201 outstanding associations; compound legal/source validation; versioned ATT&CK/KEV/EPSS relationships; 86 withdrawal/reassignment proposals; reproducible report | Remaining source comparisons and actual responsible mapping reviews; approval and catalog changes remain separately recorded |
| F-32 | 327 expanded dossiers with source assessments and fixture IDs; two independent reviewers proposed for all 120 prepared-observation/incident profiles; assignment and substantive-review coverage validation | Actual independent reviewer assignments, interests/recusals, substantive review records and justified timetable |

## Reproducible checks

The repository regression suite tests legal/compound citation preservation,
source/component drift, missing applicability and dataset-population requirements,
incomplete/stale/emulated desktop reports, incorrect outputs, small pilot bases,
case-mix distortion, future data, silent attrition, quorum loss and individual gate
failure. Synthetic records are identified as test fixtures and do not establish
actual pilot, native desktop or Board evidence.

```sh
python -m unittest discover -s tests -v
python tools/osms_validate.py catalog/osms-catalog.yaml --taxonomy catalog/taxonomy.yaml --domains catalog/domains.yaml --expect-count 327
python tools/framework_mappings.py --require-triaged --out framework-mapping-register.json
python tools/build_mapping_report.py --check
python recipes/gen_recipes.py --emit-candidates --out recipes/out
python tools/build_board_packet.py --bundle recipes/out --out recipes/out/board-packet
python tools/desktop_acceptance.py --plan-only --out recipes/out/desktop-case-manifest.json
```

Local generation produced 327 dossiers with zero structural errors and 5,279
planned native cases. The planned cases are unexecuted until an actual engine
report exists. Recipe CI supplies fresh native evidence for its supported engines
at the published candidate; older bundle reports must not be relabeled as current.
Full source-adapter and production/capacity conformity are separate from fixture
execution. STD-002a retains its stated minimum population and platform limits.

The remaining mapping work is explicit: 180 authorized standard-clause comparisons,
12 CISA ZTMM primary-text assessments, seven unidentified publications/local
policies, one EBA guidance comparison and one unresolved CTID/Atomic source. The
83 ISO/IEC 27004 associations remain limited to the public abstract. No unpublished
successor is evaluated. Original EU instruments are selected comparison baselines,
not a determination of current consolidated or national legal applicability.

## Review entry points

- [Reviewer guide](REVIEWER_START_HERE.md)
- [Source assessment and proposed dispositions](framework/F27_ASSESSMENT.md)
- [Native Excel/DAX execution and acceptance](../recipes/NATIVE_DESKTOP_VERIFICATION.md)
- [Pilot intake contract](PILOT_INTAKE.md)
- [Charter proposal](BOARD_CHARTER_PROPOSAL.md)

The strict assessment, actual-review and formal-promotion gates intentionally
remain unsatisfied where their required evidence is absent. A technical preparation
does not close a broader finding or supply a missing responsible person's decision.
