#!/usr/bin/env python3
"""Formula Lab bundle builder — catalog.json + recipes.json for the website.

Statuses: curated_verified | generated_concrete | generated_skeleton | pending.
Skeletons are executable by construction (hooks are `AND TRUE /* map: ... */`).
"""
import yaml, json, re, hashlib, sys, os

import argparse
_here = os.path.dirname(os.path.abspath(__file__))
_ap = argparse.ArgumentParser(description="OSMS recipe generator - builds recipes from the card catalog")
_ap.add_argument("--repo", default=os.path.dirname(_here), help="repo root (default: parent of recipes/)")
_ap.add_argument("--out", default=os.path.join(_here, "out"), help="output directory")
_ap.add_argument("--emit-candidates", action="store_true", help="also emit CI-only SPL/ES|QL candidates + fixtures")
ARGS = _ap.parse_args()
REPO, OUT = ARGS.repo, ARGS.out
os.makedirs(OUT, exist_ok=True)

MECH = {"Ratio":"ratio","Unit Cost":"ratio","Duration":"duration","Count":"count","Delta":"delta","Penalty":"delta",
        "Composite":"component_tree","Weighted Sum":"component_tree","Weighted Average":"component_tree",
        "Index":"component_tree","Score":"component_tree","Monetary Risk":"component_tree","Ranking":"ranking"}
KEEP = ["id","name","card_version","domain","type_label","calculation_type","unit","direction","frequency","purpose",
        "management_question","calculation_plain","formula","special_cases_gates","calculation_example",
        "target_thresholds","minimum_data_fields","data_sources","numerator_denominator","threshold_mode"]

cards = yaml.safe_load(open(os.path.join(REPO, "catalog/osms-catalog.yaml"), "rb"))
cards = cards["cards"] if isinstance(cards, dict) and "cards" in cards else cards

def human(v):  # snake_case variable -> readable phrase
    return v.replace("_", " ")

RATIO_PAT = re.compile(r"^\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*/\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?\s*(\*\s*100)?\s*$")
DUR_PAT = re.compile(r"([a-z_]+_at)\s*[-−]\s*([a-z_]+_at)")

