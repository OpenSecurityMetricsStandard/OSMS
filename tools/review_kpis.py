#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
review_kpis.py — measures the OSMS 0.9 public review against the published Review KPIs.

Requires the GitHub CLI ('gh', authenticated: gh auth login).

Usage (Friday routine, ~1 minute):
    python tools/review_kpis.py --repo OWNER/REPO --catalog catalog/ \
        --extra-findings 3 --extra-reviewers 2 --exclude YOUR_GH_LOGIN --markdown

    --extra-findings / --extra-reviewers  add form/email submissions counted manually
    --exclude        your own login(s), so you don't count as an external reviewer
    --markdown       prints a ready-to-paste weekly status post (GitHub Discussion)
    --no-triage      skip the per-issue events calls (faster; triage time shows n/a)
"""
import argparse, json, re, statistics, subprocess, sys
from datetime import datetime, timezone

CATS = ["card-contract", "formula", "data-source", "data-confidence", "taxonomy", "domain",
        "decision-chain", "evidence", "hierarchy", "board-relevance", "implementation", "language"]
DECISIONS = ["accepted", "rejected", "deferred", "accepted-risk", "breaking"]

def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("gh error:", r.stderr.strip(), file=sys.stderr); sys.exit(2)
    return r.stdout

def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def body_field(body, heading):
    m = re.search(rf"###\s*{re.escape(heading)}\s*\n+\s*(.+)", body or "", re.IGNORECASE)
    return m.group(1).strip() if m else None

def load_catalog_ids(path):
    try:
        import yaml
    except ImportError:
        return None, None
    from pathlib import Path
    p = Path(path)
    files = ([p] if p.is_file() else sorted(p.rglob("*.yaml")) + sorted(p.rglob("*.yml"))) if p.exists() else []
    ids, p0 = set(), set()
    for f in files:
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        cards = doc.get("cards", doc if isinstance(doc, list) else [doc])
        for c in cards or []:
            if isinstance(c, dict) and c.get("id"):
                ids.add(c["id"])
                if c.get("priority") == "P0": p0.add(c["id"])
    return (ids or None), (p0 or None)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--catalog", default="catalog/")
    ap.add_argument("--id-pattern", default=r"OSMS-[A-Za-z0-9._-]+")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--extra-findings", type=int, default=0)
    ap.add_argument("--extra-reviewers", type=int, default=0)
    ap.add_argument("--no-triage", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    a = ap.parse_args()

    issues = json.loads(gh(["issue", "list", "-R", a.repo, "--label", "finding", "--state", "all",
                            "--limit", "500", "--json",
                            "number,title,body,author,createdAt,state,labels"]))
    excl = {e.lower() for e in a.exclude}
    labels = lambda i: {l["name"] for l in i.get("labels", [])}

    # K-01 active external reviewers
    reviewers = {i["author"]["login"].lower() for i in issues
                 if i.get("author") and i["author"]["login"].lower() not in excl}
    k01 = len(reviewers) + a.extra_reviewers
    # K-02 findings total
    k02 = len(issues) + a.extra_findings
    # K-03 per category (label first, issue-form body as fallback)
    percat = {c: 0 for c in CATS}
    for i in issues:
        cat = next((l.split(":", 1)[1] for l in labels(i) if l.startswith("cat:")), None)
        if not cat:
            bf = body_field(i.get("body"), "Category")
            if bf:
                cat = bf.lower().replace(" / ", "-").replace(" ", "-")
                cat = {"helper-parent-child": "hierarchy"}.get(cat, cat)
        if cat in percat: percat[cat] += 1
    # severity (label first, body fallback)
    def sev(i):
        s = next((l.split(":", 1)[1] for l in labels(i) if l.startswith("severity:")), None)
        return s or (body_field(i.get("body"), "Severity") or "").lower() or None
    # K-08 open criticals
    k08 = sum(1 for i in issues if i["state"] == "OPEN" and sev(i) == "critical")
    # K-07 decision quota
    decided = sum(1 for i in issues if any(l.startswith("decision:") for l in labels(i)))
    cm = [i for i in issues if sev(i) in ("critical", "major")]
    cm_decided = sum(1 for i in cm if any(l.startswith("decision:") for l in labels(i)))
    # K-04/K-05 card coverage
    all_ids, p0_ids = load_catalog_ids(a.catalog)
    touched = set()
    for i in issues:
        touched |= set(re.findall(a.id_pattern, (i.get("title") or "") + "\n" + (i.get("body") or "")))
    cov_all = f"{len(touched & all_ids)}/{len(all_ids)} ({100*len(touched & all_ids)/len(all_ids):.0f} %)" if all_ids else f"{len(touched)} IDs referenced (catalog not loaded)"
    cov_p0 = f"{len(touched & p0_ids)}/{len(p0_ids)} ({100*len(touched & p0_ids)/len(p0_ids):.0f} %)" if p0_ids else "n/a"
    # K-06 median triage time (creation -> first severity label)
    k06 = "n/a"
    if not a.no_triage and issues:
        hours = []
        for i in issues[:100]:
            evs = json.loads(gh(["api", f"repos/{a.repo}/issues/{i['number']}/events", "--paginate"]))
            t = next((parse_dt(e["created_at"]) for e in evs
                      if e.get("event") == "labeled" and e.get("label", {}).get("name", "").startswith("severity:")), None)
            if t: hours.append((t - parse_dt(i["createdAt"])).total_seconds() / 3600)
        if hours: k06 = f"{statistics.median(hours)/24:.1f} d (median, n={len(hours)})"

    today = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    rows = [
        ("K-01 Active external reviewers", k01, "CP1 >=4 | CP2 >=8 | Freeze >=10"),
        ("K-02 Findings total", k02, "CP1 >=10 | CP2 >=25 | Freeze >=40"),
        ("K-04 Card coverage P0", cov_p0, "CP2 >=60 % | Freeze 100 %"),
        ("K-05 Card coverage overall", cov_all, "CP2 >=15 % | Freeze >=30 %"),
        ("K-06 Median triage time", k06, "<= 5 working days"),
        ("K-07 Decisions taken", f"{decided}/{k02}  (crit+major: {cm_decided}/{len(cm)})", "Freeze: 100 % crit+major, >=90 % overall"),
        ("K-08 Open critical findings", k08, "Freeze: 0"),
    ]
    print(f"OSMS Review KPIs — {a.repo} — {today}")
    print("-" * 78)
    for n, v, t in rows: print(f"{n:34} {str(v):28} target: {t}")
    print("-" * 78)
    print("K-03 Findings by category:", ", ".join(f"{c}={n}" for c, n in percat.items() if n) or "none yet")

    if a.markdown:
        print("\n----- paste into GitHub Discussions: 'Review Status' -----\n")
        print(f"## Review status — {today}\n")
        print("| KPI | Current | Target |\n|---|---|---|")
        for n, v, t in rows: print(f"| {n} | {v} | {t} |")
        cats = ", ".join(f"{c} ({n})" for c, n in sorted(percat.items(), key=lambda x: -x[1]) if n)
        print(f"\n**Findings by category:** {cats or 'none yet'}")
        print("\nAll definitions: see REVIEW_PROCESS.md. Submit findings via the "
              "[Review Finding template](../../issues/new/choose) or review@opensecuritymetrics.org.")

if __name__ == "__main__":
    main()
