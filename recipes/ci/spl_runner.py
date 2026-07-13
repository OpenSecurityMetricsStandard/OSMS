#!/usr/bin/env python3
"""SPL engine verification for OSMS recipe candidates (Splunk container).

Fixture pass: send each fixture card's rows as HEC events with indexed fields,
run the candidate SPL search (oneshot), compare against expected values.
Empty pass: every candidate search must dispatch without a parse error against
an empty index.

Notes:
- Date-typed fixture fields are converted to epoch seconds for SPL, matching
  the recipes' arithmetic contract (e.g. (detected_at - occurred_at) / 3600).
- Curated $token$ parameters are substituted with literals (epochs / strings).

Usage:
  python3 recipes/ci/spl_runner.py --out recipes/out --splunk https://localhost:8089 \
      --hec http://localhost:8088 --password $SPLUNK_PASSWORD
  python3 recipes/ci/spl_runner.py --out recipes/out --dry-run
"""
import json, re, os, sys, time, argparse, ssl, datetime as dt
import urllib.request, urllib.error, urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="recipes/out")
ap.add_argument("--splunk", default="https://localhost:8089")
ap.add_argument("--hec", default="http://localhost:8088")
ap.add_argument("--user", default="admin")
ap.add_argument("--password", default=os.environ.get("SPLUNK_PASSWORD", ""))
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--timeout", type=int, default=420)
A = ap.parse_args()

CAND = json.load(open(os.path.join(A.out, "ci_candidates.json")))
FIX = json.load(open(os.path.join(A.out, "fixtures.json")))
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def epoch(iso):
    return int(dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())

def adapt(search, fixture=None):
    s = search
    params = (fixture or {}).get("params", {})
    for k, v in params.items():
        lit = str(epoch(v)) if re.match(r"\d{4}-\d{2}-", str(v)) else '"%s"' % v
        s = s.replace("$%s$" % k, lit)
    leftover = re.findall(r"\$[a-z_]+\$", s)
    if leftover:
        raise RuntimeError("unresolved params: %s" % leftover)
    if fixture and (fixture.get("card") or fixture.get("tables")):
        s = re.sub(r"index=\S+", "index=" + ix_for(fixture), s, count=1)
        s = re.sub(r"sourcetype=\S+", "sourcetype=" + st_for(fixture), s, count=1)
    return s

def st_for(fixture):
    t = fixture.get("tables") or {}
    return t.get("spl_sourcetype") or "records_" + fixture["card"].lower().replace("-", "_")

def ix_for(fixture):
    return (fixture.get("tables") or {}).get("spl_index") or "osms"

def rows_for_spl(fixture):
    out = []
    for r in fixture["rows"]:
        row = {}
        for k, v in r.items():
            row[k] = epoch(v) if fixture["fields"].get(k) == "date" else v
        out.append(row)
    return out

def mgmt(method, path, data=None):
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(A.splunk + path, data=body, method=method)
    import base64
    req.add_header("Authorization", "Basic " + base64.b64encode(
        ("%s:%s" % (A.user, A.password)).encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=90, context=CTX) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

def retry(fn, tries=4, gap=8):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e; time.sleep(gap)
    raise last

def hec_send(token, events):
    payload = "".join(json.dumps(e) for e in events).encode()
    req = urllib.request.Request(A.hec + "/services/collector/event", data=payload, method="POST",
                                 headers={"Authorization": "Splunk " + token})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read())

def oneshot(search):
    try:
        st, body = retry(lambda: mgmt("POST", "/services/search/jobs",
                        {"search": "search " + search if not search.lstrip().startswith(("search", "|", "index=")) else search,
                         "exec_mode": "oneshot", "output_mode": "json", "count": "10"}), tries=3, gap=6)
    except Exception as e:
        return None, str(e)[:300]
    if st != 200:
        return None, body[:300]
    try:
        res = json.loads(body).get("results", [])
    except Exception:
        return None, body[:300]
    return (res[0] if res else {}), None

