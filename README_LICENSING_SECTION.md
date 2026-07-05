<!-- Paste the two sections below into README.md -->

## Licensing

| Asset | License |
|---|---|
| Specification, catalog (YAML), taxonomy, principles, crosswalks | [CC BY 4.0](LICENSE) |
| Validator, scripts (`tools/`), JSON schema (`schema/`) | [MIT](LICENSE-CODE) |
| The book (official guide) | All rights reserved — not part of this repository's licenses |

Attribution format and trademark notice: see [NOTICE](NOTICE).
"OSMS" is an EU trade mark application (No. 019380729). The open licenses do not grant trademark rights.

## Validate it yourself

OSMS claims to be a *reproducible decision contract* — so don't take our word for it:

```bash
git clone https://github.com/OWNER/REPO && cd REPO
pip install pyyaml jsonschema
python tools/osms_validate.py catalog/ --schema schema/osms-card.schema.json
```

The validator enforces the card contract plus 16 semantic rules (ID uniqueness,
parent/child integrity, rollup cycle detection, helper cards never board-reportable,
direction/threshold consistency, fail-closed denominators, data-confidence gates,
decision chains, version-break rules, evidence fields, <=4-step drilldown lineage).
Every pull request runs the same checks in CI.
