#!/usr/bin/env python3
"""Curate the OSMS readiness source taxonomy from the live catalog.
Emits source_taxonomy.yaml (classes, groups, mapping) and reports unmapped strings."""
import yaml, re, collections, sys, json

import os
CAT = os.environ.get("OSMS_CATALOG", "catalog/osms-catalog.yaml")

# ---------------------------------------------------------------- classes
# id, label (EN, user-facing), group id
CLASSES = [
    # Detection & Response
    ("siem",              "SIEM",                                            "detect"),
    ("soar",              "SOAR & response playbooks",                       "detect"),
    ("case_mgmt",         "Case management & threat hunting",                "detect"),
    ("detection_repo",    "Detection rule repository (detection-as-code)",   "detect"),
    ("threat_intel",      "Threat intelligence platform & feeds",            "detect"),
    ("telemetry_pipeline","Log pipeline & telemetry health",                 "detect"),
    ("ai_soc_mlops",      "AI SOC / ML operations platform",                 "detect"),
    # Endpoint & Network
    ("edr",               "EDR / XDR & endpoint telemetry",                  "endpoint"),
    ("endpoint_mgmt",     "Endpoint management (MDM/UEM, config, imaging)",  "endpoint"),
    ("email_sec",         "Email security gateway & report-button telemetry","endpoint"),
    ("network_sec",       "Network security (firewall, IDS/NDR, NAC, VPN)",  "endpoint"),
    ("proxy_swg",         "Web proxy / secure web gateway",                  "endpoint"),
    ("ot_iot",            "OT / ICS & IoT platforms",                        "endpoint"),
    # Identity & Access
    ("idp_iam",           "Identity provider / IAM / directory",             "identity"),
    ("pam",               "PAM & break-glass records",                       "identity"),
    ("iga_reviews",       "Access reviews & identity governance",            "identity"),
    ("secrets_kms",       "Secrets, keys & crypto management (Vault, KMS/HSM)","identity"),
    # Vulnerability & Attack Surface
    ("vuln_scanner",      "Vulnerability scanner",                           "vuln"),
    ("vuln_intel_feeds",  "Vulnerability intel feeds (EPSS, CISA KEV)",      "vuln"),
    ("config_compliance", "Secure-configuration & benchmark scanning",       "vuln"),
    ("easm",              "EASM / external attack surface",                  "vuln"),
    ("asset_discovery",   "Asset discovery (DHCP/IPAM, network discovery)",  "vuln"),
    ("dns_cert",          "DNS, certificate & PKI inventory",                "vuln"),
    ("pentest_redteam",   "Security testing (pentest, red/purple team, BAS)","vuln"),
    # Cloud & Infrastructure
    ("cloud_platform",    "Cloud platform inventory & configuration",        "cloud"),
    ("cloud_logs",        "Cloud audit & flow logs (CloudTrail etc.)",       "cloud"),
    ("cspm",              "CSPM / CNAPP / cloud security posture",           "cloud"),
    ("container_k8s",     "Container & Kubernetes runtime",                  "cloud"),
    ("platform_audit_logs","Platform & admin audit logs",                    "cloud"),
    # Application & Supply Chain
    ("cicd_repo",         "CI/CD & source code platform",                    "appsec"),
    ("appsec_tools",      "Code & IaC security scanning (SAST/DAST/SCA)",    "appsec"),
    ("artifact_sbom",     "Artifact registries, SBOM & signing",             "appsec"),
    ("api_gateway",       "API gateway & API inventory",                     "appsec"),
    # Data Security & Privacy
    ("dlp",               "DLP (endpoint, network, cloud)",                  "data"),
    ("casb_saas",         "CASB / SaaS security & discovery",                "data"),
    ("dspm_dataclass",    "Data catalog, classification & DSPM",             "data"),
    ("privacy_tool",      "Privacy records (RoPA, DPIA, DSAR)",              "data"),
    ("backup",            "Backup & immutable storage",                      "data"),
    # GRC, Risk & Audit
    ("grc_isms",          "GRC / ISMS platform",                             "grc"),
    ("policy_repo",       "Policy repository",                               "grc"),
    ("risk_register",     "Risk register & risk quantification",             "grc"),
    ("audit_findings",    "Audit findings & control test results",           "grc"),
    ("evidence_repo",     "Evidence repository & attestations",              "grc"),
    ("metric_store",      "Metric store, KPI engine & dashboards",           "grc"),
    ("security_reference","Framework reference mappings (ATT&CK, OWASP)",    "grc"),
    # Service Management & Workforce
    ("itsm_incidents",    "ITSM, ticketing & incident register",             "ops"),
    ("workforce_ops",     "On-call, roster & workforce capacity",            "ops"),
    ("finance_cost",      "Finance, procurement & cost data",                "ops"),
    ("docs_architecture", "Architecture & design documentation",             "ops"),
    # People & Awareness
    ("hr_system",         "HR system (joiners, movers, leavers)",            "people"),
    ("lms_training",      "LMS / training platform",                         "people"),
    ("phishing_sim",      "Phishing simulation platform",                    "people"),
    ("survey_feedback",   "Surveys, feedback & internal reporting channels", "people"),
    # Third Parties & Resilience
    ("tprm",              "TPRM / supplier register & portals",              "third"),
    ("legal_contracts",   "Contracts, legal & regulator records",            "third"),
    ("cyber_insurance",   "Cyber insurance records",                         "third"),
    ("bia_bcm",           "BIA, BCM, DR & crisis management",                "resilience"),
    # AI Governance
    ("ai_governance",     "AI registry & governance (approved AI tools)",    "ai"),
]

