# Method decisions for the OSMS 0.9.2 maintainer draft

Status: maintainer working draft; not a Review Board decision or a 1.0 approval.
Development may continue before the board starts. At review start, select a named
candidate commit and publish subsequent semantic changes with a change log and a
new card version. Do not silently replace the material reviewers are evaluating.

## Maintainer boundary decisions included in card 0.9.2

These choices are adopted for the 0.9.2 maintainer draft under the maintainer
development authority in REVIEW_PROCESS.md. They resolve gaps and overlaps in the
previous prose. They can be revised through versioned changes before or during
later board review; that later review is not a prerequisite for using this draft.
The executable boundary profiles are in `reference/thresholds.py`; their regression
oracles exercise the exact boundaries independently of the catalog text.

| Card | Candidate choice | Why the choice needs review |
|---|---|---|
| SOC-063 | Green includes 90 and 110; Amber includes 75 and 125 | Removes overlap without changing the stated target band |
| STD-019 / STD-055 | Exactly 30 overdue days is Red; critical override takes precedence | Conservative closure of an unassigned boundary |
| STD-012 | Meeting plan is Green; any positive shortfall up to 25% is Amber | Fills the 0–10% shortfall and plan-equality gaps |
| STD-015 | Flat through +50% is Amber; >50% or high-EPSS/SLA override is Red | Resolves missing small changes and overlapping Red/Amber; flat is not improvement |
| STD-005 | Zero or negative verified return is Red; missing comparable trend/evidence is provisional | Covers negative values and prevents unsupported Green |
| VAL-001 | Applicable scope <95% is Amber; applicable remediation <100% is Red; unmanaged critical findings override n/a | Makes the previously incomplete worst-of rule executable without inventing an 85% boundary |
| SOC-078 | Noncritical SLA breach is Amber through 150%; >125% triggers early escalation; >150% or critical appetite breach is Red | Closes the gap between SLA and the former +25% wording; critical internet exposure is bounded by the lower of SLA and 72 h |

Relative comparisons require an explicit zero-baseline rule. STD-012 with plan<=0
has no relative assessment; STD-015 with a zero baseline treats zero as unchanged
and a positive value as Red. These are policy choices, not externally mandated
ISO limits. A threshold/profile change creates a visible trend break. Evaluate raw
values; display rounding must not move a value into another band.

## Additional candidate methods

STD-011 now defines numeric confidence profile `dq-checks/1`: five evidence-backed
check pass fractions, fixed weights, mandatory dimensions and noncompensable gates.
STD-003 now states stable competition ranks and the complete all-zero population
boundary. Both changed definitions advance to card version 0.9.2.

`reference/assurance.py` implements those methods plus fixed-anchor normalization,
independent weighted contributions and DSPS reconstruction, design-limited Wilson
intervals and aggregation of complete joint annual-loss draws. The open ordinal
rubrics are in `reference/RUBRICS.md`; 12 cards now resolve their guide references
inside this repository. Numeric anchors, source registers and empirical model
parameters remain explicit application inputs, not inferred sample defaults.

SOC-023, AIM-011 and SOC-072 retain their formulas and denominators with names and
interpretation limits matching what is measured. STD-024 is an event rate per day,
not a count. All cards explicitly retain draft lifecycle status.

## Work still requiring implementation or real evidence

1. Validate application source adapters against the complete calculation layer:
   207 canonical quotient cards, 119 prepared-observation cards and SOC-003.
   Calculation coverage does not establish source completeness or authenticity.
2. Supply versioned source/check registers and risk-appetite anchors in applications;
   verify all native engine implementations against the frozen profile/input set.
3. Calibrate risk models and evaluate sampling, selection/censoring and control-credit
   assumptions with real evidence. The pilot remains a separate empirical activity.
4. Adopt actual Board membership, conflict rules, quorum and decision records when
   that review body is established. Maintainer 0.x development continues meanwhile.
5. Complete individual framework mapping editions, relationships, rationale and
   evidence under `catalog/framework-mapping-policy.yaml`.
6. Validate source-dimension population; the three long lineage paths now fit the
   four-node path convention without removing their axes or evidence requirements.
7. Update the externally handled website after repository integration and verify its
   full schema, field, output-status and execution-profile behavior.

Current evidence and remaining acceptance requirements are recorded in
`review/EXECUTION_VALIDATION.md`.
