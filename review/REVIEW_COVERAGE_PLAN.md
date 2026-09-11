# Review coverage plan for the maintainer candidate

This is a technical review plan. Member identities, assignments, quorum votes and
meeting dates are recorded when they exist. They are not prerequisites for the
maintainer to correct or release an identified 0.x draft.

[Pre-board dossiers and verification](PREBOARD_READINESS.md) provide the executable
327-card review packet and per-association mapping material. The
[charter proposal](BOARD_CHARTER_PROPOSAL.md) is ready for actual adoption; it is not
a record of an adopted charter or a completed review.

Review a named source commit and its validation artifacts. Evaluate semantic
changes against the previous named definition and retain any trend-break decision.
Subsequent changes remain possible and receive a new identified review revision.

| Review area | Required expertise | Material to assess | Evidence to record |
|---|---|---|---|
| Management usefulness | Relevant domain and accountable metric owner | One question/decision, outcome relevance, scope, guardrails | Card/output IDs, findings and rationale |
| Calculation semantics | Measurement/statistics | Population, estimand, units, empty/invalid states, percentile definition, normalization, confidence | Independent recomputation and negative cases |
| Platform implementation | SQL/SIEM/BI/spreadsheet implementation | Typed contract, query/formula, case selection, time/identity handling, capacity limits | Engine/version, source/profile hashes, observed case results |
| Traceability | Assurance/audit and data engineering | Source snapshot, input lineage, independent contribution reconstruction, classifications | Reconciled source totals and retained evidence |
| Review process | Maintainer/review coordination | Candidate identity, independence/conflicts, unresolved findings and version changes | Actual decision records and follow-up ownership |

Inspect every P0 card's semantics and every known high-severity finding; do not
infer coverage from reviewer counts or one passing generic example. Give duration,
ratio/quantity exceptions, composite, penalty, risk, ranking and multi-output
profiles distinct method attention. Reuse the common arithmetic-kernel evidence
where the binding contract is identical; separately check each card's population,
units, inputs, output selection and gates.

The generated `execution-coverage.json` lists all 327 cards and eight dialects.
`conformance-matrix.json` adds matching runtime reports and exact case/output
coverage. Missing profiles, untested engines and unresolved raw-source adapters
remain explicit review work. Synthetic fixtures establish calculation behavior;
pilot observations establish empirical usability and data availability.

All 119 additional prepared-observation profiles are implemented. Remaining
source-adapter, engine-execution and external evidence tasks are recorded in
[IMPLEMENTATION_BACKLOG.json](IMPLEMENTATION_BACKLOG.json).
[IMPLEMENTATION_CANDIDATE.json](IMPLEMENTATION_CANDIDATE.json) maps the working
changes to the existing audit issue numbers, categories, severities and card IDs.
Its candidate commit fields identify the published implementation history.
Actual issue closure and acceptance evidence are recorded in GitHub.

A finding can close when its own acceptance criterion is met and the relevant
source/evidence is identified. A partial implementation does not close a broader
criterion. F-28 remains externally handled after the repository export is updated;
its acceptance evidence includes deployed version and a full field/behavior match.
