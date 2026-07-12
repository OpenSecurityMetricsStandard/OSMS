# Field conventions

## `timestamp` (envelope field)

`timestamp` is the technical observation/extraction time of the source record -
the moment the row was captured from the source system. It exists for audit and
data-quality purposes only.

Business event times always use specific fields such as `detected_at`,
`occurred_at`, `contained_at`, or `fix_deploy_timestamp`. These specific fields
are the only time fields that formulas compute on.

Invariant: the bare `timestamp` field never enters a formula. This is enforced
by `tools/formula_audit.py` and holds for all 327 cards.

## Event-time suffixes

Specific event times use `*_at` (point in time an event occurred) or
`*_timestamp` (system-stamped moments such as `fix_deploy_timestamp`). Both are
business fields; new cards should prefer `*_at` for events.
