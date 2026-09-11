# Start the OSMS review

Review a frozen candidate, not a moving branch. The packet contains 327 card dossiers,
the calculation/profile hash, every source relationship and a file manifest. Generation
is not a review decision. The charter and assignment depths remain proposals until
the actual Board adopts them.

## First session

1. Record the exact candidate commit, packet manifest and charter revision.
2. Adopt or explicitly revise the charter. Record actual members, expertise,
   interests, recusals, quorum, vote, dissent, mandatory gates and dated checkpoints.
3. Assign two independent reviewers to the 120 prepared-observation/incident
   profiles. Assign the remaining P0 cards for substantive population and decision
   review. Shared quotient-kernel tests do not replace each card's assessment.
4. Prioritize STD-001/001a/001b, STD-002a, STD-003, STD-006, STD-011, the duration
   estimators and the F-03/F-06 cards. Then review the remaining complex profiles
   and the source relationships with withdrawal or narrowing proposals.

The proposed gate truth table is deliberately simple:

| Mandatory gates | Result |
|---|---|
| Every gate passes, with actual evidence and valid review/quorum | Eligible for the recorded promotion decision |
| Any one gate fails | Promotion blocked |
| Any gate is pending or lacks evidence | Promotion blocked |
| A finding is deferred or accepted as risk | Still unresolved for any mandatory gate it violates |

## For each assigned card

Open `cards/CARD-ID.md`. It contains the management question, population, formula,
units, thresholds, guards, independent examples, required test IDs, native evidence
and the proposed source relationships. Record the population, calculation and
decision assessment separately. For a shared implementation, independently check
the input selection and output contract as well as the common kernel.

For mappings, check the exact source and selected edition, measured facet,
unsupported requirements and applicability. An abstract is not a clause review;
a dataset label is not validated threat coverage. `mapping-withdrawal-proposals.json`
contains proposed removals/reassignments; these have not been silently applied to
the catalog. `source-evidence-queue.md` groups the remaining source work to avoid
repeated procurement while retaining a separate decision for every card.

## Record actual decisions

From the candidate checkout, after generating the packet:

```sh
python tools/review_acceptance.py --packet recipes/out/board-packet --prepare-record --out board-review-record.json
python tools/review_acceptance.py --packet recipes/out/board-packet --record board-review-record.json --out board-review-status.json
# Required only for formal promotion; an empty/prepared record must fail.
python tools/review_acceptance.py --packet recipes/out/board-packet --record board-review-record.json --require-complete --out board-review-status.json
```

The record contains `members`, `adoption`, `assignments`, `reviews` and `gates`.
Members need stable IDs, actual names, declared expertise and an OSMS issue/PR
declaration reference. Adoption needs participants, recusals, date, disposition,
rationale, dissent, the six named gates, their failure consequence and checkpoints
with scheduling reasons. Every review binds its card hash and records actual case
IDs, independence, findings and disposition. A deferred/accepted-risk review needs
an owner, follow-up criterion and date. The validator reports missing information;
it does not authenticate a person or turn a string into an actual approval.

Use `tools/desktop_acceptance.py` for the missing native desktop evidence and
`review/PILOT_INTAKE.md` for binary-outcome pilot observations. The real execution,
pilot and Board records are the remaining inputs; no generated example counts as
their completion. F-28 is handled externally.
