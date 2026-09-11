# Binary-outcome pilot intake — F-23

The executable intake evaluates small bases, delayed outcomes, late arrivals and
changes in cohort/campaign composition. It does not claim an empirical pilot has
occurred. Use it for a declared binary outcome such as a validated hit/miss; duration,
loss-distribution and composite-score pilots require their own estimator contracts.

Provide a JSON document with these top-level fields:

| Field | Required content |
|---|---|
| `pilot_id`, `scope_id`, `card_id`, `output_id` | Actual pilot, population and measured output |
| `source_catalog_sha256` | SHA-256 of the frozen catalog bytes |
| `definition_ref`, `normalization_ref`, `weight_profile_ref` | Versioned definitions; state and justify an unused normalization/weight profile explicitly |
| `source_evidence_ref`, `verifier_record_ref` | Retained source evidence and actual verification record; no sensitive records need to be published |
| `evidence_class` | `real_pilot` for actual observations or `synthetic_example` for test data |
| `population_kind`, `sampling_rationale` | `census` or justified `binomial_sample`; a sample additionally requires `independent_bernoulli_justified: true` |
| `minimum_observed_denominator` | Positive locally adopted evidence threshold; not a universal significance rule |
| `outcome_maturity_days`, `late_arrival_days` | Nonnegative versioned timing criteria |
| `snapshots` | At least two chronological snapshots of the same accumulated population |

Each snapshot supplies `as_of`, `source_receipt_ref`, `rows` and a reconciled
`receipt` containing `complete: true`, `record_count` and `rows_sha256`. The latter
uses canonical JSON: sorted keys, compact separators, UTF-8, preserved Unicode,
no nonfinite numbers. The source receipt and its upstream reconciliation must exist
independently; a locally calculated hash cannot prove the source was complete.

Each row supplies a stable pseudonymous `record_id`, `cohort_id`, `campaign_id`,
timezone-aware `event_at` and `known_at`, binary `outcome` or null, and `outcome_at`
or null. A corrected previously observed outcome needs `correction_evidence_ref`.
Previously eligible records may not silently disappear or change cohort. A changed
definition or sampling scope needs a new baseline; do not concatenate incompatible
periods. Future knowledge or outcomes are rejected.

```sh
python reference/pilot_evaluation.py --input actual-pilot.json --require-real --out pilot-evaluation.json
```

The report retains eligible, observed, pending, mature-pending and late counts,
outcome corrections, per-stratum rates, changes in the observed rate and a rate
standardized to the previous observed cohort/campaign mix. Missing comparison strata
produce no standardized result. A changed mix is reported even if the overall rate
stays constant. Wilson intervals are limited to the explicitly justified binomial
sampling model; a census receives no sampling interval.

For F-23 acceptance, an actual reviewer must evaluate whether the minimum base is
appropriate, which records were selected, whether outcomes have matured, how rates
change under plausible alternative mixes and what the real operational findings
mean. Meeting a minimum count does not establish stability, causality or Board
approval. Preserve the report, source reconciliation, environment and decision
reference with the frozen candidate. Synthetic tests verify this evaluator only.
