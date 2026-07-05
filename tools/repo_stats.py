#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
repo_stats.py — private repository numbers, visible only to you.

Requires the GitHub CLI ('gh') authenticated with push access to the repo
(traffic data is only served to users with push access — that's the privacy).

Usage (e.g. in a Codespace terminal):
    python tools/repo_stats.py --repo OpenSecurityMetricsStandard/OSMS

Shows:
  - Repo visits: views + unique visitors, last 14 days (GitHub Insights data)
  - Clones: count + unique cloners, last 14 days
  - Top referrers (where visitors came from)
  - Release asset downloads per file (all-time, from the Releases API)
  - Stars / forks / watchers

Note: traffic and referrer data covers a rolling 14-day window and is private.
Release download counts are technically readable by anyone via the public API.
"""
import argparse, json, subprocess, sys

def gh(args):
    r = subprocess.run(["gh"] + args, capture_output=True, text=True)
    if r.returncode != 0:
        print("gh error:", r.stderr.strip(), file=sys.stderr); sys.exit(2)
    return json.loads(r.stdout) if r.stdout.strip() else {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, help="OWNER/REPO")
    a = ap.parse_args()
    R = a.repo

    views = gh(["api", f"repos/{R}/traffic/views"])
    clones = gh(["api", f"repos/{R}/traffic/clones"])
    refs = gh(["api", f"repos/{R}/traffic/popular/referrers"])
    meta = gh(["api", f"repos/{R}"])
    rels = gh(["api", f"repos/{R}/releases"])

    print(f"Repo stats — {R} (traffic = last 14 days, private to you)")
    print("-" * 66)
    print(f"Views:  {views.get('count', 0):>6}  ({views.get('uniques', 0)} unique visitors)")
    print(f"Clones: {clones.get('count', 0):>6}  ({clones.get('uniques', 0)} unique cloners)")
    print(f"Stars: {meta.get('stargazers_count', 0)} · Forks: {meta.get('forks_count', 0)} · Watchers: {meta.get('subscribers_count', 0)}")
    if refs:
        print("\nTop referrers (last 14 days):")
        for r in refs[:8]:
            print(f"  {r['referrer']:<28} {r['count']:>5} views ({r['uniques']} unique)")
    total = 0
    lines = []
    for rel in rels:
        for asset in rel.get("assets", []):
            total += asset["download_count"]
            lines.append(f"  {rel['tag_name']:<10} {asset['name']:<38} {asset['download_count']:>6}")
    print(f"\nRelease downloads (all-time): {total}")
    for l in lines:
        print(l)
    if not lines:
        print("  (no release assets yet)")

if __name__ == "__main__":
    main()
