#!/usr/bin/env python3
"""OSMS(TM) Reference Drill Engine
================================

Traverses reference drill mechanics and checks selected arithmetic and reference
identity invariants. It is not a complete evaluator of all per-card contracts;
see recipes/CONTRACTS.md for adapter and assurance limitations.

Aligned to catalog v0.9.2 (327 cards, 13 calculation types) and to
reference/star_schema.sql. The catalog is data, the engine is fixed:
13 strategies - one per calculation type - grouped into 6 drill mechanics.

    ratio          : Ratio, Unit Cost
    duration       : Duration
    count          : Count
    delta          : Delta, Penalty
    component_tree : Composite, Weighted Sum, Weighted Average,
                     Index, Score, Monetary Risk
    ranking        : Ranking

At startup the engine cross-checks this mapping against dim_calc_type in
the database (seeded by tools/gen_seed.py) so engine, seed and catalog can
never drift apart silently.

Usage
-----
  python3 drill_engine.py --coverage            # 327/327 strategy+lineage check
  python3 drill_engine.py --demo                # end-to-end demo, all 13 types
  (defaults: catalog/osms-catalog.yaml, reference/star_schema.sql,
             reference/seed_reference_data.sql - run from the repo root)

This is a reference implementation: percentiles are computed client-side
and SQL targets SQLite for portability of the demo. Platform
implementations should push aggregation into the warehouse (PostgreSQL,
Snowflake, BigQuery) using the same schema and the same invariants.
"""
from __future__ import annotations
import argparse, re, sqlite3, statistics, sys, math, json
from pathlib import Path
import yaml

# ---------------------------------------------------------------------------
# calculation type -> drill mechanic (MUST equal the dim_calc_type seed)
# ---------------------------------------------------------------------------
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

CARD_REF = re.compile(r'\b([A-Z]{2,4}-\d{3}[a-z]?)\b')
LINEAGE_AXES = re.compile(r'Drill axes:\s*(.*?)\s*·\s*(?:Path|Primary path|The primary path(?:\s*\([^)]*\))?):', re.S | re.I)

# lineage axis -> (SELECT expression, JOIN clause) on fact_evidence_item e
AXIS_SQL = {
    'period':         ("e.period_end", ""),
    'business unit':  ("o.name",
                       "LEFT JOIN dim_org_unit o ON o.org_key = e.org_key"),
    'owner':          ("ow.owner_id",
                       "LEFT JOIN dim_owner ow ON ow.owner_key = e.owner_key"),
    'criticality':    ("json_extract(e.attributes, '$.criticality')", ""),
    'service/asset':  ("COALESCE(s.name, a.name)",
                       "LEFT JOIN dim_service s ON s.service_key = e.service_key "
                       "LEFT JOIN dim_asset a ON a.asset_key = e.asset_key"),
    'control family': ("c.family",
                       "LEFT JOIN dim_control c ON c.control_key = e.control_key"),
    'source':         ("src.name",
                       "LEFT JOIN dim_source src ON src.source_key = e.source_key"),
}
# Additional declared axes have an explicit canonical field in evidence JSON.
# The adapter populates it from the card's source data; NULL stays visible as a
# missing-dimension group. Fields are a fixed whitelist, never caller SQL.
AXIS_ATTRIBUTES = {
    'target group':'target_group', 'exposure':'exposure',
    'detection source':'detection_source', 'cloud provider':'cloud_provider',
    'data classification':'data_classification', 'approval status':'approval_status',
    'supplier':'supplier_id', 'identity/account':'identity_account_id',
    'data class':'data_class', 'channel':'channel', 'cause':'cause',
    'duration':'duration', 'missed control point':'missed_control_point',
    'risk class':'risk_class', 'reported KPI':'reported_kpi_id',
    'subscore component':'subscore_component', 'regime':'regime',
    'reporting stage':'reporting_stage', 'measure_impact':'measure_impact',
    'partial metric':'partial_metric', 'sharing community':'sharing_community',
    'stakeholder group':'stakeholder_group', 'incident class':'incident_class',
    'feedback source (the incident/exercise/stakeholder)':'feedback_source',
    'rule/use case':'rule_use_case_id', 'vendor':'vendor', 'cost type':'cost_type',
    'ATT&CK technique':'attack_technique', 'root cause':'root_cause',
    'KEV/EPSS':'kev_epss', 'activity category':'activity_category',
    'shift':'shift', 'escalation level':'escalation_level', 'recipient':'recipient',
    'reason code':'reason_code', 'SLA':'sla',
    'reporting-obligation class':'reporting_obligation_class',
    'recipient (the authority/stakeholder)':'recipient',
    'risk class/weight':'risk_class_weight',
}
AXIS_SQL.update({axis:("json_extract(e.attributes, '$."+field+"')", '')
                 for axis,field in AXIS_ATTRIBUTES.items()})
