#!/usr/bin/env python3
import json, re, math, subprocess, sys, os, argparse
import duckdb, pandas as pd
_here = os.path.dirname(os.path.abspath(__file__))
_ap = argparse.ArgumentParser(description="OSMS recipe gate battery")
_ap.add_argument("--bundle", default=os.path.join(_here, "out"))
ARGS = _ap.parse_args()
BND = ARGS.bundle

B = json.load(open(os.path.join(BND, "recipes.json")))["recipes"]
CAT = {c["id"]: c for c in json.load(open(os.path.join(BND, "catalog.json")))}
fails = []

def typ(f):
    if f == "exclusion_does_not_apply": return "DOUBLE", "float64", "real"
    if f.endswith("_at") or f.endswith("_timestamp") or f.startswith("date_") or f.startswith("period_") or f.endswith("_date"): return "TIMESTAMP", "datetime64[ns]", "datetime"
    if f.endswith("_flag") or f in ("internet_facing",) or f.startswith("is_"): return "BOOLEAN", "bool", "bool"
    if re.search(r"(_value|_score|^weight$|_weight|_amount|_hours|_days|_cost|_eur|_pct)", f): return "DOUBLE", "float64", "real"
    return "VARCHAR", "object", "string"

# ---------------- 1) Sicherheits-Lints ----------------
INVISIBLE = re.compile("[\u202a-\u202e\u2066-\u2069\u200b-\u200f\u2060\ufeff\u00ad]")
DESTR = {"gsql": r"\b(drop|delete|insert|update|alter|create|grant|truncate|merge|attach|copy|call|exec)\b",
 "pg": r"\b(drop|delete|insert|update|alter|create|grant|truncate|merge|attach|copy|call|exec)\b",
 "kql": r"(\.ingest|\.set|\.append|\.drop|externaldata|evaluate\s+python)",
 "spl": r"\b(outputlookup|collect|sendemail|runshellscript|script|delete|map|rest)\b",
 "esql": r"\.ingest", "dax": r"\bpathitem\b",
 "xlsx": r"\b(webservice|rtd|dde|call|registerid|hyperlink|filterxml|encodeurl)\b",
 "py": r"(\bimport\s+(?!math\b|pandas\b)\w+|os\.|sys\.|subprocess|eval\(|exec\(|__import__|open\(|requests|socket|pickle|shutil)"}
CMT = {"gsql": ("--", "/*"), "pg": ("--", "/*"), "kql": ("//",), "spl": ("```",), "esql": ("//",), "dax": ("//",), "py": ("#",), "xlsx": ("'",)}

def is_comment_span(lang, line):
    s = line.strip()
    return any(s.startswith(p) for p in CMT[lang])

lintfail = 0
for cid, r in B.items():
    for lang, code in (r.get("dialects") or {}).items():
        p = []
        if INVISIBLE.search(code): p.append("bidi/invisible")
        for ln in code.split("\n"):
            core = ln if is_comment_span(lang, ln) else ln
            if not is_comment_span(lang, ln):
                if lang in ("gsql", "pg"):
                    core = re.sub(r"/\*.*?\*/", "", ln)
                    core = core.split("--")[0]
                elif lang in ("kql", "esql", "dax"):
                    core = ln.split("//")[0]
                elif lang == "py":
                    core = ln.split("#")[0]
                elif lang == "xlsx":
                    core = re.sub(r'"[^"]*"', "", ln)
                bad = {ch for ch in core if ord(ch) > 126}
                if bad: p.append(f"nonascii-code {bad}"); break
        stripped = []
        for ln in code.split("\n"):
            c = ln
            if lang in ("gsql", "pg"): c = re.sub(r"/\*.*?\*/", "", c).split("--")[0]
            elif lang in ("kql", "esql", "dax"): c = c.split("//")[0]
            elif lang == "py": c = c.split("#")[0]
            elif lang == "spl": c = re.sub(r"```.*?```", "", c)
            elif lang == "xlsx": c = "" if ln.strip().startswith("'") else re.sub(r'"[^"]*"', "", ln)
            stripped.append(c)
        if re.search(DESTR[lang], "\n".join(stripped), re.I): p.append("destruktiv")
        if not re.search(r"(NULL|null\(\)|real\(null\)|BLANK|NA\(\)|None|n/a)", code): p.append("kein-fail-closed")
        if p:
            lintfail += 1
            if lintfail <= 6: fails.append(f"LINT {cid} {lang}: {p}")
print(f"[1] Lints: {'PASS' if lintfail==0 else str(lintfail)+' FAIL'} über", sum(len(r.get('dialects') or {}) for r in B.values()), "Snippets")

