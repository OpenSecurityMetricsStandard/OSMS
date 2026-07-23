#!/usr/bin/env python3
"""OSMS Readiness Check — bundle generator and CI gate.

Reads the live catalog and the curated source taxonomy, emits
website/readiness/readiness_bundle.json (minified, deterministic) and prints
its SHA-256 for the page MANIFEST.

Usage:
  python3 tools/readiness/build_readiness_bundle.py \
      --catalog catalog/osms-catalog.yaml \
      --taxonomy tools/readiness/source_taxonomy.yaml \
      --out website/readiness/readiness_bundle.json
  python3 tools/readiness/build_readiness_bundle.py --check   # CI gate, writes nothing

Gate conditions (--check exits non-zero):
  * any data_sources string in the catalog not covered by the taxonomy mapping
  * any mapping target that is not a declared class
  * any declared class matched by zero cards
  * any card that resolves to zero source classes
"""
import argparse, collections, datetime, hashlib, json, sys
import yaml

ENVELOPE_MIN_SHARE = 0.8  # fields on >= 80% of cards form the provenance envelope


def load(catalog_path, taxonomy_path):
    cat = yaml.safe_load(open(catalog_path, encoding="utf-8"))
    tax = yaml.safe_load(open(taxonomy_path, encoding="utf-8"))
    return cat, tax


def resolve(cat, tax):
    cards = cat["cards"]
    mapping = tax["mapping"]
    class_ids = [c["id"] for c in tax["classes"]]
    class_set = set(class_ids)
    problems = []

    for tgt_list in mapping.values():
        for tgt in tgt_list:
            if tgt not in class_set:
                problems.append(f"mapping target not a declared class: {tgt}")

    resolved = []
    use = collections.Counter()
    for c in cards:
        classes = set()
        for s in c["data_sources"]:
            key = s.strip()
            if key not in mapping:
                problems.append(f"unmapped data_source: {key!r} (card {c['id']})")
                continue
            classes.update(mapping[key])
        if not classes:
            problems.append(f"card resolves to zero classes: {c['id']}")
        for x in classes:
            use[x] += 1
        direction = str(c.get("direction", "")).split(" - ")[0].strip()
        resolved.append({
            "id": c["id"],
            "name": c["name"],
            "domain": c["domain"],
            "type": c["type"],
            "priority": c["priority"],
            "mvp": c["mvp"],
            "unit": c["unit"],
            "calc": c["calculation_type"],
            "dir": direction,
            "mq": c["management_question"],
            "classes": sorted(classes),
            "fields": list(c["minimum_data_fields"]),
        })

    for cid in class_ids:
        if use[cid] == 0:
            problems.append(f"class matched by zero cards: {cid}")

    # provenance envelope = fields on >= ENVELOPE_MIN_SHARE of all cards
    freq = collections.Counter(f for c in cards for f in c["minimum_data_fields"])
    n = len(cards)
    envelope = sorted(f for f, k in freq.items() if k >= n * ENVELOPE_MIN_SHARE)
    return resolved, envelope, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", default="catalog/osms-catalog.yaml")
    ap.add_argument("--taxonomy", default="tools/readiness/source_taxonomy.yaml")
    ap.add_argument("--out", default="website/readiness/readiness_bundle.json")
    ap.add_argument("--check", action="store_true", help="gate mode: verify only, write nothing")
    args = ap.parse_args()

    cat, tax = load(args.catalog, args.taxonomy)
    resolved, envelope, problems = resolve(cat, tax)

    if problems:
        print("READINESS GATE: FAIL")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    print(f"READINESS GATE: PASS ({len(resolved)} cards, "
          f"{len(tax['classes'])} classes, {len(tax['mapping'])} mapped source strings)")
    if args.check:
        return

    bundle = {
        "schema": "osms-readiness-bundle/1",
        "catalog_version": cat["version"],
        "taxonomy_version": tax["taxonomy_version"],
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": {"cards": len(resolved), "classes": len(tax["classes"])},
        "envelope_fields": envelope,
        "groups": tax["groups"],
        "classes": tax["classes"],
        "cards": resolved,
    }
    blob = json.dumps(bundle, ensure_ascii=True, separators=(",", ":"),
                      sort_keys=False).encode("utf-8")
    with open(args.out, "wb") as f:
        f.write(blob)
    sha = hashlib.sha256(blob).hexdigest()
    print(f"wrote {args.out} ({len(blob)} bytes)")
    print(f"sha256 {sha}")
    print(f'MANIFEST entry: "readiness_bundle.json": "{sha}"')


if __name__ == "__main__":
    main()