AXIS_SQL.update({
    'business service':('s.name','LEFT JOIN dim_service s ON s.service_key=e.service_key'),
    'asset class':('a.asset_class','LEFT JOIN dim_asset a ON a.asset_key=e.asset_key'),
    'asset criticality':('a.criticality','LEFT JOIN dim_asset a ON a.asset_key=e.asset_key'),
    'severity':('sev.code','LEFT JOIN dim_severity sev ON sev.severity_key=e.severity_key'),
})
TOL = 1e-8  # raw-value absolute arithmetic tolerance; counts are exact


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------
class Card:
    def __init__(self, raw):
        self.raw = raw
        self.id = raw['id']
        self.name = raw['name']
        self.calc_type = raw['calculation_type']
        self.unit = raw['unit']
        lineage = raw.get('drilldown_lineage', '') or ''
        m = LINEAGE_AXES.search(lineage)
        self.axes = [a.strip() for a in re.split(r'[,·]', m.group(1)) if a.strip()] if m else []
        # composite-style lineages list their parts instead of axes
        self.child_ids = [c for c in CARD_REF.findall(lineage) if c != self.id]
        self.has_parts = ('Subscore' in lineage or 'Sub-scores' in lineage
                          or 'Components' in lineage or bool(self.child_ids))

class Catalog:
    def __init__(self, path):
        doc = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        self.version = doc.get('version')
        self.cards = {c['id']: Card(c) for c in doc['cards']}

    def __getitem__(self, card_id) -> Card:
        return self.cards[card_id]


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
class Strategy:
    """One strategy per calculation type. Subclasses implement:
    recompute(value_row) -> float|None   (from components/evidence)
    breakdown(value_row, axis) -> [(label, value)]
    items(value_row, limit) -> [rows]
    """
    mechanic = None

    def __init__(self, eng, card: Card):
        self.eng, self.card, self.con = eng, card, eng.con

    # -- shared plumbing ----------------------------------------------------
    def value_row(self, scope, period_end):
        r = self.con.execute(
            """SELECT v.value_id, v.value_numeric, v.is_na, v.numerator,
                      v.denominator, v.scope_id, v.period_end, v.card_key, v.period_start
               FROM fact_kpi_value v JOIN dim_card d ON d.card_key = v.card_key
               WHERE d.card_id = ? AND d.card_version = ?
                 AND v.scope_id = ? AND v.period_end = ?""",
            (self.card.id, self.card.raw['card_version'], scope, period_end)).fetchone()
        if not r:
            raise LookupError(f"no fact_kpi_value for {self.card.id}/{scope}/{period_end}")
        return dict(zip(('value_id', 'value', 'is_na', 'num', 'den',
                         'scope', 'period_end', 'card_key', 'period_start'), r))

    def evidence_agg(self, value_id, select, joins="", group=""):
        sql = (f"SELECT {select} FROM fact_evidence_item e {joins} "
               f"WHERE e.value_id = ? {group}")
        return self.con.execute(sql, (value_id,)).fetchall()

    def reconcile(self, scope, period_end):
        v = self.value_row(scope, period_end)
        errors = []
        try:
            recomputed = self.recompute(v)
        except (ValueError, TypeError, NotImplementedError) as exc:
            recomputed = None
            errors.append(str(exc))
        arithmetic_ok = ((recomputed is None and v['is_na']) or
                         (recomputed is not None and not v['is_na'] and math.isfinite(recomputed)
                          and abs(v['value'] - recomputed) <= (0 if self.card.calc_type == 'Count' else TOL)))
        if self.mechanic != 'component_tree':
            bad = self.con.execute("""SELECT COUNT(*) FROM fact_evidence_item e
                WHERE e.value_id = ? AND (e.card_key <> ? OR e.scope_id <> ?
                OR e.period_start IS NULL OR e.period_start <> ? OR e.period_end <> ?
                OR e.evidence_ref IS NULL OR TRIM(e.evidence_ref) = '' OR e.source_key IS NULL)""",
                (v['value_id'], v['card_key'], v['scope'], v['period_start'], v['period_end'])).fetchone()[0]
            if bad:
                errors.append('evidence identity, scope, period or reference mismatch')
        return {'stored': None if v['is_na'] else v['value'], 'recomputed': recomputed,
                'arithmetic_ok': bool(arithmetic_ok), 'ok': bool(arithmetic_ok and not errors),
                'errors': errors, 'assurance': 'arithmetic_and_reference_identity_only',
                'card_contract_validated': False}

    def drill(self, scope, period_end, axis=None, limit=8):
        v = self.value_row(scope, period_end)
        axis = axis or (self.card.axes[1] if len(self.card.axes) > 1 else 'period')
        return {
            'card': f"{self.card.id} {self.card.name}",
            'type': self.card.calc_type, 'mechanic': self.mechanic,
            'L0_value': None if v['is_na'] else v['value'],
            'L1_breakdown': {'axis': axis, 'rows': self.breakdown(v, axis)},
            'L2_items': self.items(v, limit),
        }


