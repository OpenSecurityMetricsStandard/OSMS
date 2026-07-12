#!/usr/bin/env python3
"""ES|QL engine verification for OSMS recipe candidates.

Fixture pass: load each fixture card's rows into a real Elasticsearch index,
run the candidate ES|QL query, compare against the card's expected values.
Empty pass: every candidate query must execute (correct syntax and column
references) against an empty, correctly typed index.

Usage:
  python3 recipes/ci/esql_runner.py --out recipes/out --es http://localhost:9200
  python3 recipes/ci/esql_runner.py --out recipes/out --dry-run
"""
import json, re, os, sys, time, argparse, urllib.request, urllib.error

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="recipes/out")
ap.add_argument("--es", default="http://localhost:9200")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--timeout", type=int, default=180)
A = ap.parse_args()

CAND = json.load(open(os.path.join(A.out, "ci_candidates.json")))
FIX = json.load(open(os.path.join(A.out, "fixtures.json")))
CAT = {c["id"]: c for c in json.load(open(os.path.join(A.out, "catalog.json")))}

def es_type(field):
    if field.endswith("_at") or field.endswith("_timestamp") or field.startswith("period_") or field.startswith("date_"):
        return "date"
    if field.endswith("_flag") or field in ("internet_facing",) or field.startswith("is_"):
        return "boolean"
    if re.search(r"(_value|_score|^weight$|_weight|_amount|_hours|_days|_cost)", field):
        return "double"
    return "keyword"

def adapt(query, index, params=None):
    q = re.sub(r"\bFROM\s+\w+", "FROM " + index, query, count=1)
    for k, v in (params or {}).items():
        tok = "?" + k
        lit = 'TO_DATETIME("%s")' % v if re.match(r"\d{4}-\d{2}-", str(v)) else '"%s"' % v
        q = q.replace(tok, lit)
    leftover = re.findall(r"\?[a-z_]+", q)
    if leftover:
        raise RuntimeError("unresolved params: %s" % leftover)
    return q

def http(method, path, body=None, ok=(200, 201)):
    req = urllib.request.Request(A.es + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")

def bulk(index, rows):
    lines = []
    for r in rows:
        lines.append(json.dumps({"index": {"_index": index}}))
        lines.append(json.dumps(r))
    data = ("\n".join(lines) + "\n").encode()
    req = urllib.request.Request(A.es + "/_bulk?refresh=true", data=data, method="POST",
                                 headers={"Content-Type": "application/x-ndjson"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        out = json.loads(resp.read())
    assert not out.get("errors"), out

def run_query(q):
    st, body = http("POST", "/_query", {"query": q})
    if st != 200:
        return None, body
    cols = [c["name"] for c in body.get("columns", [])]
    vals = body.get("values") or [[]]
    return dict(zip(cols, vals[0] if vals else [])), None

report = {"fixtures": [], "empty": {"pass": 0, "fail": []}}

# ---------------- dry run: logic only ----------------
plan_fx = [f for f in FIX if "esql" in f["dialects"]]
for f in plan_fx:
    q = CAND[f["card"]]["esql"]
    idx = "osms_fx_" + f["card"].lower().replace("-", "_")
    adapt(q, idx, f.get("params"))  # raises on unresolved params
print("plan: %d fixture cards, %d empty-run candidates" % (len(plan_fx), len(CAND)))
if A.dry_run:
    print("dry-run OK: all queries adaptable, all params resolvable")
    sys.exit(0)

# ---------------- live ----------------
t0 = time.time()
while True:
    try:
        st, h = http("GET", "/_cluster/health")
        if st == 200 and h.get("status") in ("yellow", "green"):
            break
    except Exception:
        pass
    if time.time() - t0 > A.timeout:
        print("Elasticsearch not reachable"); sys.exit(2)
    time.sleep(3)

fail = 0
for f in plan_fx:
    cid = f["card"]
    idx = "osms_fx_" + cid.lower().replace("-", "_")
    http("DELETE", "/" + idx, ok=(200, 404))
    st, _ = http("PUT", "/" + idx, {"mappings": {"properties": {k: {"type": v} for k, v in f["fields"].items()}}})
    assert st in (200, 201), (cid, st)
    bulk(idx, f["rows"])
    q = adapt(CAND[cid]["esql"], idx, f.get("params"))
    row, err = run_query(q)
    if err is not None:
        fail += 1; report["fixtures"].append({"card": cid, "error": str(err)[:300]}); continue
    bad = {}
    for k, exp in f["expect"].items():
        got = row.get(k)
        if got is None or abs(float(got) - float(exp)) > 1e-4:
            bad[k] = {"expected": exp, "got": got}
    report["fixtures"].append({"card": cid, "result": row, "mismatches": bad})
    if bad:
        fail += 1; print("FIXTURE FAIL", cid, bad)
    else:
        print("FIXTURE PASS", cid, {k: row.get(k) for k in f["expect"]})

# empty pass: per-card typed empty index
for cid, d in CAND.items():
    fields = CAT[cid]["minimum_data_fields"]
    idx = "osms_empty_" + cid.lower().replace("-", "_")
    http("DELETE", "/" + idx, ok=(200, 404))
    props = {}
    for fd in fields:
        props[re.sub(r"[^A-Za-z0-9_]", "_", fd.split(" (")[0].split("/")[0].strip())] = {"type": es_type(fd)}
    http("PUT", "/" + idx, {"mappings": {"properties": props}})
    q = adapt(d["esql"], idx, {"period_start": "2026-06-01T00:00:00Z", "period_end": "2026-07-01T00:00:00Z", "scope_id": "prod"})
    _, err = run_query(q)
    if err is not None:
        report["empty"]["fail"].append({"card": cid, "error": json.dumps(err)[:200]})
    else:
        report["empty"]["pass"] += 1

json.dump(report, open(os.path.join(A.out, "esql_report.json"), "w"), indent=1)
ef = len(report["empty"]["fail"])
print("empty pass: %d/%d | fixture fails: %d" % (report["empty"]["pass"], len(CAND), fail))
for x in report["empty"]["fail"][:5]:
    print("EMPTY FAIL", x["card"], x["error"][:140])
sys.exit(1 if (fail or ef) else 0)