# ---------------- 2) DuckDB: jedes gsql-Snippet ausführen ----------------
con = duckdb.connect()
sqlfail = 0; sqlrun = 0
for cid, r in B.items():
    code = (r.get("dialects") or {}).get("gsql")
    if not code or r["status"] == "curated_verified" and cid == "STD-016": pass
    if not code: continue
    fields = CAT[cid]["minimum_data_fields"]
    cols = ", ".join(f'"{f}" {typ(f)[0]}' for f in fields)
    try:
        con.execute("DROP TABLE IF EXISTS records; DROP TABLE IF EXISTS findings; DROP TABLE IF EXISTS incidents")
        for t in ("records", "findings", "incidents"):
            con.execute(f'CREATE TABLE {t} ({cols})')
        q = code.replace(":period_start", "$period_start").replace(":period_end", "$period_end").replace(":scope_id", "$scope_id")
        params = {k: v for k, v in {"period_start": "2026-06-01", "period_end": "2026-07-01", "scope_id": "prod"}.items() if "$"+k in q}
        row = con.execute(q, params).fetchone()
        sqlrun += 1
        if r["mechanic"] in ("ratio", "delta") and row[0] is not None: raise AssertionError(f"fail-closed verletzt: {row}")
        if r["mechanic"] == "duration":
            zeros = sum(1 for v in row if v == 0); nones = sum(1 for v in row if v is None)
            if not (zeros == 1 and nones == len(row) - 1): raise AssertionError(f"fail-closed verletzt: {row}")
        if r["mechanic"] == "count" and row[0] != 0: raise AssertionError(f"count leer != 0: {row}")
    except Exception as e:
        sqlfail += 1
        if sqlfail <= 5: fails.append(f"SQL {cid}: {str(e)[:110]}")
print(f"[2] DuckDB gsql: {sqlrun-sqlfail}/{sqlrun+ (0)} ausgeführt, {'PASS' if sqlfail==0 else str(sqlfail)+' FAIL'}")

# ---------------- 3) Python: jedes py-Snippet ausführen ----------------
pyfail = 0; pyrun = 0
for cid, r in B.items():
    code = (r.get("dialects") or {}).get("py")
    if not code: continue
    fields = CAT[cid]["minimum_data_fields"]
    df = pd.DataFrame({f: pd.Series(dtype=typ(f)[1]) for f in fields})
    ns = {}
    try:
        exec(compile(code, cid, "exec"), ns)
        fn = ns.get("compute") or ns.get("mttd") or ns.get("sla_compliance_pct")
        import inspect
        nargs = len(inspect.signature(fn).parameters)
        res = fn(df, "2026-06-01", "2026-07-01", "prod") if nargs == 4 else fn(df, "prod")
        pyrun += 1
        if r["mechanic"] in ("ratio", "duration") and res is not None: raise AssertionError(f"fail-closed: {res}")
        if r["mechanic"] == "count" and res != 0: raise AssertionError(f"count leer: {res}")
    except Exception as e:
        pyfail += 1
        if pyfail <= 5: fails.append(f"PY {cid}: {type(e).__name__} {str(e)[:100]}")
print(f"[3] Python: {pyrun}/{pyrun+pyfail} ausgeführt, {'PASS' if pyfail==0 else str(pyfail)+' FAIL'}")

# ---------------- 4) Duration-Selbstfixtures (konkrete Karten mit Beispielstunden) ----------------
sf_ok = sf_n = 0
for cid, r in B.items():
    if r["status"] != "generated_concrete" or r.get("visual", {}).get("kind") != "duration": continue
    hours = r["visual"]["hours"]; sf_n += 1
    m = re.search(r"([a-z_]+_at)\s*[-\u2212]\s*([a-z_]+_at)", CAT[cid]["formula"]) or re.search(r'"(\w+_at)"\].*?"(\w+_at)"', r["dialects"]["py"])
    end, start = m.group(1), m.group(2)
    base_t = pd.Timestamp("2026-06-10")
    fields = CAT[cid]["minimum_data_fields"]
    rows = []
    for h in hours:
        row = {f: (base_t if f == start else base_t + pd.Timedelta(hours=h) if f == end else ("prod" if f == "scope_id" else None)) for f in fields}
        rows.append(row)
    df = pd.DataFrame(rows)
    for f in fields:
        if typ(f)[2] == "datetime": df[f] = pd.to_datetime(df[f])
    ns = {}; exec(compile(r["dialects"]["py"], cid, "exec"), ns)
    res = ns["compute"](df, "prod")
    hs = sorted(hours); exp_p50 = pd.Series(hs).median(); exp_p90 = hs[math.ceil(0.9 * len(hs)) - 1]
    if res and abs(res["p50_h"] - exp_p50) < 1e-9 and abs(res["p90_h"] - exp_p90) < 1e-9: sf_ok += 1
    else: fails.append(f"SELFFIX {cid}: {res} vs P50 {exp_p50} P90 {exp_p90}")
