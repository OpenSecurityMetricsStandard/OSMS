# Method decisions proposed for the review candidate

Status: maintainer working draft; not a Review Board decision or a 1.0 approval.
Development may continue before the board starts. At review start, select a named
candidate commit and publish subsequent semantic changes with a change log and a
new card version. Do not silently replace the material reviewers are evaluating.

## Boundary decisions included in card 0.9.2-draft

These are explicit candidate choices where the previous prose had gaps or overlap.
The executable boundary profiles are in `reference/thresholds.py`; their regression
oracles exercise the exact boundaries independently of the catalog text.

| Card | Candidate choice | Why the choice needs review |
|---|---|---|
| SOC-063 | Green includes 90 and 110; Amber includes 75 and 125 | Removes overlap without changing the stated target band |
| STD-019 / STD-055 | Exactly 30 overdue days is Red; critical override takes precedence | Conservative closure of an unassigned boundary |
| STD-012 | Meeting plan is Green; any positive shortfall up to 25% is Amber | Fills the 0–10% shortfall and plan-equality gaps |
| STD-015 | Flat through +50% is Amber; >50% or high-EPSS/SLA override is Red | Resolves missing small changes and overlapping Red/Amber; flat is not improvement |
| STD-005 | Zero or negative verified return is Red; missing comparable trend/evidence is provisional | Covers negative values and prevents unsupported Green |

Relative comparisons require an explicit zero-baseline rule. STD-012 with plan<=0
has no relative assessment; STD-015 with a zero baseline treats zero as unchanged
and a positive value as Red. These are policy choices, not externally mandated
ISO limits. A threshold/profile change creates a visible trend break. Evaluate raw
values; display rounding must not move a value into another band.

## Decisions still required

1. **Confidence production:** define evidence-based dimension scoring, mandatory
   noncompensable validity gates, aggregation and minimum source/sample basis.
   Keep data quality separate from statistical uncertainty. No arbitrary numeric
   confidence rubric has been inserted into all 327 cards.
2. **Normalization and composites:** version each child's direction, bounds,
   normalization curve, output selection, missing-data treatment and weight set.
   Preserve both raw and normalized values. Fix weights before the reporting period.
3. **Typed contracts:** publish per-card input types, units, primary keys,
   nullability, population/time anchors, outputs and numerical methods. A schema
   presence check is not this contract. Multi-output cards require distinct named
   results, not one ambiguous scalar.
4. **Statistical/risk profiles:** select estimators per output, selection/censoring
   treatment, uncertainty methods, Monte Carlo generator and dependency/horizon
   assumptions. Review possible double-counting in STD-056 before changing it;
   the audit did not establish that the model is definitely wrong.
5. **Terminology:** decide whether SOC-023 measures false-alarm share or classical
   false-positive rate; distinguish AIM-011 attack prevalence/detection coverage
   from sensitivity and SOC-072 tolerance hits from calibration.
6. **Governance:** adopt the charter, member/COI rules, quorum, decision classes and
   freeze rule. No member identity, session, approval or date is fabricated here.
   Suggested freeze rule: every mandatory gate must pass; missing evidence leaves
   that gate unresolved. Reviewer counts alone do not establish review quality.
7. **Framework mappings:** bind the edition, relationship and rationale. Current
   ISO/IEC 27004 references are informative mappings, not conformity claims.
   No restricted ISO/DIN draft has been uploaded or incorporated in this work.
8. **Publication:** update the separate website from the complete GitHub-derived
   export, preserve schema identities and publish a versioned compatibility note.
   The new candidate `$id` does not claim that its URL is already deployed.

Each card should remain reviewable without a private book: where a normative
rubric currently depends on a guide reference, publish an original open rubric or
mark the calculation incomplete. Do not reproduce restricted source material.