# ---------------- example-number extraction for visuals & self-fixtures ----------------
def ratio_example(ex):
    nums = [float(x) for x in re.findall(r"(\d+(?:[.,]\d+)?)", ex.replace(",", "."))]
    pcts = [float(x) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", ex.replace(",", "."))]
    for p in pcts:
        for i, n in enumerate(nums):
            for m in nums[:i] + nums[i+1:]:
                if n > 0 and m <= n and abs(100.0 * m / n - p) < 0.05:
                    return {"den": n, "num": m, "pct": round(100.0 * m / n, 1)}
    return None

def duration_example(ex):
    hs = [float(x) for x in re.findall(r"(\d+(?:[.,]\d+)?)\s*h\b", ex.replace(",", "."))]
    hs = sorted(set(hs))
    return {"hours": hs} if len(hs) >= 3 else None

# ---------------- templates (gsql / kql / py) ----------------
def hdr(cid, ch):  # ch: comment prefix
    return f"{ch} {cid} \u00b7 generated from the card contract \u00b7 non-normative"

def t_ratio_gsql(cid, num, den, times100, hooks):
    pct = " * 100" if times100 else ""
    return f"""{hdr(cid,'--')}
WITH denominator AS (
  SELECT record_id FROM records
  WHERE scope_id = :scope_id
    AND TRUE /* period: anchor on the card's reporting-period timestamp */
    AND TRUE /* population: {hooks['den']} */
),
numerator AS (
  SELECT r.record_id
  FROM records r JOIN denominator USING (record_id)
  WHERE TRUE /* condition: {hooks['num']} */
)
SELECT CASE
  WHEN (SELECT COUNT(*) FROM denominator) = 0 THEN NULL  -- n/a, never 0
  ELSE 1.0{pct} * (SELECT COUNT(*) FROM numerator)
             / (SELECT COUNT(*) FROM denominator)
END AS {num[:40]}_ratio;"""

def t_ratio_kql(cid, num, den, times100, hooks):
    f = "100.0 * " if times100 else "1.0 * "
    return f"""{hdr(cid,'//')}
let scope = "prod";
records
| where scope_id == scope
| where true // period: anchor on the card's reporting-period timestamp
| where true // population: {hooks['den']}
| summarize den = count(),
            num = countif(true) // condition: {hooks['num']}
| extend value = iff(den == 0, real(null), {f}num / den) // n/a, never 0"""

def t_ratio_py(cid, num, den, times100, hooks):
    f = "100.0 * " if times100 else "1.0 * "
    return f"""{hdr(cid,'#')}
import pandas as pd

def compute(records: pd.DataFrame, scope_id):
    population = lambda r: True   # map: {hooks['den']}
    condition = lambda r: True    # map: {hooks['num']}
    base = records[(records["scope_id"] == scope_id)
                   & records.apply(population, axis=1)]
    den = len(base)
    if den == 0:
        return None               # n/a - never 0
    num = int(base.apply(condition, axis=1).sum())
    return {f}num / den"""

def t_dur_gsql(cid, end, start, concrete):
    body = f"EXTRACT(EPOCH FROM ({end} - {start})) / 3600.0" if concrete else \
           "0.0 /* duration expression: map per the card formula */"
    filt = (f"AND {start} IS NOT NULL AND {end} IS NOT NULL\n    AND {end} >= {start}"
            if concrete else "AND TRUE /* validity: exclude missing or negative durations */")
    return f"""{hdr(cid,'--')}
WITH cases AS (
  SELECT {body} AS d_h
  FROM records
  WHERE scope_id = :scope_id
    AND TRUE /* period: anchor on the card's reporting-period timestamp */
    {filt}
)
SELECT CASE WHEN COUNT(*) = 0 THEN NULL
       ELSE percentile_disc(0.5) WITHIN GROUP (ORDER BY d_h) END AS p50_h,
       CASE WHEN COUNT(*) = 0 THEN NULL
       ELSE percentile_disc(0.9) WITHIN GROUP (ORDER BY d_h) END AS p90_h,
       AVG(d_h) AS mean_h_supplementary,
       COUNT(*) AS valid_cases
FROM cases;"""

def t_dur_kql(cid, end, start, concrete):
    body = f"({end} - {start}) / 1h" if concrete else "0.0 // duration expression: map per the card formula"
    filt = (f"| where isnotnull({start}) and isnotnull({end}) and {end} >= {start}"
            if concrete else "| where true // validity: exclude missing or negative durations")
    return f"""{hdr(cid,'//')}
let scope = "prod";
records
| where scope_id == scope
| where true // period: anchor on the card's reporting-period timestamp
{filt}
| extend d_h = {body}
| summarize valid_cases = count(), p50_h = percentile(d_h, 50),
            p90_h = percentile(d_h, 90),
            mean_h_supplementary = round(avg(d_h), 1)
// empty case base -> no row = n/a, never 0"""

def t_dur_py(cid, end, start, concrete):
    body = (f'((base["{end}"] - base["{start}"]).dt.total_seconds() / 3600.0)'
            if concrete else "base.apply(lambda r: 0.0, axis=1)  # map: duration per the card formula")
    filt = (f'& base["{start}"].notna() & base["{end}"].notna()' if concrete else "")
    return f"""{hdr(cid,'#')}
import math
import pandas as pd

def compute(records: pd.DataFrame, scope_id):
    base = records[(records["scope_id"] == scope_id)]
    base = base[pd.Series(True, index=base.index) {filt}]
    d_h = {body}
    d_h = d_h[d_h >= 0].sort_values()
    n = len(d_h)
    if n == 0:
        return None               # n/a - never 0
    return {{"valid_cases": n, "p50_h": d_h.median(),
            "p90_h": d_h.iloc[math.ceil(0.9 * n) - 1],   # nearest rank
            "mean_h_supplementary": round(d_h.mean(), 1)}}"""

def t_count_gsql(cid, hook):
    return f"""{hdr(cid,'--')}
SELECT COUNT(*) AS value          -- a count of 0 is a valid result here
FROM records
WHERE scope_id = :scope_id
  AND TRUE /* period: anchor on the card's reporting-period timestamp */
  AND TRUE /* population: {hook} */
-- n/a applies only when the source itself is unavailable (data confidence)"""

def t_count_kql(cid, hook):
    return f"""{hdr(cid,'//')}
let scope = "prod";
records
| where scope_id == scope
| where true // period: anchor on the card's reporting-period timestamp
| where true // population: {hook}
| summarize value = count()
// n/a applies only when the source itself is unavailable (data confidence)"""

def t_count_py(cid, hook):
    return f"""{hdr(cid,'#')}
import pandas as pd

def compute(records: pd.DataFrame, scope_id):
    population = lambda r: True   # map: {hook}
    base = records[(records["scope_id"] == scope_id)
                   & records.apply(population, axis=1)]
    return int(len(base))         # source unavailable -> None (n/a) via data confidence"""

def t_delta_gsql(cid, hook):
    return f"""{hdr(cid,'--')}
WITH current_period AS (
  SELECT 0.0 AS v /* quantity: {hook} - current period */ FROM records
  WHERE scope_id = :scope_id AND TRUE /* period: current */
),
previous_period AS (
  SELECT 0.0 AS v /* quantity: {hook} - previous period */ FROM records
  WHERE scope_id = :scope_id AND TRUE /* period: previous */
)
SELECT CASE WHEN (SELECT COUNT(*) FROM current_period) = 0
         OR (SELECT COUNT(*) FROM previous_period) = 0 THEN NULL  -- n/a, never 0
  ELSE (SELECT SUM(v) FROM current_period)
     - (SELECT SUM(v) FROM previous_period) END AS delta;"""

def t_delta_kql(cid, hook):
    return f"""{hdr(cid,'//')}
let scope = "prod";
let current_v  = toscalar(records | where scope_id == scope | where true // {hook} - current period
                          | summarize sum(0.0));
let previous_v = toscalar(records | where scope_id == scope | where true // {hook} - previous period
                          | summarize sum(0.0));
print delta = iff(isnull(current_v) or isnull(previous_v), real(null), current_v - previous_v)
// n/a, never 0, when either period is missing"""

def t_delta_py(cid, hook):
    return f"""{hdr(cid,'#')}
import pandas as pd

def compute(records: pd.DataFrame, scope_id):
    quantity = lambda period: 0.0   # map: {hook} per period
    current_v, previous_v = quantity("current"), quantity("previous")
    if current_v is None or previous_v is None:
        return None                 # n/a - never 0
    return current_v - previous_v"""


# ---------------- composite pattern A: subscores as input rows ----------------
COMPOSITE_ACTIVATE = ["STD-069"]  # pilot; rollout per verified pattern class

def parse_composite(c):
    if not {"subscore_id", "subscore_value", "weight"} <= set(c["minimum_data_fields"]): return None
    m = re.search(r"p\(([^)]*)\)\s*=\s*([^;]+)", c["formula"])
    if not m: return None
    args = [a.strip() for a in m.group(1).split(",") if a.strip()]
    terms = re.findall(r"(\d*\.?\d+)\s*\*\s*([a-z_][a-z0-9_]*)", m.group(2))
    if len(terms) < 2 or {x[1] for x in terms} != set(args): return None
    comps = [(n, float(w)) for w, n in terms]
    if abs(sum(w for _, w in comps) - 1.0) > 0.001: return None
    return comps

def composite_example(c, comps):
    ex = c["calculation_example"]
    vals = {}
    for n, _ in comps:
        mm = re.search(re.escape(n) + r"\s*=\s*(\d+(?:\.\d+)?)", ex)
        if not mm: return None
        vals[n] = float(mm.group(1))
    calc = round(sum(w * vals[n] for n, w in comps), 4)
    stated = re.findall(r"=\s*(\d+(?:\.\d+)?)\s*(?:\u2192|->)", ex)
    if stated and abs(float(stated[-1]) - calc) > 0.01: return None
    return {"items": [{"id": n, "w": w, "v": vals[n]} for n, w in comps], "result": calc}

def slug(name):
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:40]

