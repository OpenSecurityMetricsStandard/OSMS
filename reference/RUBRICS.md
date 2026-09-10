# Open ordinal rubrics and normalization profiles

This repository defines the following maintainer-draft reference vocabulary. No
separate guide is needed to interpret these labels. Application-specific anchors,
BIA evidence, accountable approval and profile versions remain part of the input
record; organizational risk appetite cannot be inferred from an engine sample.

| Level | Asset/service criticality | Data sensitivity | Residual risk |
|---|---|---|---|
| 1 | Limited local impact with a documented routine recovery path | Public or approved for public disclosure | Within approved appetite, with effective evidenced controls |
| 2 | Contained business disruption requiring coordinated recovery | Internal information with restricted routine distribution | Within appetite, but with documented control or uncertainty concerns |
| 3 | Major disruption of an important service or material exposure | Confidential information requiring a defined authorized population | Above approved appetite; treatment or a time-bound risk decision required |
| 4 | Critical service, crown-jewel asset or impact exceeding the organization's critical BIA boundary | Restricted information whose compromise exceeds the organization's critical impact boundary | Above a critical appetite boundary or subject to a mandatory escalation gate |

Select the highest applicable documented level. Record the reason, classification
owner, as-of date, BIA/appetite/profile version and evidence reference. Missing or
conflicting classification remains invalid input. It must not become level 1.
Local numeric impact boundaries belong to the versioned BIA/appetite profile.
These labels are ordinal classifications, not probabilities or currency amounts.

A card that explicitly multiplies a level from 1 to 4 retains that numeric level.
A card that explicitly requires min–max normalization of that scale uses
`(level - 1) / 3` for [0,1], or `100 * (level - 1) / 3` for [0,100]. A normalized
zero denotes the bottom of this ordinal scale; it does not establish absence of
risk. Do not substitute these ordinal transforms for a card's measured-value
posture transform. A stored normalized input preserves its raw level and rubric
version so reconciliation can reproduce the transformation.

For measured-value posture, `reference/assurance.py::normalize` implements linear
higher-is-better, lower-is-better and target-band profiles. Each child specifies
its card/output version, unit, good and bad anchors, evidence and profile version.
Zero-width or inverted anchors fail. No current sample minimum or maximum is
silently substituted for fixed risk-appetite anchors. Clipping affects posture
only; preserve the uncapped raw value and apply the card's raw-value gates.

`reference/assurance.py::dsps` recomputes all 14 normalized child contributions with
the weights from STD-001, then applies exactly one evidenced TSP and EDP from the
same context. Missing profiles, changed child versions, duplicate penalties or
incorrect cached contributions invalidate the evaluation. These generic routines
do not supply an organization's normalization anchors or prove source authenticity.
