# Native desktop verification — 2026-09-11

Microsoft Excel 16.0.20228 (32-bit) executed all 99 existing audit-critical cases for F-03/F-06 on source commit b19a91e778eaaa61a71a3fd78e72439eec2d707d. The original report and separate acceptance check both pass (99/99, zero failures). Each fixture was recalculated, saved, reopened and recalculated again by the unchanged repository runner.

The original JSON report contains actual outputs, fixture hashes, source hashes, engine version and UTC execution timestamps. The case manifest contains the independent expected outputs and tolerances. These are native Excel runtime results over synthetic fixtures.

Executed by Codex / Alya through Remote Desktop Commander under the maintainer request. No independent human review or board approval is claimed. Native DAX acceptance and the exact issue-example supplements remain pending at this checkpoint. F-03/#4 and F-06/#7 remain open.
