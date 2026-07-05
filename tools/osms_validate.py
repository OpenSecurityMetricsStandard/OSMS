#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
osms_validate.py — reference validator for the Open Security Metrics Standard (OSMS).
CALIBRATED to the production catalog structure (osms-catalog.yaml, 2026-07-04).

Usage:
    python tools/osms_validate.py catalog/ --expect-count 327
    python tools/osms_validate.py catalog/osms-catalog.yaml --json report.json

Enums are loaded from catalog/taxonomy.yaml (fallback: built-ins mirroring it).
Domains are checked against catalog/domains.yaml. Aux YAMLs (taxonomy, domains,
principles) are auto-skipped by the card loader.

Exit codes: 0 = OK (warnings allowed), 1 = errors found, 2 = usage/load problem.
"""
import argparse, json, re, sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML required ->  pip install pyyaml", file=sys.stderr); sys.exit(2)

# ---- real field names of the production catalog (single place to adapt) ----
F_ID="id"; F_NAME="name"; F_DOMAIN="domain"; F_TYPE="type"; F_PRIO="priority"
F_LAG="lag_type"; F_CALC="calculation_type"; F_DIR="direction"
F_FORMULA="formula"; F_NUMDEN="numerator_denominator"
F_MINFIELDS="minimum_data_fields"; F_SOURCES="data_sources"
F_CONF="data_confidence"; F_DRILL="drilldown_lineage"
F_DECISION="decision_chain"; F_BREAK="version_break_rule"
F_GUARD="guardrails"; F_STATUS="status"; F_TMODE="threshold_mode"
F_THRESH="target_thresholds"; F_OWNER="accountable_owner"

REQUIRED = ["id","name","osms_version","card_version","release_status","domain",
 "type_label","type","lag_type","priority","mvp","status","scope","unit","purpose",
 "story","management_question","definition","formula","calculation_type",
 "calculation_type_check","calculation_plain","variables_inputs","rebuild_steps",
 "special_cases_gates","calculation_example","target_thresholds",
 "numerator_denominator","frequency","threshold_mode","direction",
 "accountable_owner","escalation_owner","data_sources","minimum_data_fields",
 "framework_mapping","audit_test","reproducibility","drilldown_lineage",
 "data_confidence","confidence_production_rule","decision_chain",
 "version_break_rule","interpretation","example_tasks","guardrails","next_chain"]

LIST_FIELDS = ["guardrails","minimum_data_fields","data_sources",
               "framework_mapping","example_tasks"]
ID_PATTERN = r"^[A-Z]{2,4}-\d{3}[a-z]?$"
EVIDENCE_MIN = {"evidence_ref","record_id","source_system"}

FALLBACK_TAX = {
 "indicator_types": ["metric","kpi","kri","kci","outcome","confidence","maturity","helper"],
 "priorities": ["P0","P1","P2","P3"],
 "lag_types": ["leading","lagging","not_specified"],
 "calculation_types": ["Ratio","Duration","Count","Weighted Sum","Weighted Average",
                       "Composite","Penalty","Index","Ranking","Monetary Risk"],
 "directions": ["higher_is_better","lower_is_better","zero_is_target",
                "band_is_better","context_dependent"],
}

class Report:
    def __init__(self):
        self.errors, self.warnings, self.checks = [], [], {}
    def err(self, check, card, msg):
        self.errors.append({"severity":"ERROR","check":check,"card":card,"message":msg})
    def warn(self, check, card, msg):
        self.warnings.append({"severity":"WARNING","check":check,"card":card,"message":msg})

def load_yaml(p):
    return yaml.safe_load(Path(p).read_text(encoding="utf-8"))

def load_files(paths, rep):
    files=[]
    for p in paths:
        p=Path(p)
        if p.is_dir(): files += sorted(p.rglob("*.yaml"))+sorted(p.rglob("*.yml"))
        elif p.exists(): files.append(p)
        else: print(f"ERROR: path not found: {p}",file=sys.stderr); sys.exit(2)
    cards, meta = [], {}
    for f in files:
        try: doc=load_yaml(f)
        except yaml.YAMLError as e:
            print(f"ERROR: YAML parse error in {f}: {e}",file=sys.stderr); sys.exit(2)
        if doc is None: continue
        if isinstance(doc,dict) and "cards" in doc:
            meta={k:v for k,v in doc.items() if k!="cards"}
            for c in doc["cards"] or []: cards.append((str(f),c))
        elif isinstance(doc,list):
            if doc and isinstance(doc[0],dict) and F_ID in doc[0]:
                for c in doc: cards.append((str(f),c))
            # else: aux file (e.g. domains.yaml) -> skip silently
        elif isinstance(doc,dict):
            if F_ID in doc: cards.append((str(f),doc))
            # else: aux file (taxonomy/principles) -> skip silently
    return cards, meta

def load_taxonomy(path):
    p=Path(path)
    if not p.exists(): return FALLBACK_TAX, False
    doc=load_yaml(p) or {}
    tax={k: doc.get(k, FALLBACK_TAX[k]) for k in FALLBACK_TAX}
    return tax, True

def load_domains(path):
    p=Path(path)
    if not p.exists(): return None
    doc=load_yaml(p)
    if isinstance(doc,list):
        return {d["name"] if isinstance(d,dict) and "name" in d else str(d) for d in doc}
    if isinstance(doc,dict) and "domains" in doc:
        return {d["name"] for d in doc["domains"] if isinstance(d,dict)}
    return None

def dir_prefix(v):
    return str(v or "").split(" - ",1)[0].split(" — ",1)[0].strip()

def main():
    ap=argparse.ArgumentParser(description="OSMS catalog validator (production structure)")
    ap.add_argument("paths",nargs="+")
    ap.add_argument("--taxonomy",default="catalog/taxonomy.yaml")
    ap.add_argument("--domains",default="catalog/domains.yaml")
    ap.add_argument("--expect-count",type=int,default=None)
    ap.add_argument("--json",default=None)
    ap.add_argument("--strict",action="store_true")
    a=ap.parse_args()

    rep=Report()
    cards, meta = load_files(a.paths, rep)
    if not cards: print("ERROR: no cards found",file=sys.stderr); sys.exit(2)
    tax, tax_loaded = load_taxonomy(a.taxonomy)
    domains = load_domains(a.domains)
    # header calculation_types may extend the taxonomy (report drift)
    header_calc=[c.get("name") for c in (meta.get("calculation_types") or []) if isinstance(c,dict)]
    calc_allowed=set(tax["calculation_types"]) | set(header_calc)
    drift=set(header_calc)-set(tax["calculation_types"])
    if drift:
        rep.warn("taxonomy_drift","-",
            f"calculation_types im Katalog-Header, aber nicht in taxonomy.yaml: {sorted(drift)}")

    ids={}
    helpers=[]
    lifecycle_missing = all("lifecycle" not in c for _,c in cards)
    for src,c in cards:
        cid=c.get(F_ID) or f"<no-id in {src}>"
        # required completeness
        for req in REQUIRED:
            v=c.get(req)
            if v in (None,"",[],{}):
                rep.err("required_fields",cid,f"missing/empty field '{req}'")
        # id
        if cid in ids: rep.err("id_uniqueness",cid,f"duplicate id (also in {ids[cid]})")
        ids[cid]=src
        if not re.match(ID_PATTERN,str(cid)):
            rep.err("id_pattern",cid,f"id does not match {ID_PATTERN}")
        # enums
        if c.get(F_TYPE) not in tax["indicator_types"]:
            rep.err("card_types",cid,f"invalid type '{c.get(F_TYPE)}'")
        if c.get(F_PRIO) not in tax["priorities"]:
            rep.err("priorities",cid,f"invalid priority '{c.get(F_PRIO)}'")
        if c.get(F_LAG) not in tax["lag_types"]:
            rep.err("lag_types",cid,f"invalid lag_type '{c.get(F_LAG)}'")
        if c.get(F_CALC) not in calc_allowed:
            rep.warn("calculation_type_drift",cid,
                f"calculation_type '{c.get(F_CALC)}' weder in taxonomy.yaml noch im Katalog-Header deklariert")
        dp=dir_prefix(c.get(F_DIR))
        if dp not in tax["directions"]:
            rep.err("direction",cid,f"direction prefix '{dp}' not in taxonomy")
        # domains
        if domains is not None and c.get(F_DOMAIN) not in domains:
            rep.err("domains",cid,f"domain '{c.get(F_DOMAIN)}' not in domains.yaml")
        # list fields really lists
        for lf in LIST_FIELDS:
            if not isinstance(c.get(lf),list) or not c.get(lf):
                rep.err("list_fields",cid,f"'{lf}' must be a non-empty list")
        # fail-closed: Ratio needs '/' and explicit Nenner
        if c.get(F_CALC)=="Ratio":
            if "/" not in str(c.get(F_FORMULA,"")):
                rep.err("fail_closed",cid,"Ratio without '/' in formula")
            nd=str(c.get(F_NUMDEN,""))
            has_words=re.search(r"(Nenner|Denominator|Zaehler|Z\u00e4hler|Numerator)",nd,re.IGNORECASE)
            has_slash=("/" in nd and all(part.strip() for part in nd.split("/",1)))
            if not (has_words or has_slash):
                rep.err("fail_closed",cid,"Ratio without recognizable numerator/denominator in numerator_denominator")
        # evidence fields inside minimum_data_fields
        mf=set(map(str,c.get(F_MINFIELDS) or []))
        missing=EVIDENCE_MIN-mf
        if missing:
            rep.err("evidence_fields",cid,f"minimum_data_fields missing {sorted(missing)}")
        # data confidence gates 70/85
        dc=str(c.get(F_CONF,""))
        if not (re.search(r"\b70\b",dc) and re.search(r"\b85\b",dc)):
            rep.warn("data_confidence",cid,"gates 70/85 not both referenced in data_confidence")
        # decision + version break substance
        if len(str(c.get(F_DECISION,"")).strip())<30:
            rep.err("decision_chain",cid,"decision_chain too short - no metric without a decision")
        if len(str(c.get(F_BREAK,"")).strip())<15:
            rep.err("version_break_rule",cid,"version_break_rule too short")
        # drilldown path <= 4 nodes (3 arrows) in the 'Pfad:' segment
        dl=str(c.get(F_DRILL,""))
        m=re.search(r"(?:Pfad|Path):\s*(.+)$",dl)
        if m and len(__import__("re").findall(r"(?:\u2192|->)",m.group(1)))>3:
            rep.warn("drilldown_lineage",cid,"Pfad has more than 4 steps to evidence")
        if "threshold_modes" in tax:
            tm_head=str(c.get(F_TMODE,"")).split(" \u2014 ")[0].split(" - ")[0].strip()
            if tm_head not in tax["threshold_modes"]:
                rep.warn("threshold_mode",cid,f"threshold_mode-Kopf '{tm_head[:40]}' nicht in taxonomy.threshold_modes")
        # helper consistency: status 'helper' <-> threshold_mode mentions Helper
        is_helper = c.get(F_STATUS)=="helper"
        tm=str(c.get(F_TMODE,""))
        if is_helper: helpers.append(cid)
        if is_helper and "elper" not in tm:
            rep.warn("helper_cards",cid,"status=helper but threshold_mode does not mark it as helper")
        if (not is_helper) and tm.startswith("Helper"):
            rep.warn("helper_cards",cid,"threshold_mode says Helper but status is not 'helper'")

    # meta / header checks
    if not meta.get("license"):
        rep.warn("license_meta","-","catalog header has no license block")
    counts=meta.get("counts") or {}
    if counts.get("cards") not in (None,len(cards)):
        rep.err("card_count","-",f"header counts.cards={counts.get('cards')} but found {len(cards)}")
    if a.expect_count and len(cards)!=a.expect_count:
        rep.err("card_count","-",f"expected {a.expect_count} cards, found {len(cards)}")
    used_domains={c.get(F_DOMAIN) for _,c in cards}
    if domains is not None:
        unused=sorted(domains-used_domains)
        if unused:
            rep.warn("domains","-",f"{len(unused)} Eintraege in domains.yaml ohne Cards: {unused[:6]}{'...' if len(unused)>6 else ''}")
        if counts.get("domains") not in (None,len(used_domains)):
            rep.warn("domains","-",f"header counts.domains={counts.get('domains')} but cards use {len(used_domains)} distinct domains")
    if lifecycle_missing:
        rep.warn("lifecycle","-","field 'lifecycle' (stable/draft/deprecated) fehlt katalogweit - vor dem 1.0-Freeze ergaenzen (Freeze-Kriterium 2)")
    if not tax_loaded:
        rep.warn("taxonomy","-","taxonomy.yaml not found - built-in enums used")

    rep.checks={"card_count":len(cards),"unique_ids":len(ids),
        "p0_cards":sum(1 for _,c in cards if c.get(F_PRIO)=="P0"),
        "helper_cards":len(helpers),
        "by_type":{t:sum(1 for _,c in cards if c.get(F_TYPE)==t) for t in tax["indicator_types"]},
        "distinct_domains":len(used_domains)}

    for e in rep.errors:   print(f"ERROR   [{e['check']}] {e['card']}: {e['message']}")
    for w in rep.warnings: print(f"WARNING [{w['check']}] {w['card']}: {w['message']}")
    ok = not rep.errors and not (a.strict and rep.warnings)
    print("-"*72)
    print(f"cards: {rep.checks['card_count']} | unique ids: {rep.checks['unique_ids']} "
          f"| P0: {rep.checks['p0_cards']} | helpers(status): {rep.checks['helper_cards']} "
          f"| domains used: {rep.checks['distinct_domains']}")
    print(f"errors: {len(rep.errors)} | warnings: {len(rep.warnings)} | result: {'PASS' if ok else 'FAIL'}")
    if a.json:
        Path(a.json).write_text(json.dumps({"result":"pass" if ok else "fail",
            "summary":rep.checks,"errors":rep.errors,"warnings":rep.warnings},
            indent=1,ensure_ascii=False),encoding="utf-8")
        print(f"json report: {a.json}")
    sys.exit(0 if ok else 1)

if __name__=="__main__":
    main()
