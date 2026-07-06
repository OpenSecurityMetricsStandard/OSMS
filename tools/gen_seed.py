#!/usr/bin/env python3
"""gen_seed.py - generate seed_reference_data.sql from osms-catalog.yaml.

Proves the OSMS principle "the catalog is data": dim_card, dim_domain,
dim_calc_type, dim_framework, bridge_card_framework and kpi_threshold are
loaded 1:1 from the machine-readable catalog. Re-run on every catalog release.

Usage:  python3 gen_seed.py <path/to/osms-catalog.yaml> <output.sql>
"""
import sys, yaml, datetime

MECHANIC = {
    'Ratio': 'ratio', 'Unit Cost': 'ratio',
    'Duration': 'duration',
    'Count': 'count',
    'Delta': 'delta', 'Penalty': 'delta',
    'Composite': 'component_tree', 'Weighted Sum': 'component_tree',
    'Weighted Average': 'component_tree', 'Index': 'component_tree',
    'Score': 'component_tree', 'Monetary Risk': 'component_tree',
    'Ranking': 'ranking',
}
FW_PREFIXES = sorted([
    'NIST CSF 2.0', 'NIST SP 800-61', 'NIST SP 800-53', 'NIST SP', 'NIST AI RMF', 'NIST',
    'ISO/IEC 27001', 'ISO/IEC 27004', 'ISO/IEC', 'ISO', 'CIS Controls v8.1', 'CIS Controls', 'CIS',
    'MITRE ATT&CK', 'MITRE', 'NIS2', 'DORA', 'CRA', 'CISA ZTMM', 'CISA', 'ENISA',
    'OWASP', 'FIRST', 'SLSA', 'OpenSSF', 'GDPR', 'EU AI Act', 'EU', 'Gartner', 'BSI',
], key=len, reverse=True)

def q(s):
    return "'" + str(s).replace("'", "''") + "'"

def split_fw(m):
    for p in FW_PREFIXES:
        if m.startswith(p):
            return p, (m[len(p):].strip() or '-')
    parts = m.split(None, 1)
    return parts[0], (parts[1] if len(parts) > 1 else '-')

def main(cat_path, out_path):
    doc = yaml.safe_load(open(cat_path, encoding='utf-8'))
    cards = doc['cards']
    today = datetime.date.today().isoformat()
    L = [f"-- seed_reference_data.sql  (generated {today} from catalog "
         f"v{doc.get('version')} - {len(cards)} cards; do not edit by hand)",
         "BEGIN;"]

    calc_types = sorted({c['calculation_type'] for c in cards})
    ct_key = {}
    for i, ct in enumerate(calc_types, 1):
        ct_key[ct] = i
        L.append(f"INSERT INTO dim_calc_type VALUES ({i}, {q(ct)}, "
                 f"{q(MECHANIC.get(ct, 'component_tree'))});")

    domains = sorted({c['domain'] for c in cards})
    dom_key = {}
    for i, d in enumerate(domains, 1):
        dom_key[d] = i
        L.append(f"INSERT INTO dim_domain VALUES ({i}, {q(d)});")

    fw_key, bridges = {}, []
    for c in cards:
        for m in c['framework_mapping']:
            fw, ref = split_fw(m.strip())
            if fw not in fw_key:
                fw_key[fw] = len(fw_key) + 1
            bridges.append((c['id'], fw_key[fw], ref))
    for fw, k in sorted(fw_key.items(), key=lambda x: x[1]):
        L.append(f"INSERT INTO dim_framework VALUES ({k}, {q(fw)});")

    card_key = {}
    for i, c in enumerate(cards, 1):
        card_key[c['id']] = i
        L.append("INSERT INTO dim_card VALUES (" + ", ".join([
            str(i), q(c['id']), q(c['name']), str(dom_key[c['domain']]),
            q(c['type']), str(ct_key[c['calculation_type']]), q(c['unit']),
            q(c.get('direction', '')), q(c.get('threshold_mode', '')),
            q(str(c.get('frequency', ''))[:120]), q(c.get('priority', '')),
            q(c.get('mvp', '')), q(c.get('release_status', '')),
            q(c['card_version']), q(c['osms_version']),
            q(today), 'NULL', 'TRUE']) + ");")

    seen = set()
    for cid, fwk, ref in bridges:
        t = (card_key[cid], fwk, ref)
        if t in seen:
            continue
        seen.add(t)
        L.append(f"INSERT INTO bridge_card_framework VALUES "
                 f"({t[0]}, {t[1]}, {q(ref)});")

    for i, c in enumerate(cards, 1):
        L.append(f"INSERT INTO kpi_threshold VALUES ({i}, {card_key[c['id']]}, "
                 f"'default', {q(c['target_thresholds'])}, NULL, NULL, NULL, "
                 f"{q(today)}, NULL);")

    L.append("COMMIT;")
    open(out_path, 'w', encoding='utf-8').write("\n".join(L) + "\n")
    print(f"{out_path}: {len(cards)} cards, {len(domains)} domains, "
          f"{len(calc_types)} calc types, {len(fw_key)} frameworks, "
          f"{len(seen)} framework bridges")

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
