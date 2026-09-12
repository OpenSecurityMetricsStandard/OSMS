#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute hand-specified F-03/F-06 issue examples in a native local DAX model."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "recipes/ci"), str(ROOT / "recipes")]
import audit_issue_examples
from desktop_runner import execute, fixture_hash
from semantic_runner import equal

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", default="recipes/out")
    parser.add_argument("--server", required=True)
    parser.add_argument("--tom-assembly", required=True)
    parser.add_argument("--adomd-assembly", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("An actual Windows DAX runtime is required")
    source = ROOT / args.bundle / "execution-profiles.json"
    bundle = json.loads(source.read_bytes())
    for name, expected in bundle["source_files_sha256"].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Stale source: " + name)
    # Nonfinite strings require separate native model-ingestion rejection probes.
    fixtures = [(cid, profile, case) for cid, profile, case in
                audit_issue_examples.fixtures(bundle)
                if not case["name"].endswith("_text")]
    report = dict(
        engine="dax", execution_kind="native_desktop",
        stage="audit_issue_supplements",
        started_at=datetime.now(timezone.utc).isoformat(),
        profile_bundle_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        source_files_sha256=bundle["source_files_sha256"],
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        fixture_generator_sha256=hashlib.sha256(
            Path(audit_issue_examples.__file__).read_bytes()).hexdigest(),
        required_cases=len(fixtures), cases=[], aborted=False,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    def save():
        out.write_bytes((json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode())
    with tempfile.TemporaryDirectory(prefix="osms-dax-issue-") as folder:
        for cid, profile, case in fixtures:
            row = dict(card_id=cid, case_id=case["name"], fixture=case,
                       fixture_sha256=fixture_hash(case),
                       expected=case["expected"], status="fail")
            try:
                actual, version = execute(profile, case, "dax", Path(folder), args, True)
                report["engine_version"] = version
                errors = [name for name, expected in case["expected"].items()
                          if name not in actual or not equal(
                              actual[name], expected,
                              profile["plan"]["output_contracts"].get(name))]
                if case.get("status") and actual.get("evaluation_status") != case["status"]:
                    errors.append("evaluation_status")
                row.update(actual=actual, failed_outputs=errors,
                           status="fail" if errors else "pass")
            except Exception as exc:
                row["error"] = str(exc)
                if isinstance(exc, subprocess.CalledProcessError):
                    row["error"] += " " + str(exc.stderr)[:4000]
                report["aborted"] = True
            report["cases"].append(row)
            save()
            print(cid, case["name"], row["status"], row.get("failed_outputs", row.get("error")), flush=True)
            if report["aborted"]:
                break
    report.update(completed_at=datetime.now(timezone.utc).isoformat(),
                  passed=sum(row["status"] == "pass" for row in report["cases"]))
    report["failed"] = len(report["cases"]) - report["passed"]
    save()
    print(report["passed"], "passed;", report["failed"], "failed", flush=True)
    return int(report["aborted"] or report["failed"] or len(report["cases"]) != len(fixtures))

if __name__ == "__main__":
    raise SystemExit(main())