class EvidenceStrategy(Strategy):
    """Base for types whose aggregate re-derives from fact_evidence_item."""
    def axis_parts(self, axis):
        if axis not in AXIS_SQL:
            raise ValueError(f'Unsupported drill axis: {axis}')
        expr, join = AXIS_SQL[axis]
        return expr, join

    def items(self, v, limit):
        rows = self.evidence_agg(
            v['value_id'],
            "e.record_id, e.evidence_ref, e.status, e.numeric_value, "
            "e.in_numerator, e.in_denominator")
        return [dict(zip(('record_id', 'evidence_ref', 'status', 'numeric',
                          'in_num', 'in_den'), r)) for r in rows[:limit]]

class RatioStrategy(EvidenceStrategy):
    mechanic = 'ratio'
    def recompute(self, v):
        (num, den), = self.evidence_agg(
            v['value_id'], "SUM(e.in_numerator), SUM(e.in_denominator)")
        if not den:                       # empty denominator => n/a, never 0
            return None
        return (100.0 if re.search(r'\*\s*100\b', self.card.raw['formula']) else 1.0) * num / den
    def breakdown(self, v, axis):
        expr, join = self.axis_parts(axis)
        return self.evidence_agg(
            v['value_id'],
            f"{expr}, ROUND({100.0 if re.search(r'\*\s*100\b', self.card.raw['formula']) else 1.0}*SUM(e.in_numerator)/"
            f"NULLIF(SUM(e.in_denominator),0), 1)",
            join, f"GROUP BY {expr}")

class UnitCostStrategy(EvidenceStrategy):
    mechanic = 'ratio'                    # cost sum / unit count
    def recompute(self, v):
        if self.card.id == 'STD-005':
            rows = self.evidence_agg(v['value_id'], "e.attributes")
            data = [json.loads(r[0]) for r in rows]
            if not data:
                return None
            if any(not {'verified_risk_reduction','security_investment_cost'} <= set(r) for r in data):
                raise ValueError('STD-005 requires verified risk reduction and cost amounts in attributes')
            den = sum(r['security_investment_cost'] for r in data)
            return sum(r['verified_risk_reduction'] for r in data) / den if den > 0 else None
        raise NotImplementedError('Unit Cost requires a card-specific quantity adapter')
    def breakdown(self, v, axis):
        self.axis_parts(axis)
        return [('whole scope (quantity adapter)', self.recompute(v))]


class CountStrategy(EvidenceStrategy):
    mechanic = 'count'
    def recompute(self, v):
        (n,), = self.evidence_agg(v['value_id'], "SUM(e.in_denominator)")
        return float(n or 0)
    def breakdown(self, v, axis):
        expr, join = self.axis_parts(axis)
        return self.evidence_agg(v['value_id'],
                                 f"{expr}, SUM(e.in_denominator)",
                                 join, f"GROUP BY {expr}")