def t_comp_gsql(cid, name, comps):
    ids = ",\n                        ".join("'" + n + "'" for n, _ in comps)
    k = len(comps)
    return f"""{hdr(cid,'--')}
-- composite: subscore rows in, weighted sum out (weights are data, validated)
WITH subs AS (
  SELECT subscore_id, subscore_value, weight
  FROM records  -- subscore rows per the card's minimum data fields
  WHERE scope_id = :scope_id
    AND period_start = :period_start AND period_end = :period_end
    AND subscore_id IN ({ids})
),
checks AS (
  SELECT COUNT(*) AS n, COUNT(DISTINCT subscore_id) AS ids, SUM(weight) AS wsum,
         MIN(subscore_value) AS vmin, MAX(subscore_value) AS vmax
  FROM subs
)
SELECT CASE
  WHEN n <> {k} OR ids <> {k} THEN NULL     -- component missing or duplicated -> n/a
  WHEN vmin < 0 OR vmax > 100 THEN NULL     -- inputs must be 0-100 posture scores
  WHEN ABS(wsum - 1.0) > 0.001 THEN NULL    -- versioned weights must sum to 1.0
  ELSE (SELECT SUM(weight * subscore_value) FROM subs)
END AS {slug(name)}
FROM checks;"""

def t_comp_kql(cid, name, comps):
    ids = ", ".join('"' + n + '"' for n, _ in comps)
    k = len(comps)
    return f"""{hdr(cid,'//')}
// composite: subscore rows in, weighted sum out (weights are data, validated)
let scope = "prod";
let p_start = datetime(2026-06-01);
let p_end = datetime(2026-07-01);
records
| where scope_id == scope and period_start == p_start and period_end == p_end
| where subscore_id in ({ids})
| summarize n = count(), ids = dcount(subscore_id), wsum = sum(weight),
            vmin = min(subscore_value), vmax = max(subscore_value),
            score = sum(weight * subscore_value)
| extend value = iff(n != {k} or ids != {k} or vmin < 0.0 or vmax > 100.0
                     or abs(wsum - 1.0) > 0.001, real(null), score)
| project value, valid_components = ids
// any gate violation -> real(null), never a fabricated score"""

