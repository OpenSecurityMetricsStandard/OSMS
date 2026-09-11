# Review Board charter proposal

Status: proposed for adoption at formal review start. No membership, vote, meeting
or approval is implied. This proposal operationalizes `REVIEW_PROCESS.md`; adoption
must record any changes to it.

## Mandate and baseline

Assess whether each reviewed card supports a clear management decision and whether
its population, formula, inputs, confidence, units, gates, implementation evidence
and versioning support that decision. Review a named source commit, catalog version,
profile bundle hash and packet manifest. A changed baseline invalidates affected
reviews until their impact has been assessed; unaffected evidence may be reused only
when its dependency hashes still match.

## Participation and coverage

At least three active members participate in a formal decision session, consistent
with the existing review process. Record actual expertise coverage in measurement,
security operations/risk, data engineering/implementation and assurance. One person
may cover more than one area. Each participant declares relevant interests; the
subject's implementer must not be its sole independent verifier. Record recusals,
remaining quorum and the independent assessment used for each affected decision.

Assign all P0 cards and critical/major findings before review starts. Allocate the
other cards by domain and calculation family; every reviewed card needs its own
population and decision assessment even when kernel tests are shared. Track
substantive semantic review separately from a comment or automated check. Use the
327-row generated review matrix; do not populate reviewer fields with placeholders
that would count as real assignments.

## Decisions and evidence

For each finding or normative method choice, record the candidate commit, card and
output IDs, proposed correction, alternatives and consequences, evidence references,
independent verifier, date, participants, quorum, dissent and reasoned disposition.
Allowed formal dispositions remain accepted, rejected, deferred and accepted-risk.
A deferral retains an owner, follow-up criterion and target review point. Accepted
risk does not erase an unmet mandatory gate or claim that an implementation passed.
Publish the necessary rationale and technical evidence. Retain personal contact,
internal coordination and irrelevant tooling details outside public review records.

## Proposed mandatory promotion gates

Each mandatory gate must pass; dates and aggregate percentages cannot override a
failed gate. Adopt the final combination explicitly before formal review begins.

- Zero unresolved critical findings and no known wrong primary calculation or
  unsafe confidence/decision gate in the declared release scope.
- All P0 cards receive substantive independent review; critical and major findings
  have a recorded formal disposition and evidence consistent with that disposition.
- Supported platform claims identify actual native runtime, version, scope,
  independently expected outputs, rejection cases and population capacity. Any
  reduced release scope is explicit and versioned, not silently counted as support.
- Reproducible source-bound catalog/schema/profile artifacts and complete issue and
  decision traceability; version changes include migration and trend-break guidance.
- Pilot limitations and unresolved framework relationships are explicit. Stable
  maturity claims require the applicable actual empirical and review evidence.
- Actual quorum, independence checks, website/version alignment and review summary
  are recorded. A maintainer draft remains available under the separate 0.x rules.

## Adoption record to complete at the meeting

Candidate commit and manifest; charter revision; participants and expertise;
independence/recusal decisions; quorum; adopted gates; timetable and checkpoints;
assignment-register reference; vote and dissent; publication decision and rationale.
