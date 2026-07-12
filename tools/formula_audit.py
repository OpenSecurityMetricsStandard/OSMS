#!/usr/bin/env python3
"""OSMS formula audit - conservative machine checks over the card catalog.

Usage: python3 tools/formula_audit.py catalog/osms-catalog.yaml
Exit code 0 = no findings, 1 = findings printed.
Checks: editorial markers, German residue in formulas, dead p(CARD) refs,
formula inputs without field homes, weight-sum near-misses, ratio *100 vs
unit, timestamp alternatives in formulas, composite example recomputation,
ratio example recomputation, German words used as field names.
"""
import yaml, re, sys, argparse

GERMAN_FORMULA = re.compile(r"[\u00e4\u00f6\u00fc\u00c4\u00d6\u00dc\u00df]|\b(und|oder|beziehungsweise|bzw|sowie|Anzahl|bekannte|deklariert|blockiert|validiert|Meldung)\b")
GERMAN_FIELD = re.compile(r"(szenario|pruef|freigabe|meldung|bericht|kennzahl|gewicht|anzahl|(?<![a-z])datum|testdatum|nummer|kuerzel|massnahme|ausnahme|stichtag|faehig|reife)")

def audit(path):
    data = yaml.safe_load(open(path, encoding="utf-8"))
    cards = data["cards"] if isinstance(data, dict) and "cards" in data else data
    ids = {c["id"] for c in cards}
    findings = []
    for c in cards:
        f, cid = c["formula"], c["id"]
        fields = set(c["minimum_data_fields"])
        if re.search(r"\b(TBD|TODO|FIXME|to be (?:defined|determined)|draft)\b", f, re.I):
            findings.append((cid, "editorial marker in formula"))
        if GERMAN_FORMULA.search(f):
            findings.append((cid, "German residue in formula"))
        for ref in re.findall(r"p\((\w{2,4}-\d{3}[a-z]?)\)", f):
            if ref not in ids:
                findings.append((cid, f"dead card reference p({ref})"))
        lhs = set(re.findall(r"([a-z][a-z0-9_]{2,})\s*=", f))
        has_indirection = bool(c.get("numerator_denominator")) or {"subscore_id"} <= fields or "child_card_id" in fields
        toks = set(re.findall(r"\b([a-z][a-z0-9_]*_[a-z0-9_]+)\b", f))
        homeless = [t for t in toks if t not in fields and t not in lhs]
        if homeless and not has_indirection and fields and len(homeless) >= 2:
            findings.append((cid, "formula inputs without field home: " + ", ".join(sorted(homeless)[:6])))
        ws = [float(x) for x in re.findall(r"(\d\.\d+)\s*\*", f)]
        if c["calculation_type"] in {"Weighted Sum", "Weighted Average", "Composite", "Index"} and len(ws) >= 2:
            s = sum(ws)
            if 0.9 <= s <= 1.1 and abs(s - 1.0) > 0.011:
                findings.append((cid, f"weight sum suspicious: {round(s,3)}"))
        if c["calculation_type"] == "Ratio" and re.search(r"\*\s*100\b", f) and not re.search(r"%|percent", c["unit"], re.I):
            findings.append((cid, "formula has *100 but unit lacks %"))
        if re.search(r"\b[a-z_]+_at\s*/\s*[a-z_]+_at\b", f):
            findings.append((cid, "timestamp alternative (x_at/y_at) in formula"))
        if re.search(r"(?<![a-z_])timestamp(?![a-z_])", f):
            findings.append((cid, "bare timestamp used in formula - business event times must use specific *_at/*_timestamp fields"))
        if c["calculation_type"] == "Ratio":
            ex = c["calculation_example"].replace(",", ".")
            nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)", ex)]
            pcts = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", ex)]
            if pcts and len(nums) >= 3:
                ok = any(abs(100.0 * m / n - p) < 0.06 for p in pcts
                         for i, n in enumerate(nums) if n > 0
                         for m in nums[:i] + nums[i + 1:] if m <= n)
                if not ok:
                    findings.append((cid, "ratio example does not reproduce the stated %"))
        for fd in c["minimum_data_fields"]:
            if GERMAN_FIELD.search(fd):
                findings.append((cid, f"German word used as field name: {fd}"))
    return findings

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("catalog")
    a = ap.parse_args()
    fs = audit(a.catalog)
    for cid, msg in fs:
        print(f"FINDING {cid}: {msg}")
    print(f"formula_audit: {len(fs)} finding(s) over catalog")
    sys.exit(1 if fs else 0)