def t_comp_py(cid, name, comps):
    ids = ", ".join('"' + n + '"' for n, _ in comps)
    k = len(comps)
    return f"""{hdr(cid,'#')}
# composite: subscore rows in, weighted sum out (weights are data, validated)
import pandas as pd

EXPECTED = {{{ids}}}

def compute(records: pd.DataFrame, period_start, period_end, scope_id):
    s = records[(records["scope_id"] == scope_id)
                & (records["period_start"] == period_start)
                & (records["period_end"] == period_end)
                & records["subscore_id"].isin(EXPECTED)]
    if len(s) != {k} or s["subscore_id"].nunique() != {k}:
        return None                        # component missing or duplicated -> n/a
    if s["subscore_value"].min() < 0 or s["subscore_value"].max() > 100:
        return None                        # inputs must be 0-100 posture scores
    if abs(s["weight"].sum() - 1.0) > 0.001:
        return None                        # versioned weights must sum to 1.0
    return float((s["weight"] * s["subscore_value"]).sum())"""

COMP_ASSUM = {
 "gsql": "Concrete composite recipe: the card mandates pre-scored 0-100 subscores as input rows, so the query only validates and aggregates - completeness of the expected components, value bounds, and the versioned weight sum. Any violation returns NULL, never a fabricated score.",
 "kql": "Concrete composite recipe for Sentinel/Log Analytics: subscore rows are validated (completeness, 0-100 bounds, weight sum = 1.0) before the weighted sum; period parameters are named p_start/p_end to avoid shadowing the period_start/period_end columns.",
 "py": "Concrete composite recipe (pandas): validates completeness, bounds and weight sum before aggregating; every gate violation returns None (n/a). The subscores arrive pre-scored per the card contract - this recipe never rescales raw values."}

# ---------------- curated overrides (verified in the MVP run) ----------------
CURATED = {}
for f in [os.path.join(_here, "curated", "std-016.json"), os.path.join(_here, "curated", "soc-002.json")]:
    d = json.load(open(f))
    CURATED[d["card"]] = d

CURATED_ASSUM = json.load(open(os.path.join(_here, "curated", "curated_assumptions.json")))

SKEL_ASSUM = {
 "gsql": "Executable skeleton: scope, period and fail-closed scaffolding are generated from the card contract; the TRUE-marked hooks are where you map the card's population to your source. Table name records is illustrative.",
 "kql": "Executable skeleton for Sentinel/Defender/Log Analytics: replace the true-marked hooks with your population predicates; records stands for your export table.",
 "py": "Executable skeleton (pandas): replace the lambda hooks with the card's population logic; column names follow the card's minimum data fields."}
CONC_ASSUM = {
 "gsql": "Concrete duration recipe: percentile_disc is the exact nearest-rank percentile the card mandates (P50/P90; mean supplementary). Map the period anchor and validity rules to your source.",
 "kql": "Concrete duration recipe: percentile() is a T-digest estimate, not exact nearest rank - compute the rank explicitly for board-grade exactness. Empty case base returns no row = n/a.",
 "py": "Concrete duration recipe with explicit nearest rank (ceil(0.9 \u00b7 n)); NaT never counts; negative durations are excluded as data-quality errors."}