class DurationStrategy(EvidenceStrategy):
    mechanic = 'duration'
    def _hours(self, value_id):
        rows = self.evidence_agg(
            value_id,
            "COALESCE(e.numeric_value, "
            f"(JULIANDAY(e.resolved_at)-JULIANDAY(e.detected_at))*{1440 if 'minutes' in self.card.unit else 24})")
        return sorted(r[0] for r in rows if r[0] is not None)
    def recompute(self, v):
        h = self._hours(v['value_id'])
        if any(x < 0 or not math.isfinite(x) for x in h):
            raise ValueError('invalid duration')
        return statistics.median(h) if h else None
    def breakdown(self, v, axis):
        expr, join = self.axis_parts(axis)
        rows = self.evidence_agg(
            v['value_id'],
            f"{expr}, COALESCE(e.numeric_value, "
            f"(JULIANDAY(e.resolved_at)-JULIANDAY(e.detected_at))*{1440 if 'minutes' in self.card.unit else 24})", join)
        by = {}
        for label, hours in rows:
            if hours is None:
                continue
            if hours < 0 or not math.isfinite(hours):
                raise ValueError('invalid duration')
            by.setdefault(label, []).append(hours)
        return [(k, round(statistics.median(vv), 1)) for k, vv in by.items()]

class DeltaStrategy(EvidenceStrategy):
    mechanic = 'delta'                    # each item carries its delta share
    def recompute(self, v):
        aggregate = 'AVG' if self.card.id == 'STD-074' else 'SUM'
        (s,), = self.evidence_agg(v['value_id'], f'{aggregate}(e.numeric_value)')
        return None if s is None else float(s)
    def breakdown(self, v, axis):
        expr, join = self.axis_parts(axis)
        return self.evidence_agg(v['value_id'],
                                 f"{expr}, ROUND({'AVG' if self.card.id == 'STD-074' else 'SUM'}(e.numeric_value),2)",
                                 join, f"GROUP BY {expr}")

class PenaltyStrategy(DeltaStrategy):
    def recompute(self, v):
        rows = self.evidence_agg(v['value_id'], 'e.numeric_value')
        if any(r[0] is None or not math.isfinite(r[0]) or r[0] < 0 for r in rows):
            raise ValueError('penalty contributions must be finite and nonnegative')
        cap = {'STD-001a': 25, 'STD-001b': 15}.get(self.card.id)
        if cap is None:
            raise NotImplementedError('Penalty cap requires a card-specific contract')
        return min(cap, sum(r[0] for r in rows))

    mechanic = 'delta'                    # deductions sum (optionally capped)


class ComponentStrategy(Strategy):
    """Base for the component-tree family. L1 = the weighted parts; parts
    that are cards themselves drill on recursively by their own type."""
    mechanic = 'component_tree'
    weighted_average = False

    def components(self, value_id):
        return self.con.execute(
            """SELECT COALESCE(d.card_id, c.component_label),
                      c.weight, c.component_value, c.contribution, d.card_id
               FROM fact_kpi_component c
               LEFT JOIN dim_card d ON d.card_key = c.child_card_key
               WHERE c.parent_value_id = ?""", (value_id,)).fetchall()

    def recompute(self, v):
        comps = self.components(v['value_id'])
        if not comps:
            return None
        for label, weight, value, contribution, child in comps:
            if any(x is None or not math.isfinite(x) for x in (weight, value, contribution)) or weight < 0:
                raise ValueError('invalid component input')
            if abs(weight * value - contribution) > TOL:
                raise ValueError('cached contribution does not equal weight * component value')
            if child:
                rows = self.con.execute("""SELECT f.value_numeric FROM fact_kpi_value f
                    JOIN fact_kpi_component c ON c.child_card_key = f.card_key
                    WHERE c.parent_value_id = ? AND f.scope_id = ? AND f.period_start = ? AND f.period_end = ?
                      AND c.child_card_key = (SELECT card_key FROM dim_card WHERE card_id = ? AND card_version = ?)""",
                    (v['value_id'], v['scope'], v['period_start'], v['period_end'], child, self.eng.catalog[child].raw['card_version'])).fetchall()
                if len(rows) != 1 or rows[0][0] is None or abs(rows[0][0] - value) > TOL:
                    raise ValueError('child value/version/scope/period is not bound to the component')
        s = sum(c[1] * c[2] for c in comps)
        if self.weighted_average:
            w = sum(c[1] for c in comps)
            return None if not w else s / w
        return s

    def breakdown(self, v, axis=None):
        return [(label, f"w={w} v={cv} -> {contrib}")
                for label, w, cv, contrib, _ in self.components(v['value_id'])]

    def items(self, v, limit):
        out = []
        for label, w, cv, contrib, child_id in self.components(v['value_id']):
            if child_id and child_id in self.eng.catalog.cards:
                try:                       # recurse by the CHILD's own type
                    sub = self.eng.drill(child_id, v['scope'], v['period_end'])
                    out.append({'child_card': child_id,
                                'drills_as': sub['type'],
                                'child_value': sub['L0_value'],
                                'child_breakdown': sub['L1_breakdown']['rows'][:3]})
                except LookupError:
                    out.append({'child_card': child_id, 'note': 'no fact loaded'})
        return out[:limit]

