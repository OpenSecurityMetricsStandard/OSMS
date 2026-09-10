# Apply and review this candidate

The supplied handoff contains a complete source archive, a patch against the audited
base commit, the change register and local verification logs. Nothing was pushed.

For an existing clone, start from a clean checkout of the audited base:

```bash
git switch -c review/osms-audit-remediation 747cd28fb0b6728ebadbe6c477722d166b5b40b5
git apply --check /path/to/OSMS_Auditkorrekturen.patch
git apply /path/to/OSMS_Auditkorrekturen.patch
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements-checks.txt
python -m unittest discover -s tests -v
```

If main has advanced, apply in a separate branch and reconcile conflicts rather
than replacing current work. A source ZIP is also included for direct inspection.
The patch preserves the catalog's existing CRLF line endings; Git may print
whitespace notices unless `core.whitespace` includes `cr-at-eol`.

Review `METHOD_DECISIONS.md` before adopting the six threshold changes. Update
STD-016 loaders for `mitigated_at`. Migrate existing reference databases explicitly;
the supplied SQL creates a new database and does not alter an existing deployment.
Update consumers for `curated_candidate`, mapping-required sentinels and the new
SQL reconciliation status names. The website needs a separate integration/deployment.

The stable 1.x release guard must be replaced by the adopted board/evidence gate
before stable promotion. It does not block continued local draft development.