recipes, stats = {}, {"curated_verified":0,"generated_concrete":0,"generated_skeleton":0,"pending":0}
for c in cards:
    cid, mech = c["id"], MECH[c["calculation_type"]]
    entry = {"mechanic": mech, "card_version": str(c["card_version"])}
    if cid in CURATED:
        entry.update(status="curated_verified", recipe_version=CURATED[cid]["recipe_version"],
                     dialects=CURATED[cid]["snippets"], assumptions=CURATED_ASSUM[cid])
        ex = ratio_example(c["calculation_example"]) if mech == "ratio" else duration_example(c["calculation_example"])
        if ex: entry["visual"] = {"kind": mech, **ex}
    elif mech == "ratio":
        m = RATIO_PAT.match(c["formula"].strip())
        if m:
            num, den, t100 = m.group(1), m.group(2), bool(m.group(3))
            hooks = {"num": human(num), "den": human(den)}
        else:
            num, den, t100 = "numerator", "denominator", True
            nd = (c.get("numerator_denominator") or "").strip()
            hooks = {"num": nd.split("/")[0].strip() or "numerator per the card definition",
                     "den": (nd.split("/")[1].strip() if "/" in nd else "denominator per the card definition")}
        entry.update(status="generated_skeleton", recipe_version="0.1.0",
                     dialects={"gsql": t_ratio_gsql(cid, num, den, t100, hooks),
                               "kql": t_ratio_kql(cid, num, den, t100, hooks),
                               "py": t_ratio_py(cid, num, den, t100, hooks)},
                     assumptions=SKEL_ASSUM)
        ex = ratio_example(c["calculation_example"])
        if ex: entry["visual"] = {"kind": "ratio", **ex}
    elif mech == "duration":
        m = DUR_PAT.search(c["formula"])
        concrete = bool(m and m.group(1) in c["minimum_data_fields"] and m.group(2) in c["minimum_data_fields"])
        end, start = (m.group(1), m.group(2)) if concrete else ("end_at", "start_at")
        entry.update(status="generated_concrete" if concrete else "generated_skeleton", recipe_version="0.1.0",
                     dialects={"gsql": t_dur_gsql(cid, end, start, concrete),
                               "kql": t_dur_kql(cid, end, start, concrete),
                               "py": t_dur_py(cid, end, start, concrete)},
                     assumptions=CONC_ASSUM if concrete else SKEL_ASSUM)
        ex = duration_example(c["calculation_example"])
        if ex: entry["visual"] = {"kind": "duration", **ex}
    elif mech in ("count", "delta"):
        hook = (c.get("numerator_denominator") or c["formula"])[:110].strip()
        T = {"count": (t_count_gsql, t_count_kql, t_count_py),
             "delta": (t_delta_gsql, t_delta_kql, t_delta_py)}[mech]
        entry.update(status="generated_skeleton", recipe_version="0.1.0",
                     dialects={"gsql": T[0](cid, hook), "kql": T[1](cid, hook), "py": T[2](cid, hook)},
                     assumptions=SKEL_ASSUM)
    elif mech == "component_tree" and cid in COMPOSITE_ACTIVATE and parse_composite(c):
        comps = parse_composite(c)
        entry.update(status="generated_concrete", recipe_version="0.1.0",
                     dialects={"gsql": t_comp_gsql(cid, c["name"], comps),
                               "kql": t_comp_kql(cid, c["name"], comps),
                               "py": t_comp_py(cid, c["name"], comps)},
                     assumptions=COMP_ASSUM)
        ex = composite_example(c, comps)
        if ex: entry["visual"] = {"kind": "components", **ex}
    else:
        entry.update(status="pending",
                     note="Component-tree and ranking recipes land in a later release; the card contract above is complete.")
    stats[entry["status"]] += 1
    recipes[cid] = entry

slim = [{**{k: c.get(k) for k in KEEP}, "mechanic": MECH[c["calculation_type"]]} for c in cards]
cat_js = json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
rec_js = json.dumps({"bundle_version": "0.3.0", "source_catalog": "osms-catalog.yaml v0.9.1",
                     "recipes": recipes}, ensure_ascii=False, separators=(",", ":"))
open(f"{OUT}/catalog.json", "w").write(cat_js)
open(f"{OUT}/recipes.json", "w").write(rec_js)
man = {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest()
       for p in [f"{OUT}/catalog.json", f"{OUT}/recipes.json"]}