GROUPS = [
    ("detect",    "Detection & Response"),
    ("endpoint",  "Endpoint, Email & Network"),
    ("identity",  "Identity & Access"),
    ("vuln",      "Vulnerabilities & Attack Surface"),
    ("cloud",     "Cloud & Infrastructure"),
    ("appsec",    "Applications & Supply Chain"),
    ("data",      "Data Security & Privacy"),
    ("grc",       "GRC, Risk & Audit"),
    ("ops",       "Service Management & Operations"),
    ("people",    "People & Awareness"),
    ("third",     "Third Parties & Legal"),
    ("resilience","Resilience & Continuity"),
    ("ai",        "AI Governance"),
]

# ---------------------------------------------------------------- ordered rules
# first match wins; case-insensitive search
RULES = [
    (r'^Primary evidence', None),  # handled by overrides (multi-class)
    (r'source cards|STD-\d', "metric_store"),
    # AI ops before generic
    (r'AI SOC|triage engine|reasoning trace|MLOps|model registry|prompt|evaluation (log|platform)|AI (decision|action)|override action|Re-analysis|Reviewer (log|tag)|Reversal log|Event log of AI', "ai_soc_mlops"),
    (r'AI registry|AI gateway|AI platform|cloud AI|KI-Freigabeliste|Approved-Tool', "ai_governance"),
    (r'AI red-team', "pentest_redteam"),
    (r'OWASP|ATT&CK|MITRE', "security_reference"),
    # detection stack
    (r'detection[ -](repo|repository|backlog|as-code|test)|Detection Rule|rule metadata|rule export|tuning ticket|UBA|UEBA', "detection_repo"),
    (r'SIEM (ingestion|parser|source|schema|timestamp|data catalog|deployment|event|coverage)|collector queue|source (heartbeat|counter|configuration)|log delivery|NTP|time service|data volume|enrichment (log|table)|Monitoring/Avail|Performance monitoring|freshness SLA|retention config', "telemetry_pipeline"),
    (r'SIEM|alert (statistic|backlog|queue)', "siem"),
    (r'SOAR|playbook|notification tool|IR-Pipeline|IR-Plattform', "soar"),
    (r'case management|hunt|Threat Hunting', "case_mgmt"),
    (r'threat[ -]intel|TIP\b|ISAC|Sharing-', "threat_intel"),
    (r'EPSS|KEV', "vuln_intel_feeds"),
    # endpoint & network
    (r'EDR|XDR|endpoint.*telemetr|Browser-Telemetrie|browser telemetry|tamper|agent (heartbeat|manager)|device control|device posture', "edr"),
    (r'MDM|UEM|Intune|Jamf|GPO|endpoint (config|DLP)?$|endpoint/server|Application control|golden image|BitLocker|FileVault|package deployment|software deployment|patch management', None),  # refined below
    (r'MDM|UEM|Intune|Jamf|GPO|Application control|golden image|BitLocker|FileVault|package deployment|Patch management|endpoint/server (config|management)|endpoint config', "endpoint_mgmt"),
    (r'endpoint DLP', "dlp"),
    (r'mail|DMARC|Report-Button|E-Mail', "email_sec"),
    (r'proxy|SWG|Secure Web Gateway', "proxy_swg"),
    (r'firewall|IDS|IPS|NDR|NAC\b|VPN|ZTNA|WAF|microsegment|switch|wireless|Packet Broker|network (config|log|telemetry|reachab|isolation|segmentation|security|/security)|AP data|Netzwerk-|network/security', "network_sec"),
    (r'OT |IoT|engineering workstation', "ot_iot"),
    # identity
    (r'break-glass|PAM\b', "pam"),
    (r'secrets|Vault|KMS|HSM|Key-Escrow|encryption config|Crypto librar', "secrets_kms"),
    (r'access review|IGA|IAG|attestation', None),  # attestations context-split below
    (r'access review|IGA|IAG|IAM review', "iga_reviews"),
    (r'IdP|IAM|Entra|Directory|RBAC|identity|credential health|SaaS admin', "idp_iam"),
    # vuln & surface
    (r'vulnerab|database scan|authenticated scan', "vuln_scanner"),
    (r'CIS benchmark|config (baseline|scan|scanner)|Config scanner|baseline scanner|audit policy export', "config_compliance"),
    (r'EASM|CAASM|external asset|domain inventory', "easm"),
    (r'DHCP|IPAM|network discovery|passive discovery|^discovery', "asset_discovery"),
    (r'DNS|certificate|Zertifikat|PKI|TLS', "dns_cert"),
    (r'pen[ -]?test|red[ -/]|purple|atomic|TLPT|TIBER|attack-path|Einsatzregeln|Rules of Engagement|test (harness|plan|result)|Testergebnisse|detection test|safe simulation|control validation|technical validation|Retest', "pentest_redteam"),
    # cloud
    (r'CloudTrail|CloudWatch|cloud (audit|change|flow)|Flow-Logs|VPC|cloud log', "cloud_logs"),
    (r'CSPM|CNAPP|Security Hub|cloud posture|cloud storage scanner|runtime exposure|Cloud Security Controls', "cspm"),
    (r'Kubernetes|container runtime|admission controller|service mesh|runtime (sensor|inventory)', "container_k8s"),
    (r'container registr|artifact|package (manager|registr)|SBOM|signing|provenance|OpenSSF|registry$', "artifact_sbom"),
    (r'cloud', "cloud_platform"),
    (r'audit log|access log|action log|admin group|^logs$|Last-Use', "platform_audit_logs"),
    # appsec
    (r'CI/CD|pipeline|repo\b|Git|version control|release management|deployment (controller|data)|bug tracker|issue tracker', "cicd_repo"),
    (r'SAST|DAST|SCA\b|AppSec|IaC|threat model', None),  # threat models -> docs
    (r'SAST|DAST|SCA\b|AppSec|IaC', "appsec_tools"),
    (r'API gateway|API inventory', "api_gateway"),
    # data & privacy
    (r'DLP|DSPM', None),
    (r'DLP', "dlp"),
    (r'DSPM|data catalog|Datenkatalog|data class|data inventory|data lineage|data platform|database permission|file share|object storage|databases$|DLP (label|discovery)', "dspm_dataclass"),
    (r'CASB|SSE\b|SaaS', "casb_saas"),
    (r'RoPA|DPIA|DSAR|privacy|Datenschutz|data processing record|legal hold|DPA record|DPO', "privacy_tool"),
    (r'backup|WORM|object lock|recovery tool', "backup"),
    # grc block
    (r'policy', "policy_repo"),
    (r'risk register|Risk Register|FAIR|risk (acceptance|committee|quantification|scenario)|materiality|impact assessment', "risk_register"),
    (r'audit finding|findings|audit (plan|rights)|control test|Control Test|certification evidence|Remediation|SOC report|remediation evidence|Gap register', "audit_findings"),
    (r'evidence|sign-off|business (owner|acceptance)|attestation|decision log|exception decision', "evidence_repo"),
    (r'GRC|ISMS|exception|Ausnahmen|risk acceptance|obligation|DORA/TIBER|regulatory mapping|Meldekanal', None),
    (r'Meldekanal', "survey_feedback"),
    (r'GRC|ISMS|exception|Ausnahmen|obligation|DORA/TIBER|regulatory mapping|compliance', "grc_isms"),
    (r'KPI|metric store|Metric store|BI semantic|dashboard|data confidence|baseline|Historical|schema validation|report$', "metric_store"),
    # ops
    (r'ITSM|ticket|Ticketing|Jira|incident|Incident|RCA|problem management|change (control|log|record|management)|post-incident|forensic|escalation log|reopen|Lessons-Learned|rollback', "itsm_incidents"),
    (r'on-call|roster|escalation matrix|MSSP|Staff capacity|SOC roster|contact list', "workforce_ops"),
    (r'Finance|ERP|cost|Time Tracking|billing|procurement|insurance premium', "finance_cost"),
    (r'architect|Architektur|diagram|map\b|maps\b|dependency|service (map|dependency)|threat model|process documentation|segmentation map|environment inventory', None),
    (r'architect|Architektur|Netzwerkdiagramme|dependency map|application map|service (map|dependency)|threat model|process documentation|segmentation map', "docs_architecture"),
    # people
    (r'HR|Personalstamm|Offboarding', "hr_system"),
    (r'LMS|training|Intervention', "lms_training"),
    (r'phishing|Phishing|Kampagnen', "phishing_sim"),
    (r'survey|Survey|feedback|user report', "survey_feedback"),
    # third parties & resilience
    (r'TPRM|supplier|Lieferanten|vendor|fourth-party|subprocessor|ICT register|Supplier', "tprm"),
    (r'contract|Contract|legal|regulator|Insurance questionnaire', None),
    (r'insurance|broker/insurer', "cyber_insurance"),
    (r'contract|Contract|legal|Legal|regulator', "legal_contracts"),
    (r'BIA|BCM|recovery|DR |Exit plan|exit plan|exercise|tabletop|Crisis|crisis|contact test|Breach-Playbook|scenario', "bia_bcm"),
    # low-signal leftovers
    (r'CMDB|asset|Asset|inventory|service catalog|Service catalog|criticality|software|SAM\b|application portfolio', "cmdb_assets"),
]

