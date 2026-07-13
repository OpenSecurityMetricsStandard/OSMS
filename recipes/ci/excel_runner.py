#!/usr/bin/env python3
"""LibreOffice engine verification for the OSMS Excel (range-model) dialect.

The recipe-CI `gates` job already recomputes the 14 fixtures in the pure-Python
`formulas` engine (gate [9]). This runner is the independent second engine: it
rebuilds the same workbooks from the same spec and recomputes them in LibreOffice
Calc, so a published Excel formula is proven to agree across two engines rather
than being an artefact of one library.

Fixture pass: for every fixture card, load its rows onto the `data` sheet, set the
parameters on the `result` sheet, convert with LibreOffice, and require the result
cell(s) to match the card's expected values exactly (tol 1e-4).

Empty pass: every published candidate must compute on an empty `data` sheet to a
number or the fail-closed sentinel #N/A — never a broken-formula error
(#NAME?/#REF!/#VALUE!/#DIV/0!). This proves each formula's functions and range
references are valid and that fail-closed actually fires with no rows.

Usage:
  python3 recipes/ci/excel_runner.py --out recipes/out                 # LibreOffice
  python3 recipes/ci/excel_runner.py --out recipes/out --dry-run       # formulas engine only
  python3 recipes/ci/excel_runner.py --out recipes/out --max-empty 40  # subset empty pass
"""
import json, os, sys, argparse, tempfile, shutil, time

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_here))          # recipes/ on path -> xlsx_dialect
import xlsx_dialect as X

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="recipes/out")
ap.add_argument("--dry-run", action="store_true", help="use the pure-Python formulas engine, no LibreOffice")
ap.add_argument("--soffice", default="soffice")
ap.add_argument("--timeout", type=int, default=120)
ap.add_argument("--max-empty", type=int, default=0, help="cap empty-pass cards from the offset (0 = all)")
ap.add_argument("--empty-offset", type=int, default=0, help="start index into the candidate list (sharding)")
ap.add_argument("--skip-fixtures", action="store_true", help="skip the fixture pass (empty pass only)")
A = ap.parse_args()

XC = json.load(open(os.path.join(A.out, "excel_candidates.json")))["candidates"]
FX = json.load(open(os.path.join(A.out, "fixtures.json")))

OKERR = {"#N/A"}                                     # fail-closed sentinel is acceptable
BADERR = {"#NAME?", "#REF!", "#VALUE!", "#DIV/0!"}   # broken-formula errors are not

tmp = tempfile.mkdtemp(prefix="osms_xlsx_")
prof = "file://" + os.path.join(tmp, "loprofile")
report = {"engine": "formulas" if A.dry_run else "libreoffice",
          "fixtures": [], "empty": {"pass": 0, "fail": []}}


def evaluate(spec, fixture, path):
    orows = X.build_workbook(spec, fixture, path)
    if A.dry_run:
        return X.eval_formulas(path, orows)
    last = None
    for _ in range(2):                               # one retry: soffice can flake under load
        try:
            r = X.eval_libreoffice(path, orows, soffice=A.soffice, timeout=A.timeout,
                                   user_installation=prof)
            if any(v is not None for v in r.values()):
                return r
            last = r
        except Exception as e:
            last = {k: "#ERR:%s" % str(e)[:40] for k in orows}
        time.sleep(1)
    return last or {k: None for k in orows}


# ---------------- fixture pass: exact cross-engine agreement ----------------
fx_fail = 0
for f in (FX if not A.skip_fixtures else []):
    cid = f["card"]
    if cid not in XC:
        continue
    got = evaluate(XC[cid]["spec"], f, os.path.join(tmp, "fx_" + cid + ".xlsx"))
    bad = {}
    for k, exp in f["expect"].items():
        gv = got.get(k)
        if not (isinstance(gv, float) and abs(gv - float(exp)) < 1e-4):
            bad[k] = {"expected": exp, "got": gv}
    report["fixtures"].append({"card": cid, "result": got, "mismatches": bad})
    if bad:
        fx_fail += 1; print("FIXTURE FAIL", cid, bad)
    else:
        print("FIXTURE PASS", cid, {k: got.get(k) for k in f["expect"]})

# ---------------- empty pass: fail-closed, no broken-formula errors ----------------
cids = list(XC.keys())[A.empty_offset:]
if A.max_empty > 0:
    cids = cids[:A.max_empty]
for i, cid in enumerate(cids, 1):
    got = evaluate(XC[cid]["spec"], {"rows": []}, os.path.join(tmp, "empty_" + cid + ".xlsx"))
    problems = []
    for k, v in got.items():
        if isinstance(v, float):
            continue
        s = str(v).strip()
        if s in OKERR:
            continue
        problems.append("%s=%s" % (k, v if v is not None else "None"))
    if problems:
        report["empty"]["fail"].append({"card": cid, "cells": problems})
        print("EMPTY FAIL", cid, problems)
    else:
        report["empty"]["pass"] += 1
    if i % 25 == 0:
        print("  ...empty pass %d/%d (%d ok)" % (i, len(cids), report["empty"]["pass"]))

json.dump(report, open(os.path.join(A.out, "excel_report.json"), "w"), indent=1)
shutil.rmtree(tmp, ignore_errors=True)

ef = len(report["empty"]["fail"])
fx_run = len(report["fixtures"])
print("\nengine=%s | fixtures: %d/%d exact | empty[%d:%d]: %d/%d fail-closed | fixture fails: %d | empty fails: %d"
      % (report["engine"], fx_run - fx_fail, fx_run, A.empty_offset, A.empty_offset + len(cids),
         report["empty"]["pass"], len(cids), fx_fail, ef))
sys.exit(1 if (fx_fail or ef) else 0)