open(f"{OUT}/manifest.json", "w").write(json.dumps(man, indent=1))
print("Status-Verteilung:", stats)
print("Größen: catalog %.2f MB, recipes %.2f MB" % (len(cat_js)/1e6, len(rec_js)/1e6))
print("Manifest:", man)

# ================= CI candidates: SPL + ES|QL (engine-verified before publication) =================
def t_ratio_spl(cid, hooks):
    return f"""{hdr(cid,'```')} ```
index=osms sourcetype=records scope_id="prod"
``` period: anchor on the card's reporting-period timestamp ```
``` population: {hooks['den']} ```
| eval cond = if(1=1, 1, 0)  ``` condition: {hooks['num']} ```
| stats count AS den, sum(cond) AS num
| eval value = if(den == 0, null(), round(100.0 * num / den, 1))
``` n/a, never 0 ```"""

def t_ratio_esql(cid, hooks):
    return f"""{hdr(cid,'//')}
FROM records
| WHERE scope_id == "prod"
| WHERE true // period: anchor on the card's reporting-period timestamp
| WHERE true // population: {hooks['den']}
| EVAL cond = CASE(true, 1, 0) // condition: {hooks['num']}
| STATS den = COUNT(*), num = SUM(cond)
| EVAL value = CASE(den == 0, NULL, 100.0 * num / den)
// n/a, never 0"""

def t_dur_spl(cid, end, start, concrete):
    if concrete:
        base = f"""| where isnotnull({start}) AND isnotnull({end}) AND {end} >= {start}
| eval d_h = ({end} - {start}) / 3600"""
    else:
        base = """``` validity: exclude missing or negative durations ```
| eval d_h = 0.0  ``` duration expression: map per the card formula ```"""
    return f"""{hdr(cid,'```')} ```
index=osms sourcetype=records scope_id="prod"
``` period: anchor on the card's reporting-period timestamp ```
{base}
| sort 0 d_h
| streamstats count AS rk
| eventstats count AS n, avg(d_h) AS mean_h
| eval is50 = if(rk == ceiling(0.5 * n), d_h, null()),
       is90 = if(rk == ceiling(0.9 * n), d_h, null())
| stats max(n) AS valid_cases, max(is50) AS p50_h,
        max(is90) AS p90_h, max(mean_h) AS mean_h_supplementary
``` nearest rank, explicit; empty case base -> no results = n/a ```"""

def t_dur_esql(cid, end, start, concrete):
    if concrete:
        base = f"""| WHERE {start} IS NOT NULL AND {end} IS NOT NULL AND {end} >= {start}
| EVAL d_h = DATE_DIFF("seconds", {start}, {end}) / 3600.0"""
    else:
        base = """| WHERE true // validity: exclude missing or negative durations
| EVAL d_h = 0.0 // duration expression: map per the card formula"""
    return f"""{hdr(cid,'//')}
FROM records
| WHERE scope_id == "prod"
| WHERE true // period: anchor on the card's reporting-period timestamp
{base}
| STATS valid_cases = COUNT(*), vals = VALUES(d_h),
        p50_h = MEDIAN(d_h), mean_h_supplementary = AVG(d_h)
| EVAL s = MV_SORT(vals), n = MV_COUNT(s),
       p90_h = MV_FIRST(MV_SLICE(s, TO_INTEGER(CEIL(0.9 * n)) - 1,
                                     TO_INTEGER(CEIL(0.9 * n)) - 1))
| KEEP valid_cases, p50_h, p90_h, mean_h_supplementary
// P90 nearest rank, explicit; empty case base -> null = n/a"""

def t_count_spl(cid, hook):
    return f"""{hdr(cid,'```')} ```
index=osms sourcetype=records scope_id="prod"
``` period + population: {hook} ```
| stats count AS value
``` a count of 0 is a valid result here ```"""

def t_count_esql(cid, hook):
    return f"""{hdr(cid,'//')}
FROM records
| WHERE scope_id == "prod"
| WHERE true // period + population: {hook}
| STATS value = COUNT(*)
// a count of 0 is a valid result here"""

def t_delta_spl(cid, hook):
    return f"""{hdr(cid,'```')} ```
index=osms sourcetype=records scope_id="prod"
| eval bucket = "current"  ``` map period split: {hook} ```
| stats sum(eval(0.0)) AS v BY bucket
| eventstats values(eval(if(bucket=="current", v, null()))) AS cur,
             values(eval(if(bucket=="previous", v, null()))) AS prev
| head 1
| eval delta = if(isnull(cur) OR isnull(prev), null(), cur - prev)
``` n/a, never 0, when either period is missing ```"""