# ---------------- dry run ----------------
plan_fx = [f for f in FIX if "spl" in f["dialects"]]
for f in plan_fx:
    adapt(CAND[f["card"]]["spl"], f)
    rows_for_spl(f)
print("plan: %d fixture cards, %d empty-run candidates" % (len(plan_fx), len(CAND)))
if A.dry_run:
    print("dry-run OK: params substitutable, date fields epoch-convertible")
    sys.exit(0)

# ---------------- live ----------------
def _ready():
    try:
        st, _ = mgmt("GET", "/services/server/info?output_mode=json")
        return st == 200
    except Exception:
        return False

t0 = time.time(); streak = 0
while streak < 2:
    if _ready():
        streak += 1
        if streak == 1:
            time.sleep(15)  # survive the provisioning restart of splunkd
    else:
        streak = 0
        if time.time() - t0 > A.timeout:
            print("Splunk not reachable within %ss" % A.timeout); sys.exit(2)
        time.sleep(5)

for idx in ("osms", "osms_empty", "security_findings", "security_incidents"):
    retry(lambda i=idx: mgmt("POST", "/services/data/indexes", {"name": i}))
retry(lambda: mgmt("POST", "/services/data/inputs/http/http", {"disabled": "0", "enableSSL": "0"}))
st, body = retry(lambda: mgmt("POST", "/services/data/inputs/http?output_mode=json",
                {"name": "osms_ci", "index": "osms", "indexes": "osms,security_findings,security_incidents"}))
tok = None
if st in (200, 201):
    tok = json.loads(body)["entry"][0]["content"]["token"]
else:
    st, body = mgmt("GET", "/services/data/inputs/http/osms_ci?output_mode=json")
    tok = json.loads(body)["entry"][0]["content"]["token"]

report = {"fixtures": [], "empty": {"pass": 0, "fail": []}}
fail = 0
for f in plan_fx:
    cid = f["card"]
    events = [{"event": {"card": cid}, "sourcetype": st_for(f),
               "index": ix_for(f), "fields": row} for row in rows_for_spl(f)]
    retry(lambda ev=events: hec_send(tok, ev))
time.sleep(8)  # index latency
for f in plan_fx:
    cid = f["card"]
    row, err = oneshot(adapt(CAND[cid]["spl"], f))
    if err is not None:
        fail += 1; report["fixtures"].append({"card": cid, "error": err}); print("FIXTURE ERROR", cid, err[:140]); continue
    bad = {}
    for k, exp in f["expect"].items():
        got = row.get(k)
        try:
            ok = got is not None and abs(float(got) - float(exp)) <= 1e-4
        except (TypeError, ValueError):
            ok = False
        if not ok:
            bad[k] = {"expected": exp, "got": got}
    report["fixtures"].append({"card": cid, "result": row, "mismatches": bad})
    if bad:
        fail += 1; print("FIXTURE FAIL", cid, bad)
    else:
        print("FIXTURE PASS", cid, {k: row.get(k) for k in f["expect"]})

for cid, d in CAND.items():
    s = adapt(d["spl"], {"params": {"period_start": "2026-06-01T00:00:00Z",
                                    "period_end": "2026-07-01T00:00:00Z", "scope_id": "prod"},
                         "tables": {"spl_index": "osms_empty", "spl_sourcetype": "records"}})
    _, err = oneshot(s)
    if err is not None:
        report["empty"]["fail"].append({"card": cid, "error": err[:200]})
    else:
        report["empty"]["pass"] += 1

json.dump(report, open(os.path.join(A.out, "spl_report.json"), "w"), indent=1)
ef = len(report["empty"]["fail"])
print("empty pass: %d/%d | fixture fails: %d" % (report["empty"]["pass"], len(CAND), fail))
for x in report["empty"]["fail"][:5]:
    print("EMPTY FAIL", x["card"], x["error"][:140])
sys.exit(1 if (fail or ef) else 0)
