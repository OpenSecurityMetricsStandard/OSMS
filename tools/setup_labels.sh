#!/usr/bin/env bash
# Creates all OSMS review labels. Usage: bash tools/setup_labels.sh owner/repo
set -e
R="${1:?usage: setup_labels.sh owner/repo}"
L(){ gh label create "$1" --repo "$R" --color "$2" --description "$3" --force; }
# process
L "finding"            "1F3A5F" "Review finding against OSMS 0.9"
L "triage"             "C9CDD4" "Awaiting triage (category + severity)"
# severity
L "severity:critical"  "B60205" "Blocks the 1.0 freeze"
L "severity:major"     "D93F0B" "Must be decided before freeze"
L "severity:minor"     "FBCA04" "Editorial / low impact"
# categories (12)
L "cat:card-contract"  "0E8A16" "Card Contract"
L "cat:formula"        "0E8A16" "Formula"
L "cat:data-source"    "0E8A16" "Data Source"
L "cat:data-confidence" "0E8A16" "Data Confidence"
L "cat:taxonomy"       "0E8A16" "Taxonomy"
L "cat:domain"         "0E8A16" "Domain"
L "cat:decision-chain" "0E8A16" "Decision Chain"
L "cat:evidence"       "0E8A16" "Evidence"
L "cat:hierarchy"      "0E8A16" "Helper / Parent / Child"
L "cat:board-relevance" "0E8A16" "Board Relevance"
L "cat:implementation" "0E8A16" "Implementation"
L "cat:language"       "0E8A16" "Language"
# review board decisions
L "decision:accepted"      "2E7D32" "Accepted into v1.0"
L "decision:rejected"      "5A6472" "Rejected with rationale"
L "decision:deferred"      "6A1B9A" "Deferred to v1.1 backlog"
L "decision:accepted-risk" "C9A227" "Known risk, not a v1.0 blocker"
L "decision:breaking"      "000000" "Blocks freeze until resolved"
echo "done: labels created/updated in $R"
