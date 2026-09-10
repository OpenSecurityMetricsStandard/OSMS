-- SPDX-License-Identifier: MIT
-- DuckDB/PostgreSQL. normalization_input is a typed one-row profile/input table.
-- Numeric columns: raw_value, red, target, red_low, target_low, target_high, red_high.
-- Text: direction, profile_id, profile_version, card_id, card_version, output_id, unit, evidence_ref.
-- Frozen profile identity and authorization must be verified by the caller.
WITH validated AS (
 SELECT *, CASE WHEN raw_value BETWEEN -1e15 AND 1e15
  AND LENGTH(TRIM(profile_id))>0 AND LENGTH(TRIM(profile_version))>0
  AND LENGTH(TRIM(card_id))>0 AND LENGTH(TRIM(card_version))>0
  AND LENGTH(TRIM(output_id))>0 AND LENGTH(TRIM(unit))>0 AND LENGTH(TRIM(evidence_ref))>0
  AND ((direction='higher' AND red BETWEEN -1e15 AND 1e15 AND target BETWEEN -1e15 AND 1e15 AND red<target)
    OR (direction='lower' AND red BETWEEN -1e15 AND 1e15 AND target BETWEEN -1e15 AND 1e15 AND target<red)
    OR (direction='band' AND red_low BETWEEN -1e15 AND 1e15 AND target_low BETWEEN -1e15 AND 1e15
      AND target_high BETWEEN -1e15 AND 1e15 AND red_high BETWEEN -1e15 AND 1e15
      AND red_low<target_low AND target_low<=target_high AND target_high<red_high))
  THEN TRUE ELSE FALSE END AS valid_profile FROM normalization_input
), normalized AS (
 SELECT *, CASE WHEN direction IN ('higher','lower') THEN 100.0*(raw_value-red)/NULLIF(target-red,0)
  WHEN raw_value BETWEEN target_low AND target_high THEN 100.0
  WHEN raw_value<target_low THEN 100.0*(raw_value-red_low)/NULLIF(target_low-red_low,0)
  ELSE 100.0*(red_high-raw_value)/NULLIF(red_high-target_high,0) END AS unbounded_posture
 FROM validated
)
SELECT CASE WHEN valid_profile THEN GREATEST(0.0,LEAST(100.0,unbounded_posture)) ELSE NULL END AS posture_score,
 CASE WHEN valid_profile THEN 'ok' ELSE 'invalid_profile' END AS evaluation_status
FROM normalized;