def t_delta_esql(cid, hook):
    return f"""{hdr(cid,'//')}
FROM records
| WHERE scope_id == "prod"
| EVAL bucket = "current" // map period split: {hook}
| STATS v = SUM(0.0) BY bucket
| STATS cur = SUM(CASE(bucket == "current", v, NULL)),
        prev = SUM(CASE(bucket == "previous", v, NULL))
| EVAL delta = CASE(cur IS NULL OR prev IS NULL, NULL, cur - prev)
// n/a, never 0, when either period is missing"""

def t_comp_spl(cid, comps):
    ids = ", ".join('"' + n + '"' for n, _ in comps); k = len(comps)
    return f"""{hdr(cid,'```')} ```
index=osms sourcetype=records scope_id="prod" subscore_id IN ({ids})
| stats count AS n, dc(subscore_id) AS ids, sum(weight) AS wsum,
        min(subscore_value) AS vmin, max(subscore_value) AS vmax,
        sum(eval(weight * subscore_value)) AS score
| eval value = if(n != {k} OR ids != {k} OR vmin < 0 OR vmax > 100
                  OR abs(wsum - 1.0) > 0.001, null(), score)
``` any gate violation -> null, never a fabricated score ```"""

def t_comp_esql(cid, comps):
    ids = ", ".join('"' + n + '"' for n, _ in comps); k = len(comps)
    return f"""{hdr(cid,'//')}
FROM records
| WHERE scope_id == "prod" AND subscore_id IN ({ids})
| STATS n = COUNT(*), ids = COUNT_DISTINCT(subscore_id), wsum = SUM(weight),
        vmin = MIN(subscore_value), vmax = MAX(subscore_value),
        score = SUM(weight * subscore_value)
| EVAL value = CASE(n != {k} OR ids != {k} OR vmin < 0.0 OR vmax > 100.0
                    OR ABS(wsum - 1.0) > 0.001, NULL, score)
// any gate violation -> NULL, never a fabricated score"""