print(f"[4] Duration-Selbstfixtures: {sf_ok}/{sf_n} PASS")

# ---------------- 5) Kuratierte Rezepte byteidentisch zur verifizierten Quelle ----------------
for f, cid in [(os.path.join(_here, "curated", "std-016.json"), "STD-016"), (os.path.join(_here, "curated", "soc-002.json"), "SOC-002")]:
    src = json.load(open(f))["snippets"]
    assert B[cid]["dialects"] == src, f"Kuratiert-Drift {cid}"
print("[5] Kuratiert byteidentisch: PASS (2/2)")

# ---------------- 6) KQL-Analyzer-Batch vorbereiten ----------------
kql_jobs = []
for cid, r in B.items():
    code = (r.get("dialects") or {}).get("kql")
    if not code: continue
    fields = CAT[cid]["minimum_data_fields"]
    def norm(f):
        f = f.split(" (")[0].split("/")[0].strip()
        return re.sub(r"[^A-Za-z0-9_]", "_", f)
    def kt(f):
        t3 = typ(f)[2]
        if f.startswith("period_") or t3 == "datetime": return "datetime"
        if t3 == "real": return "real"
        return "bool" if t3 == "bool" else "string"
    seen, decls = set(), []
    for f in fields:
        n = norm(f)
        if n and n not in seen:
            seen.add(n); decls.append(f"['{n}']: {kt(n)}")
    for tab in ("records", "findings", "incidents"):
        if re.search(r"\b" + tab + r"\b", code):
            code = f"let {tab} = datatable(" + ", ".join(decls) + ")[];\n" + code
    kql_jobs.append({"id": cid, "q": code})
json.dump(kql_jobs, open(os.path.join(BND, "kql_jobs.json"), "w"))
print(f"[6] KQL-Jobs geschrieben: {len(kql_jobs)}")


# ---------------- 7) Composite-Selbstfixture (STD-069-Pilot) ----------------
import datetime as _dt
c7_ok = c7_n = 0
for cid, r in B.items():
    if r.get("visual", {}).get("kind") != "components": continue
    c7_n += 1
    items = r["visual"]["items"]; exp = r["visual"]["result"]
    fields = CAT[cid]["minimum_data_fields"]
    ps, pe = pd.Timestamp("2026-06-01"), pd.Timestamp("2026-07-01")
    rows = []
    for it in items:
        row = {f: None for f in fields}
        row.update(subscore_id=it["id"], subscore_value=it["v"], weight=it["w"],
                   scope_id="prod", period_start=ps, period_end=pe)
        rows.append(row)
    df = pd.DataFrame(rows)
    for f in fields:
        t3 = typ(f)[1]
        if t3 == "datetime64[ns]": df[f] = pd.to_datetime(df[f])
        if t3 == "float64" and f in df: df[f] = df[f].astype("float64", errors="ignore")
    ns = {}; exec(compile(r["dialects"]["py"], cid, "exec"), ns)
    res = ns["compute"](df, ps, pe, "prod")
    neg = ns["compute"](df.iloc[:-1], ps, pe, "prod")
    bad = df.copy(); bad.loc[bad.index[0], "weight"] = 0.5
    negw = ns["compute"](bad, ps, pe, "prod")
    # DuckDB mit denselben Zeilen
    cols = ", ".join(f'"{f}" {typ(f)[0]}' for f in fields)
    con.execute("DROP TABLE IF EXISTS records"); con.execute(f"CREATE TABLE records ({cols})")
    for _, rr in df.iterrows():
        con.execute("INSERT INTO records VALUES (" + ",".join("?"*len(fields)) + ")",
                    [None if pd.isna(rr[f]) else (rr[f].to_pydatetime() if isinstance(rr[f], pd.Timestamp) else rr[f]) for f in fields])
    q = r["dialects"]["gsql"].replace(":period_start","$period_start").replace(":period_end","$period_end").replace(":scope_id","$scope_id")
    sqlres = con.execute(q, {"period_start": _dt.datetime(2026,6,1), "period_end": _dt.datetime(2026,7,1), "scope_id": "prod"}).fetchone()[0]
    if res is not None and abs(res - exp) < 1e-9 and neg is None and negw is None and sqlres is not None and abs(sqlres - exp) < 1e-9:
        c7_ok += 1
    else:
        fails.append(f"COMPOSITE {cid}: py={res} sql={sqlres} exp={exp} neg={neg}/{negw}")
print(f"[7] Composite-Selbstfixtures: {c7_ok}/{c7_n} PASS (inkl. Negativtests)")

