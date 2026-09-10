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
    graph = {c['id']: set(re.findall(r'p\(([A-Z]{2,4}-\d{3}[a-z]?)\)', c['formula'])) for c in cards}
    visited, active = set(), []
    def visit(cid):
        if cid in active:
            findings.append((cid, 'cyclic formula dependency: ' + ' -> '.join(active[active.index(cid):] + [cid])))
            return
        if cid in visited or cid not in graph:
            return
        active.append(cid)
        for child in sorted(graph[cid]):
            visit(child)
        active.pop()
        visited.add(cid)
    for cid in sorted(graph):
        visit(cid)
    for c in cards:
        f, cid = c["formula"], c["id"]
        fields = set(c["minimum_data_fields"])
        if re.search(r'/\s*0(?:\.0+)?(?![\d.])(?:\b|\s|$)', f):
            findings.append((cid, 'literal zero denominator'))
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
        # Recompute only an explicit numeric equation. Combining arbitrary
        # numbers from prose can make an incorrect result verify itself
        # (e.g. the result 99 and scale 100 in "3/4*100 = 99%"). A ratio may
        # instead be an event rate or an unscaled quotient; an ancillary
        # percentage in its prose does not change the equation's scale.
        if c["calculation_type"] == "Ratio":
            ex = c["calculation_example"].replace(",", ".")
            number=r'-?\d+(?:\.\d+)?'
            equation=rf'(?<![\w.])({number})\s*/\s*({number})\s*(?:\*\s*(100(?:\.0+)?))?\s*=\s*({number})\s*(%?)'
            for match in re.finditer(equation,ex):
                numerator,denominator,scale,stated,pct=match.groups()
                factor=float(scale) if scale else 100.0 if pct else 1.0
                digits=len(stated.split('.')[1]) if '.' in stated else 0
                tolerance=0.5*10**(-digits)+1e-10
                if float(denominator)==0 or abs(float(numerator)/float(denominator)*factor-float(stated))>tolerance:
                    findings.append((cid, 'ratio example does not reproduce the stated numeric equation'))
        for fd in c["minimum_data_fields"]:
            if GERMAN_FIELD.search(fd):
                findings.append((cid, f"German word used as field name: {fd}"))
        # Only claim a numeric check where assignments and a final result are
        # explicit. This is not a parser for all 327 free-text examples.
        function = re.search(r'p\(([^)]*)\)\s*=\s*([^;]+)', f)
        if function and c['calculation_type'] == 'Composite':
            terms = re.findall(r'(\d*\.?\d+)\s*\*\s*([a-z_][a-z0-9_]*)', function.group(2))
            ex = c['calculation_example']
            inputs = {name: re.search(r'\b' + re.escape(name) + r'\s*=\s*(-?\d+(?:\.\d+)?)', ex) for _, name in terms}
            stated = re.findall(r'=\s*(-?\d+(?:\.\d+)?)\s*(?:→|->)', ex)
            if terms and stated and all(inputs.values()):
                calculated = sum(float(weight) * float(inputs[name].group(1)) for weight, name in terms)
                if abs(calculated - float(stated[-1])) > 1e-8:
                    findings.append((cid, f'composite example result {stated[-1]} != {calculated}'))
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