if ARGS.emit_candidates:
    import math
    import datetime as _dt
    cand, fixtures = {}, []
    for c in cards:
        cid, mech = c["id"], MECH[c["calculation_type"]]
        r = recipes[cid]
        if r["status"] == "pending" and cid not in CURATED: continue
        if cid in CURATED:
            cand[cid] = {"spl": CURATED[cid]["snippets"]["spl"], "esql": CURATED[cid]["snippets"]["esql"], "status": "curated"}
            continue
        if mech == "ratio":
            m = RATIO_PAT.match(c["formula"].strip())
            nd = (c.get("numerator_denominator") or "").strip()
            hooks = ({"num": human(m.group(1)), "den": human(m.group(2))} if m else
                     {"num": nd.split("/")[0].strip() or "numerator", "den": (nd.split("/")[1].strip() if "/" in nd else "denominator")})
            cand[cid] = {"spl": t_ratio_spl(cid, hooks), "esql": t_ratio_esql(cid, hooks), "status": r["status"]}
        elif mech == "duration":
            m = DUR_PAT.search(c["formula"])
            conc = r["status"] == "generated_concrete"
            end, start = (m.group(1), m.group(2)) if (m and conc) else ("end_at", "start_at")
            cand[cid] = {"spl": t_dur_spl(cid, end, start, conc), "esql": t_dur_esql(cid, end, start, conc), "status": r["status"]}
            if conc and "visual" in r:
                hs = r["visual"]["hours"]; n = len(hs); ss = sorted(hs)
                fixtures.append({"card": cid, "dialects": ["spl", "esql"],
                    "fields": {start: "date", end: "date", "scope_id": "keyword"},
                    "rows": [{start: "2026-06-10T00:00:00Z",
                              end: (_dt.datetime(2026, 6, 10) + _dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "scope_id": "prod"} for h in hs],
                    "expect": {"valid_cases": n,
                               "p50_h": (ss[(n-1)//2] if n % 2 else (ss[n//2-1]+ss[n//2])/2),
                               "p90_h": ss[math.ceil(0.9*n)-1],
                               "mean_h_supplementary": round(sum(hs)/n, 6)}})
        elif mech == "count":
            hook = (c.get("numerator_denominator") or c["formula"])[:110].strip()
            cand[cid] = {"spl": t_count_spl(cid, hook), "esql": t_count_esql(cid, hook), "status": r["status"]}
        elif mech == "delta":
            hook = (c.get("numerator_denominator") or c["formula"])[:110].strip()
            cand[cid] = {"spl": t_delta_spl(cid, hook), "esql": t_delta_esql(cid, hook), "status": r["status"]}
        elif mech == "component_tree" and cid in COMPOSITE_ACTIVATE:
            comps = parse_composite(c)
            cand[cid] = {"spl": t_comp_spl(cid, comps), "esql": t_comp_esql(cid, comps), "status": r["status"]}
            if "visual" in r:
                fixtures.append({"card": cid, "dialects": ["spl", "esql"],
                    "fields": {"subscore_id": "keyword", "subscore_value": "double", "weight": "double", "scope_id": "keyword"},
                    "rows": [{"subscore_id": it["id"], "subscore_value": it["v"], "weight": it["w"], "scope_id": "prod"} for it in r["visual"]["items"]],
                    "expect": {"value": r["visual"]["result"]}})
    # curated fixtures: STD-016 (80/64 + decoys) und SOC-002 (Stundenpaare)
    rows16 = []
    for i in range(80):
        ok = i < 64
        rows16.append({"severity": "critical", "internet_facing": True, "scope_id": "prod",
                       "due_at": "2026-06-20T12:00:00Z",
                       "remediated_at": "2026-06-19T12:00:00Z" if ok else "2026-06-25T12:00:00Z",
                       "validation_status": "validated" if ok else "open"})
    for i in range(8):
        rows16.append({"severity": "high", "internet_facing": False, "scope_id": "prod",
                       "due_at": "2026-06-20T12:00:00Z", "remediated_at": "2026-06-19T12:00:00Z",
                       "validation_status": "validated"})
    fixtures.append({"card": "STD-016", "dialects": ["spl", "esql"],
        "fields": {"severity": "keyword", "internet_facing": "boolean", "scope_id": "keyword",
                   "due_at": "date", "remediated_at": "date", "validation_status": "keyword"},
        "params": {"period_start": "2026-06-01T00:00:00Z", "period_end": "2026-07-01T00:00:00Z", "scope_id": "prod"},
        "tables": {"spl_index": "security_findings", "spl_sourcetype": "vuln:findings", "esql_from": "findings"},
        "rows": rows16, "expect": {"sla_compliance_pct": 80.0}})
    hs2 = [2, 4, 10, 20, 30]
    fixtures.append({"card": "SOC-002", "dialects": ["spl", "esql"],
        "fields": {"occurred_at": "date", "detected_at": "date", "scope_id": "keyword"},
        "params": {"period_start": "2026-06-01T00:00:00Z", "period_end": "2026-07-01T00:00:00Z", "scope_id": "prod"},
        "tables": {"spl_index": "security_incidents", "spl_sourcetype": "incident", "esql_from": "incidents"},
        "rows": [{"occurred_at": "2026-06-10T00:00:00Z",
                  "detected_at": (_dt.datetime(2026, 6, 10) + _dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "scope_id": "prod"} for h in hs2],
        "expect": {"valid_cases": 5, "p50_h": 10.0, "p90_h": 30.0, "mean_h_supplementary": 13.2}})
    # Sicherheits-Lint über alle Kandidaten
    import sys as _sys
    INV = re.compile("[\u202a-\u202e\u2066-\u2069\u200b-\u200f\u2060\ufeff\u00ad]")
    DESTR = {"spl": r"\b(outputlookup|collect|sendemail|runshellscript|script|delete|map|rest)\b",
             "esql": r"\.ingest"}
    bad = []
    for cid, d in cand.items():
        for lang in ("spl", "esql"):
            code = d[lang]
            if INV.search(code): bad.append((cid, lang, "bidi"))
            core = "\n".join((ln.split("//")[0] if lang == "esql" else re.sub(r"```.*?```", "", ln)) for ln in code.split("\n"))
            if re.search(DESTR[lang], core, re.I): bad.append((cid, lang, "destruktiv"))
    if bad:
        print("LINT-FINDINGS:", bad[:6]); _sys.exit(1)
    json.dump(cand, open(f"{OUT}/ci_candidates.json", "w"), ensure_ascii=False, indent=0)
    json.dump(fixtures, open(f"{OUT}/fixtures.json", "w"), ensure_ascii=False, indent=1)
    print(f"CI-Kandidaten: {len(cand)} Karten x SPL+ES|QL | Fixtures: {len(fixtures)} | Lints: PASS")