# ---------------- 8) Universal-Fixture-Gate: DuckDB + Python exakt ----------------
import datetime as _dt, inspect as _insp
fx_path = os.path.join(BND, "fixtures.json")
if os.path.exists(fx_path):
    FX = json.load(open(fx_path))
    ok8 = py8 = 0
    for f in FX:
        cid = f["card"]; rec = B[cid]
        tbl = (f.get("tables") or {}).get("esql_from", "records")
        try:
            con = duckdb.connect()
            cols = ", ".join('"%s" %s' % (k, "TIMESTAMP" if v == "date" else
                             "DOUBLE" if v in ("double", "long") else
                             "BOOLEAN" if v == "boolean" else "VARCHAR")
                             for k, v in f["fields"].items())
            con.execute('CREATE TABLE "%s" (%s)' % (tbl, cols))
            for row in f["rows"]:
                vals = []
                for k, ty in f["fields"].items():
                    v = row.get(k)
                    if ty == "date" and v is not None:
                        v = _dt.datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
                    vals.append(v)
                con.execute('INSERT INTO "%s" VALUES (%s)' % (tbl, ", ".join(["?"] * len(vals))), vals)
            q = rec["dialects"]["gsql"]
            params = {"scope_id": "prod", "period_start": "2026-06-01T00:00:00Z",
                      "period_end": "2026-07-01T00:00:00Z"}
            params.update(f.get("params") or {})
            for k, v in params.items():
                lit = ("TIMESTAMP '%s'" % str(v).replace("T", " ").replace("Z", "")
                       if isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-"
                       else "'%s'" % v)
                q = q.replace(":" + k, lit)
            cur = con.execute(q)
            names = [d[0] for d in cur.description]
            got = dict(zip(names, cur.fetchone()))
            for k, exp in f["expect"].items():
                gv = got.get(k, got.get("value"))
                if gv is None and len(got) == 1 and len(f["expect"]) == 1:
                    gv = list(got.values())[0]
                assert gv is not None and abs(float(gv) - float(exp)) < 1e-6, "gsql %s exp %s got %s" % (k, exp, gv)
            ok8 += 1
        except Exception as e:
            fails.append("FX-SQL %s: %s" % (cid, str(e)[:110]))
        try:
            df = pd.DataFrame(f["rows"])
            for k, ty in f["fields"].items():
                if ty == "date" and k in df:
                    df[k] = pd.to_datetime(df[k].astype(str).str.replace("Z", "", regex=False))
            ns = {}
            exec(compile(rec["dialects"]["py"], cid, "exec"), ns)
            fn = ns.get("compute") or ns.get("mttd") or ns.get("sla_compliance_pct")
            nargs = len(_insp.signature(fn).parameters)
            ps = pd.to_datetime(params.get("period_start", "2026-06-01").replace("Z", ""))
            pe = pd.to_datetime(params.get("period_end", "2026-07-01").replace("Z", ""))
            res = fn(df, ps, pe, "prod") if nargs == 4 else fn(df, "prod")
            if isinstance(res, dict):
                for k, exp in f["expect"].items():
                    assert res.get(k) is not None and abs(float(res[k]) - float(exp)) < 1e-6, "py %s exp %s got %s" % (k, exp, res.get(k))
            else:
                expv = f["expect"].get("value", list(f["expect"].values())[0])
                assert res is not None and abs(float(res) - float(expv)) < 1e-6, "py exp %s got %s" % (expv, res)
            py8 += 1
        except Exception as e:
            fails.append("FX-PY %s: %s" % (cid, str(e)[:110]))
    print("[8] Universal-Fixture-Gate: %d/%d gsql exakt, %d/%d py exakt" % (ok8, len(FX), py8, len(FX)))

# ---------------- 9) Excel-Fixture-Gate: formulas-Engine exakt ----------------
xc_path = os.path.join(BND, "excel_candidates.json")
if os.path.exists(fx_path) and os.path.exists(xc_path):
    import tempfile
    sys.path.insert(0, _here)
    import xlsx_dialect as _xl
    XC = json.load(open(xc_path))["candidates"]
    tmp = tempfile.mkdtemp()
    ok9 = n9 = 0
    for f in FX:
        cid = f["card"]
        if cid not in XC:
            continue
        n9 += 1
        try:
            p = os.path.join(tmp, cid + ".xlsx")
            orows = _xl.build_workbook(XC[cid]["spec"], f, p)
            got = _xl.eval_formulas(p, orows)
            for k, exp in f["expect"].items():
                gv = got.get(k)
                assert isinstance(gv, float) and abs(gv - float(exp)) < 1e-4, "%s exp %s got %s" % (k, exp, gv)
            ok9 += 1
        except Exception as e:
            fails.append("FX-XLSX %s: %s" % (cid, str(e)[:110]))
    print("[9] Excel-Fixture-Gate (formulas): %d/%d exakt" % (ok9, n9))

print("\nFINDINGS:" if fails else "\nALLE GATES PASS")
for f in fails[:12]: print(" -", f)
sys.exit(1 if fails else 0)