# cmdb_assets was referenced but not declared above — declare it (Vuln group? core infra)
CLASSES.insert(21, ("cmdb_assets", "CMDB / asset inventory & service catalog", "vuln"))

OVERRIDES = {
    # prose monsters -> multi-class
    "Primary evidence: ITSM/Incident Register, Case Management, SOAR, RCA Repository, Reopen Reason Codes. Financial context: Time Tracking and cost centers only for rework costs.": ["itsm_incidents","case_mgmt","soar","finance_cost"],
    "Primary evidence: ITSM/Incident Register, SOAR, Case Management, Incident Closure Evidence, RCA Repository. Financial context only for cost impact.": ["itsm_incidents","soar","case_mgmt","finance_cost"],
    "Primary evidence: ITSM/Incident Register, SOAR/Case Management, Escalation Logs, On-call/Roster System, Reason Codes. Financial context only for capacity analysis.": ["itsm_incidents","soar","case_mgmt","workforce_ops","finance_cost"],
    "Primary evidence: SIEM, SOAR, ITSM/Incident Register, Alert Queue, On-call/Roster System. Financial context only for capacity and sourcing evaluation.": ["siem","soar","itsm_incidents","workforce_ops","finance_cost"],
    "Primary evidence: SIEM, SOAR, ITSM/Incident Register, alert review sample, analyst triage labels. Financial context: Time Tracking and SOC Tooling Cost Register only for capacity/cost impact.": ["siem","soar","itsm_incidents","finance_cost"],
    "Primary evidence: SIEM, SOAR, ITSM/Incident Register, Case Management, Escalation Logs, On-call/Roster System. Financial context only for capacity and sourcing decisions.": ["siem","soar","itsm_incidents","case_mgmt","workforce_ops","finance_cost"],
    "Primary evidence: SIEM, SOAR, ITSM/Incident Register, Detection Rule Repository, threat hunting results, purple team/test results, external reports. Financial context only for follow-up costs.": ["siem","soar","itsm_incidents","detection_repo","pentest_redteam","finance_cost"],
    "Primary evidence: Vulnerability Scanner, CMDB/Asset Inventory, ITSM Patch Tickets, re-scan evidence, EPSS, CISA KEV, EASM. Financial data is only optional context for capacity planning.": ["vuln_scanner","cmdb_assets","itsm_incidents","vuln_intel_feeds","easm"],
    # references to other cards
    "Source cards STD-006, STD-053, and STD-054": ["metric_store"],
    "STD-032/062/070.": ["metric_store"],
    # ambiguous singles decided by card context
    "SOC reports": ["audit_findings"],
    "attestations": ["evidence_repo"],
    "notification tool": ["bia_bcm"],
    "Retention-Regeln": ["privacy_tool"],
    "report": ["metric_store"],
    "registry": ["artifact_sbom"],
    "logs": ["platform_audit_logs"],
    "discovery": ["asset_discovery"],
    "cloud": ["cloud_platform"],
    "architecture": ["docs_architecture"],
    "baselines": ["metric_store"],
    "Historical baseline values": ["metric_store"],
    "Baseline studies on analyst handling time": ["workforce_ops"],
    "insurance policy": ["cyber_insurance"],
    "Insurance questionnaires": ["cyber_insurance"],
    "broker/insurer communications": ["cyber_insurance"],
    "threat scenarios": ["risk_register"],
    "incident scenarios": ["bia_bcm"],
    "legal/regulatory mappings": ["grc_isms"],
    "DORA Register of Information": ["tprm"],
    "firewall/DNS/EDR block lists": ["network_sec"],
    "identity graph": ["idp_iam"],
    "identity/asset inventory": ["idp_iam","cmdb_assets"],
    "identity/asset resolver": ["idp_iam","cmdb_assets"],
    "IdP (Credential-Eingaben)": ["idp_iam"],
    "IdP (Rollen/Privilegien)": ["idp_iam"],
    "Jira/ITSM": ["itsm_incidents"],
    "dashboard alerts": ["metric_store"],
    "Control test results": ["audit_findings"],
    "Control Test Results": ["audit_findings"],
    "control test records": ["audit_findings"],
    "schema validation": ["telemetry_pipeline"],
    # resolved by card context (see curation log)
    "Business Impact Analysis (loss magnitude)": ["risk_register"],      # STD-002a ALE
    "Input filters": ["ai_soc_mlops"],                                   # AIM-011
    "Platform configurations": ["secrets_kms"],                          # CRY-001 crypto-agility
    "data export logs": ["tprm"],                                        # TPR-007 supplier exit
    "questionnaires": ["tprm"],                                          # TPR-002
    "storage lifecycle policies": ["telemetry_pipeline"],                # LOG-007 log retention
}

