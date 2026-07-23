# OSMS Readiness Check — data pipeline

The Readiness Check (`website/readiness/`) resolves a visitor's selected source
systems against the catalog, entirely client-side. This folder holds the data
pipeline behind it.

## Files

| File | Role |
|---|---|
| `source_taxonomy.yaml` | Curated mapping: every `data_sources` string in the catalog -> canonical system class. 13 groups, 59 classes. Versioned source of truth for the check. |
| `build_readiness_bundle.py` | Generator and CI gate. Reads catalog + taxonomy, emits `website/readiness/readiness_bundle.json` and prints its SHA-256. |
| `curate_taxonomy.py` | The rule set that produced the taxonomy (regex rules + context-verified overrides). Re-run it only for large re-curations; day-to-day, extend `source_taxonomy.yaml` directly. |
| `allow_readiness.json` | Artefact-bound leak_scan exemption for the standard CSS/HTML `placeholder` vocabulary on the page. |

## Regenerating after a catalog change

```
python3 tools/readiness/build_readiness_bundle.py \
    --catalog catalog/osms-catalog.yaml \
    --taxonomy tools/readiness/source_taxonomy.yaml \
    --out website/readiness/readiness_bundle.json
```

The script prints a `MANIFEST entry:` line. Paste that SHA-256 into the
`MANIFEST` constant near the top of the `<script>` block in
`website/readiness/index.html`, then deploy both files together. The page
fetches the bundle with `?v=<sha12>` (cache busting) and verifies the full
hash via SubtleCrypto before parsing.

## Gate mode (CI)

```
python3 tools/readiness/build_readiness_bundle.py --check
```

Exits non-zero when:

* a `data_sources` string in the catalog has no taxonomy mapping (the message
  names the exact string and card — add one mapping line to fix),
* a mapping points to an undeclared class,
* a declared class matches zero cards,
* a card resolves to zero source classes.

Suggested job for `.github/workflows/validate.yml`:

```yaml
  readiness-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install pyyaml
      - name: Readiness taxonomy gate
        run: python3 tools/readiness/build_readiness_bundle.py --check
```

## Scoring semantics (as shipped on the page)

* A card's source classes are the union of the classes of all its
  `data_sources` strings.
* **candidate** — at least one of the card's source classes is selected.
* **likely computable** — a strict majority of its source classes is selected
  (`matched * 2 > total`).
* **confirmed** — the visitor ticked every card-specific `minimum_data_fields`
  entry in the drilldown (display overlay; does not change the majority math).
* The six provenance-envelope fields (`scope_id`, `source_system`,
  `evidence_ref`, `period_start`, `period_end`, `record_id`) sit on effectively
  every card and are confirmed once, globally, not per card.
* Catalog sources are typical evidence locations, not strict prerequisites —
  which is why the page never claims more than candidate/likely before field
  confirmation. This is stated on the page itself.

## Privacy

The check is fully client-side: selections live in `localStorage` on the
visitor's device, the report is built in the browser via the already-vendored
SheetJS, and the only network traffic is the bundle fetch plus the site's
standard anonymous page beacon.