class WeightedSumStrategy(ComponentStrategy):      pass
class CompositeStrategy(ComponentStrategy):        pass
class IndexStrategy(ComponentStrategy):            pass
class ScoreStrategy(ComponentStrategy):            pass
class MonetaryRiskStrategy(ComponentStrategy):     pass
class WeightedAverageStrategy(ComponentStrategy):  weighted_average = True


class RankingStrategy(Strategy):
    mechanic = 'ranking'
    def value_row(self, scope, period_end):        # ranking has many rows
        return {'value_id': None, 'value': None, 'is_na': False,
                'scope': scope, 'period_end': period_end}
    def _ranked(self, scope, period_end):
        return self.con.execute(
            """SELECT s.name, v.value_numeric
               FROM fact_kpi_value v
               JOIN dim_card d ON d.card_key = v.card_key
               LEFT JOIN dim_service s ON s.service_key = v.service_key
               WHERE d.card_id = ? AND d.card_version = ? AND v.scope_id = ? AND v.period_end = ?
               ORDER BY v.value_numeric DESC, s.service_id ASC""",
            (self.card.id, self.card.raw['card_version'], scope, period_end)).fetchall()
    def recompute(self, v):
        return float(len(self._ranked(v['scope'], v['period_end'])))
    def reconcile(self, scope, period_end):
        rows = self._ranked(scope, period_end)
        return {'stored': len(rows), 'recomputed': None, 'ok': False,
                'arithmetic_ok': False, 'card_contract_validated': False,
                'errors': ['Ranking requires independent entity risk inputs and an explicit ranking population'],
                'assurance': 'not_implemented'}

    def breakdown(self, v, axis=None):
        return [(f"#{i} {name}", val)
                for i, (name, val) in enumerate(self._ranked(v['scope'], v['period_end']), 1)]
    def items(self, v, limit):
        return []                          # each entity drills via its own card
    def drill(self, scope, period_end, axis=None, limit=8):
        v = self.value_row(scope, period_end)
        return {'card': f"{self.card.id} {self.card.name}",
                'type': self.card.calc_type, 'mechanic': self.mechanic,
                'L0_value': f"{len(self._ranked(scope, period_end))} ranked entities",
                'L1_breakdown': {'axis': 'rank', 'rows': self.breakdown(v)},
                'L2_items': []}


