# Apply and review this candidate

The audit branch has been published through the GitHub connector. Use the current
branch/PR and its recorded commit links. Earlier handoff bundles contain different
commit metadata; do not use them to overwrite the published branch. Details:
[GITHUB_IMPORT.md](GITHUB_IMPORT.md#published-commit-identity).

For a GitHub handoff that preserves the remediation commit SHA, prefer the Git
bundle/importer described in [GITHUB_IMPORT.md](GITHUB_IMPORT.md). The patch route
below remains useful for inspection or manual adaptation, but creates a different
commit when the recipient commits the applied changes.

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
