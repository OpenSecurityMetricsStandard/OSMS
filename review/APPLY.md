# Apply and review the current candidate

Use [IMPLEMENTATION_APPLY.md](IMPLEMENTATION_APPLY.md) and the current GitHub pull
request. [EXECUTION_VALIDATION.md](EXECUTION_VALIDATION.md) explains verification
scope; [RELEASE_0.9.2.md](RELEASE_0.9.2.md) describes migration and release gates.
The root [README](../README.md#validate-it-yourself) contains the canonical
validation commands and public repository URL.

Earlier audit ZIPs, patches and import bundles describe a previous handoff that
was already published through PR #2. Do not apply them over the current repository
or overwrite its branches. Historical import identity is documented in
[GITHUB_IMPORT.md](GITHUB_IMPORT.md#published-commit-identity). New changes retain
actual fixing commit IDs and their own CI evidence.

Merge only the identified verified candidate. Migrate STD-016 loaders and existing
reference databases explicitly; source-creation SQL is not an in-place database
migration. The website integration is handled externally after repository update.
Maintainer 0.x changes do not require a Board vote. Stable promotion uses the
separately adopted formal review process.