STRATEGY = {
    'Ratio': RatioStrategy, 'Unit Cost': UnitCostStrategy,
    'Duration': DurationStrategy, 'Count': CountStrategy,
    'Delta': DeltaStrategy, 'Penalty': PenaltyStrategy,
    'Weighted Sum': WeightedSumStrategy, 'Weighted Average': WeightedAverageStrategy,
    'Composite': CompositeStrategy, 'Index': IndexStrategy,
    'Score': ScoreStrategy, 'Monetary Risk': MonetaryRiskStrategy,
    'Ranking': RankingStrategy,
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class DrillEngine:
    def __init__(self, con, catalog: Catalog):
        self.con, self.catalog = con, catalog
        self._active_drills = set()
        self._check_mechanics()

    def _check_mechanics(self):
        db = dict(self.con.execute(
            "SELECT name, drill_mechanic FROM dim_calc_type"))
        drift = {t: (m, db.get(t)) for t, m in MECHANIC.items() if db.get(t) != m}
        if drift:
            raise RuntimeError(f"engine/seed mechanic drift: {drift}")

    def strategy(self, card_id) -> Strategy:
        card = self.catalog[card_id]
        cls = STRATEGY.get(card.calc_type)
        if cls is None:
            raise NotImplementedError(
                f"{card_id}: no strategy for calculation type '{card.calc_type}'")
        return cls(self, card)

    def drill(self, card_id, scope, period_end, axis=None):
        key = (card_id, scope, period_end)
        if key in self._active_drills:
            raise ValueError(f'cyclic drill path at {card_id}')
        self._active_drills.add(key)
        try:
            return self.strategy(card_id).drill(scope, period_end, axis)
        finally:
            self._active_drills.remove(key)

    def reconcile(self, card_id, scope, period_end):
        return self.strategy(card_id).reconcile(scope, period_end)

    def capture_report(self, report_id, card_id, observations, parameters):
        """Execute a card-specific plan and retain the independent input evidence."""
        from execution_store import capture
        from semantic.registry import register
        plans=register([c.raw for c in self.catalog.cards.values()])
        if card_id not in plans:
            raise ValueError('Use the canonical quotient or SOC-003 snapshot profile for this card')
        return capture(self.con,report_id,plans[card_id],observations,parameters)

    def reconcile_report(self, report_id, manifest_sha256):
        """Replay a historical receipt independently of current registry activity."""
        from execution_store import replay
        return replay(self.con,report_id,manifest_sha256)

    def coverage(self):
        ok_strategy = ok_lineage = 0
        problems = []
        for cid, card in self.catalog.cards.items():
            if card.calc_type in STRATEGY:
                ok_strategy += 1
            else:
                problems.append(f"{cid}: unknown type {card.calc_type}")
            if card.axes or card.has_parts:
                ok_lineage += 1
            else:
                problems.append(f"{cid}: lineage not parseable")
        n = len(self.catalog.cards)
        return {'cards': n, 'strategy_ok': ok_strategy,
                'lineage_ok': ok_lineage, 'problems': problems}


# ---------------------------------------------------------------------------
# Demo: one representative card per calculation type, plus a tamper test
# ---------------------------------------------------------------------------
DEMO = [  # (card_id, expected value)
    ('AI-001', 85.0), ('STD-005', 0.3), ('AIM-003', 5.5), ('AI-003', 4.0),
    ('STD-074', -1.0), ('STD-001a', 25.0), ('AIM-012', 31.0), ('STD-006', 72.5),
    ('STD-001', 65.5), ('AIM-007', 70.0), ('LOG-015', 25.0),
    ('STD-002a', 2500000.0), ('STD-003', None),
]

def build_demo_db(schema_path, seed_path):
    con = sqlite3.connect(':memory:')
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(Path(schema_path).read_text().replace('JSONB', 'TEXT'))
    con.executescript(Path(seed_path).read_text())
    con.executescript("""
    INSERT INTO dim_date VALUES (20260731,'2026-07-31',2026,3,7,31,31,1);
    INSERT INTO dim_org_unit VALUES (1,'BU-01','Group IT',NULL,1);
    INSERT INTO dim_owner VALUES (1,'OWN-4711','Service Owner',1),
                                 (2,'OWN-4712','Service Owner',1);
    INSERT INTO dim_service VALUES (1,'SVC-01','Payments','tier-1',1),
        (2,'SVC-02','ERP','tier-1',1),(3,'SVC-03','CRM','tier-2',1);
    INSERT INTO dim_source VALUES (1,'SRC-01','CASB Discovery','CASB','high');
    """)
    key = {cid: k for k, cid in con.execute("SELECT card_key, card_id FROM dim_card")}
    def val(vid, cid, value, num=None, den=None, svc='NULL', scope='SCOPE-GLOBAL'):
        con.execute(f"""INSERT INTO fact_kpi_value (value_id,card_key,date_key,period_start,period_end,scope_id,org_key,service_key,asset_key,value_numeric,is_na,numerator,denominator,sample_n,data_confidence,rag,threshold_key,loaded_at) VALUES ({vid},{key[cid]},20260731,
          '2026-07-01','2026-07-31','{scope}',1,{svc},NULL,{value},0,
          {num if num is not None else 'NULL'},{den if den is not None else 'NULL'},NULL,90,'amber',NULL,CURRENT_TIMESTAMP)""")
    def ev(pk, vid, cid, rid, num, den, numeric='NULL', det='NULL', res='NULL', own=1):
        con.execute(f"""INSERT INTO fact_evidence_item VALUES ({pk},{key[cid]},{vid},
          '{rid}','ref://{rid}','SCOPE-GLOBAL','2026-07-01','2026-07-31',20260731,
          1,{own},NULL,1,1,NULL,NULL,'ok',NULL,{det},{res},NULL,{numeric},
          {num},{den},'{{}}',CURRENT_TIMESTAMP)""")
    def comp(cid_, vid, parts):                     # parts: (label|card, w, v)
        for i, (ref, w, v) in enumerate(parts, 1):
            child = key.get(ref)
            lbl = 'NULL' if child else f"'{ref}'"
            con.execute(f"""INSERT INTO fact_kpi_component VALUES
              ({vid*10+i},{vid},{child or 'NULL'},{lbl},{w},'v1',{v},{round(w*v,4)})""")
    pk = iter(range(1000, 9999))
    # Ratio AI-001: 17/20 approved -> 85 %
    val(1, 'AI-001', 85.0, 17, 20)
    for i in range(1, 21):
        ev(next(pk), 1, 'AI-001', f'AI-{i:03d}', 1 if i <= 17 else 0, 1,
           own=1 if i % 2 else 2)
    # STD-005: 24 verified reduction points / 80 person-days = 0.3.
    val(2, 'STD-005', 0.3, 24, 80)
    ev(next(pk), 2, 'STD-005', 'INV-1', 1, 1)
    con.execute("UPDATE fact_evidence_item SET attributes = ? WHERE value_id = 2",
                (json.dumps({'verified_risk_reduction':24,'security_investment_cost':80,'cost_unit':'person-days'}),))
    # Duration AIM-003: minutes -> P50 = 5.5
    val(3, 'AIM-003', 5.5)
    for i, h in enumerate([2, 3, 4, 5, 6, 8, 10, 24], 1):
        ev(next(pk), 3, 'AIM-003', f'CASE-{i}', 0, 1, numeric=h)
    # Count AI-003: 4 leakage events
    val(4, 'AI-003', 4.0, None, 4)
    for i in range(1, 5):
        ev(next(pk), 4, 'AI-003', f'LEAK-{i}', 0, 1)
    # Delta STD-074: mean of actual-minus-expected deltas = (2-5+0)/3 = -1
    val(5, 'STD-074', -1.0)
    for i, d in enumerate([2, -5, 0], 1):
        ev(next(pk), 5, 'STD-074', f'MEAS-{i}', 0, 1, numeric=d)
    # Penalty STD-001a: shocks 5+8+12 -> 25
    val(6, 'STD-001a', 25.0)
    for i, p in enumerate([5, 8, 12], 1):
        ev(next(pk), 6, 'STD-001a', f'SHOCK-{i}', 0, 1, numeric=p)
    # Weighted Sum AIM-012: .5*40+.3*30+.2*10 = 31
    val(7, 'AIM-012', 31.0)
    comp('AIM-012', 7, [('triage_share', .5, 40), ('enrich_share', .3, 30),
                        ('report_share', .2, 10)])
    # Weighted Average STD-006: (2*80+1*60+1*70)/4 = 72.5
    val(8, 'STD-006', 72.5)
    comp('STD-006', 8, [('ctrl_a', 2, 80), ('ctrl_b', 1, 60), ('ctrl_c', 1, 70)])
    # Composite STD-001: .6 * child STD-006(72.5) + .4 * exposure(55) = 65.5
    val(9, 'STD-001', 65.5)
    comp('STD-001', 9, [('STD-006', .6, 72.5), ('exposure_mgmt', .4, 55)])
    # Index AIM-007: .5*60 + .5*80 = 70
    val(10, 'AIM-007', 70.0)
    comp('AIM-007', 10, [('mttr_gain', .5, 60), ('automation_gain', .5, 80)])
    # Score LOG-015: debt buckets 12+8+5 = 25
    val(11, 'LOG-015', 25.0)
    comp('LOG-015', 11, [('expired', 1, 12), ('undocumented', 1, 8),
                         ('unowned', 1, 5)])
    # Monetary Risk STD-002a: scenarios 1.2M+0.8M+0.5M = 2.5M EUR
    val(12, 'STD-002a', 2500000.0)
    comp('STD-002a', 12, [('ransomware', 1, 1200000), ('bec_fraud', 1, 800000),
                          ('cloud_outage', 1, 500000)])
    # Ranking STD-003: services by risk 82 / 67 / 45
    for vid, svc, score in [(13, 1, 82), (14, 2, 67), (15, 3, 45)]:
        val(vid, 'STD-003', score, svc=svc, scope=f'SVC-{svc:02d}')
    con.commit()
    return con

def run_demo(engine):
    print(f"Catalog v{engine.catalog.version} - arithmetic mechanics demo, not card conformance\n")
    failures = 0
    for cid, expected in DEMO:
        card = engine.catalog[cid]
        d = engine.drill(cid, 'SCOPE-GLOBAL', '2026-07-31')
        r = engine.reconcile(cid, 'SCOPE-GLOBAL', '2026-07-31')
        flag = 'ARITHMETIC_OK' if r['ok'] else ('NOT_IMPLEMENTED' if r.get('assurance') == 'not_implemented' else 'MISMATCH')
        if expected is not None and (not r['ok'] or abs(r['recomputed'] - expected) > TOL):
            failures += 1
        print(f"[{card.calc_type:16s}] {cid:9s} value={d['L0_value']} "
              f"recon={flag} (stored={r['stored']}, recomputed={r['recomputed']})")
        rows = d['L1_breakdown']['rows'][:3]
        print(f"    L1 ({d['L1_breakdown']['axis']}): {rows}")
        if cid == 'STD-001':
            print(f"    L2 recursion into child card: {d['L2_items']}")
    # tamper test: reconciliation must catch a manipulated contribution
    engine.con.execute(
        "UPDATE fact_kpi_component SET contribution = contribution + 7 "
        "WHERE parent_value_id = 9 AND component_label = 'exposure_mgmt'")
    r = engine.reconcile('STD-001', 'SCOPE-GLOBAL', '2026-07-31')
    print(f"\nTamper test (contribution +7 on STD-001): "
          f"recon={'MISMATCH detected' if not r['ok'] else 'FAILED TO DETECT'}")
    from execution_store import capture,replay
    from semantic.registry import register
    from semantic.cases import examples
    plans=register([c.raw for c in engine.catalog.cards.values()]);fixtures=examples(plans)
    print('\nCard-specific calculations with retained input evidence (synthetic):')
    for cid,key,expected in [('STD-001','value',60),('STD-006','value',72.5),('SOC-002','p50',16),('STD-003','service_count',2),('VAL-001','overall_band',2)]:
        f=fixtures[cid][0];receipt=capture(engine.con,'demo:'+cid,plans[cid],f['rows'],f['params'])
        actual=replay(engine.con,receipt['report_id'],receipt['manifest_sha256'])['result']['outputs'][key]
        print(cid,key,actual,'receipt',receipt['manifest_sha256'])
        if abs(actual-expected)>1e-8:failures+=1
    return failures == 0 and not r['ok']

def main():
    ap = argparse.ArgumentParser(description="OSMS reference drill engine")
    ap.add_argument('--catalog', default='catalog/osms-catalog.yaml')
    ap.add_argument('--schema', default='reference/star_schema.sql')
    ap.add_argument('--seed', default='reference/seed_reference_data.sql')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--demo', action='store_true')
    a = ap.parse_args()
    catalog = Catalog(a.catalog)
    con = build_demo_db(a.schema, a.seed)
    engine = DrillEngine(con, catalog)
    if a.coverage:
        c = engine.coverage()
        print(f"Coverage: {c['strategy_ok']}/{c['cards']} cards have a strategy, "
              f"{c['lineage_ok']}/{c['cards']} lineages parsed (not semantic conformance)")
        for p in c['problems']:
            print("  !", p)
        sys.exit(0 if not c['problems'] else 1)
    if a.demo:
        sys.exit(0 if run_demo(engine) else 1)
    ap.print_help()

if __name__ == '__main__':
    main()