def classify(s):
    key = s.strip()
    if key in OVERRIDES:
        return OVERRIDES[key]
    for pat, cls in RULES:
        if cls is None:
            continue
        if re.search(pat, key, re.IGNORECASE):
            return [cls]
    return []

def main():
    d = yaml.safe_load(open(CAT))
    cards = d["cards"]
    all_sources = sorted({s.strip() for c in cards for s in c["data_sources"]})
    class_ids = {c[0] for c in CLASSES}
    mapping, unmapped, bad = {}, [], []
    for s in all_sources:
        cls = classify(s)
        if not cls:
            unmapped.append(s)
        else:
            for x in cls:
                if x not in class_ids:
                    bad.append((s, x))
            mapping[s] = sorted(set(cls))
    print(f"sources={len(all_sources)} mapped={len(mapping)} unmapped={len(unmapped)} badclass={len(bad)}")
    for s in unmapped:
        print("  UNMAPPED:", s)
    for s, x in bad:
        print("  BADCLASS:", s, "->", x)
    if unmapped or bad:
        sys.exit(1)
    # class usage stats
    use = collections.Counter()
    for c in cards:
        cl = set()
        for s in c["data_sources"]:
            cl.update(mapping[s.strip()])
        for x in cl:
            use[x] += 1
    empty = [cid for cid, _, _ in CLASSES if use[cid] == 0]
    print("cards per class (top12):", use.most_common(12))
    print("empty classes:", empty or "none")
    # emit YAML
    out = {
        "taxonomy_version": "1.0.0",
        "catalog_version": d["version"],
        "generated_from": "catalog/osms-catalog.yaml",
        "groups": [{"id": g, "label": l} for g, l in GROUPS],
        "classes": [{"id": i, "label": l, "group": g} for i, l, g in CLASSES],
        "mapping": mapping,
    }
    with open("source_taxonomy.yaml", "w") as f:
        yaml.dump(out, f, allow_unicode=True, sort_keys=False, width=100)
    print("wrote source_taxonomy.yaml")

if __name__ == "__main__":
    main()
