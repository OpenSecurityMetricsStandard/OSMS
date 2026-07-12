-- ============================================================================
-- OSMS(TM) Reference Star Schema
-- ----------------------------------------------------------------------------
-- Aligned to:   osms-catalog.yaml  v0.9.1  (327 cards, 39 domains)
-- Generated:    2026-07-07
-- Dialect:      PostgreSQL 14+  (portable; see notes at bottom)
-- License:      see LICENSE-CODE in this repository
--
-- DESIGN PRINCIPLE — "the catalog is data, the schema is fixed":
-- Every OSMS card, regardless of its calculation type, decomposes into the
-- same three physical facts:
--
--   fact_kpi_value      the aggregate a report shows (one row per card x
--                       period x scope), carrying numerator & denominator
--   fact_kpi_component  the weighted parts of composite-family cards
--   fact_evidence_item  the raw records at the bottom of every drill path
--
-- The 13 calculation types of catalog v0.9.1 map onto 6 drill mechanics
-- (see dim_calc_type seed). Reconciliation is structural: a GROUP BY over
-- fact_evidence_item losslessly re-produces every aggregate, and composite
-- contributions must sum to their parent (vw_recon_* views verify both).
--
-- FIELD CONTRACT:
-- Catalog v0.9.1 declares 1,070 distinct minimum_data_fields across cards.
-- The conformed core below covers the fields shared across cards (scope_id,
-- record_id, evidence_ref, period_*, owner, asset, service, source, control,
-- severity, status, timestamps, numeric_value). Card-specific fields live in
-- Convention: the bare `timestamp` column is the technical observation/
-- extraction time of the source record; business event times use specific
-- *_at / *_timestamp fields and are the only time fields formulas compute on.
-- fact_evidence_item.attributes (JSONB); each card's minimum_data_fields list
-- in the catalog is the binding per-card contract that loaders and
-- validators enforce against that JSONB payload.
--
-- CATALOG RULES ENCODED AS CONSTRAINTS:
--   * "Empty denominator => result n/a, never 0"      -> chk_zero_denominator
--   * "Numerator is a subset of the denominator"      -> chk_numerator_subset
--   * "Confidence < 70 must not be Green"             -> chk_confidence_gate
-- ============================================================================


-- ============================================================================
-- SECTION 1 - CONFORMED DIMENSIONS
-- ============================================================================

CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,          -- yyyymmdd
    full_date       DATE        NOT NULL UNIQUE,
    year            INTEGER     NOT NULL,
    quarter         INTEGER     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month           INTEGER     NOT NULL CHECK (month BETWEEN 1 AND 12),
    iso_week        INTEGER     NOT NULL CHECK (iso_week BETWEEN 1 AND 53),
    day             INTEGER     NOT NULL CHECK (day BETWEEN 1 AND 31),
    is_month_end    BOOLEAN     NOT NULL DEFAULT FALSE   -- catalog as-of dates
);

-- 13 calculation types (catalog v0.9.1) -> 6 drill mechanics.
-- ratio          : Ratio, Unit Cost
-- duration       : Duration
-- count          : Count
-- delta          : Delta, Penalty
-- component_tree : Composite, Weighted Sum, Weighted Average, Index, Score,
--                  Monetary Risk
-- ranking        : Ranking
CREATE TABLE dim_calc_type (
    calc_type_key   INTEGER PRIMARY KEY,
    name            TEXT        NOT NULL UNIQUE,
    drill_mechanic  TEXT        NOT NULL CHECK (drill_mechanic IN
                    ('ratio','duration','count','delta','component_tree','ranking'))
);

CREATE TABLE dim_domain (
    domain_key      INTEGER PRIMARY KEY,
    name            TEXT        NOT NULL UNIQUE   -- 39 domains in v0.9.1
);

-- The card registry: one row per card version. Loaded straight from
-- osms-catalog.yaml (see tools/gen_seed.py). SCD2-light because the catalog
-- defines a version_break_rule: definition changes create a new row, trends
-- must not silently bridge a break.
CREATE TABLE dim_card (
    card_key        INTEGER PRIMARY KEY,
    card_id         TEXT        NOT NULL,          -- e.g. 'AI-001'
    name            TEXT        NOT NULL,
    domain_key      INTEGER     NOT NULL REFERENCES dim_domain(domain_key),
    card_type       TEXT        NOT NULL CHECK (card_type IN
                    ('kpi','kri','kci','outcome','confidence','maturity','helper')),
    calc_type_key   INTEGER     NOT NULL REFERENCES dim_calc_type(calc_type_key),
    unit            TEXT        NOT NULL,
    direction       TEXT,                          -- e.g. 'higher_is_better'
    threshold_mode  TEXT,
    frequency       TEXT,
    priority        TEXT,                          -- P0/P1/P2
    mvp             TEXT,                          -- MVP-1/2/3
    release_status  TEXT,
    card_version    TEXT        NOT NULL,
    osms_version    TEXT        NOT NULL,
    valid_from      DATE        NOT NULL,
    valid_to        DATE,                          -- NULL = open
    is_current      BOOLEAN     NOT NULL DEFAULT TRUE,
    UNIQUE (card_id, card_version)
);

CREATE TABLE dim_org_unit (
    org_key         INTEGER PRIMARY KEY,
    org_id          TEXT        NOT NULL UNIQUE,
    name            TEXT        NOT NULL,
    parent_org_key  INTEGER     REFERENCES dim_org_unit(org_key),
    org_level       INTEGER     NOT NULL DEFAULT 1
);

CREATE TABLE dim_service (
    service_key     INTEGER PRIMARY KEY,
    service_id      TEXT        NOT NULL UNIQUE,   -- business_service_id
    name            TEXT        NOT NULL,
    criticality_tier TEXT,                          -- tier/crown-jewel class
    org_key         INTEGER     REFERENCES dim_org_unit(org_key)
);

CREATE TABLE dim_asset (
    asset_key       INTEGER PRIMARY KEY,
    asset_id        TEXT        NOT NULL UNIQUE,   -- asset_id / external_asset_id
    name            TEXT,                           -- hostname_or_service
    asset_class     TEXT,                           -- device_class / asset_class
    environment     TEXT,                           -- environment_type
    criticality     TEXT,                           -- asset_criticality
    crown_jewel     BOOLEAN     NOT NULL DEFAULT FALSE,
    internet_facing BOOLEAN     NOT NULL DEFAULT FALSE,
    service_key     INTEGER     REFERENCES dim_service(service_key),
    cmdb_ref        TEXT
);

-- Owners are pseudonym-capable by design: the catalog consistently uses
-- *_id_or_pseudonym fields. Store the pseudonymous handle, resolve names
-- outside the warehouse if and where lawful.
CREATE TABLE dim_owner (
    owner_key       INTEGER PRIMARY KEY,
    owner_id        TEXT        NOT NULL UNIQUE,   -- owner_id / pseudonym
    role_label      TEXT,                           -- accountable/escalation role
    org_key         INTEGER     REFERENCES dim_org_unit(org_key)
);

CREATE TABLE dim_source (
    source_key      INTEGER PRIMARY KEY,
    source_id       TEXT        NOT NULL UNIQUE,
    name            TEXT        NOT NULL,           -- source_system
    source_class    TEXT,                           -- SIEM/EDR/CMDB/GRC/ITSM/...
    criticality     TEXT                            -- source_class_criticality
);

CREATE TABLE dim_control (
    control_key     INTEGER PRIMARY KEY,
    control_id      TEXT        NOT NULL UNIQUE,   -- control_id_or_requirement_id
    name            TEXT,
    family          TEXT,                           -- drill axis 'control family'
    tier            TEXT
);

CREATE TABLE dim_severity (
    severity_key    INTEGER PRIMARY KEY,
    code            TEXT        NOT NULL UNIQUE,   -- severity / criticality band
    rank            INTEGER     NOT NULL            -- 1 = most severe
);

CREATE TABLE dim_framework (
    framework_key   INTEGER PRIMARY KEY,
    name            TEXT        NOT NULL UNIQUE    -- NIST CSF 2.0, ISO/IEC, ...
);

-- Many-to-many: card <-> framework reference, loaded from framework_mapping.
CREATE TABLE bridge_card_framework (
    card_key        INTEGER     NOT NULL REFERENCES dim_card(card_key),
    framework_key   INTEGER     NOT NULL REFERENCES dim_framework(framework_key),
    reference_text  TEXT        NOT NULL,           -- e.g. 'GV.RM/ID.AM'
    PRIMARY KEY (card_key, framework_key, reference_text)
);

-- Versioned threshold configuration. raw_expression carries the catalog's
-- target_thresholds string verbatim; parsed bounds are optional convenience.
-- Segment supports catalog overrides such as 'crown_jewel' or 'high_risk'.
CREATE TABLE kpi_threshold (
    threshold_key   INTEGER PRIMARY KEY,
    card_key        INTEGER     NOT NULL REFERENCES dim_card(card_key),
    segment         TEXT        NOT NULL DEFAULT 'default',
    raw_expression  TEXT        NOT NULL,
    green_bound     NUMERIC,
    amber_bound     NUMERIC,
    red_bound       NUMERIC,
    valid_from      DATE        NOT NULL,
    valid_to        DATE,
    UNIQUE (card_key, segment, valid_from)
);


-- ============================================================================
-- SECTION 2 - FACTS
-- ============================================================================

-- One row per card x period x scope: the number a report shows.
-- scope_id is the catalog's own scope handle (present on all 327 cards) and
-- defines the grain together with card and period end (as-of date).
CREATE TABLE fact_kpi_value (
    value_id        BIGINT      PRIMARY KEY,
    card_key        INTEGER     NOT NULL REFERENCES dim_card(card_key),
    date_key        INTEGER     NOT NULL REFERENCES dim_date(date_key), -- as-of
    period_start    DATE        NOT NULL,
    period_end      DATE        NOT NULL,
    scope_id        TEXT        NOT NULL,
    org_key         INTEGER     REFERENCES dim_org_unit(org_key),
    service_key     INTEGER     REFERENCES dim_service(service_key),
    asset_key       INTEGER     REFERENCES dim_asset(asset_key),
    value_numeric   NUMERIC,
    is_na           BOOLEAN     NOT NULL DEFAULT FALSE,
    numerator       NUMERIC,
    denominator     NUMERIC,
    sample_n        INTEGER,
    data_confidence NUMERIC     CHECK (data_confidence BETWEEN 0 AND 100),
    rag             TEXT        CHECK (rag IN ('green','amber','red')),
    threshold_key   INTEGER     REFERENCES kpi_threshold(threshold_key),
    loaded_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (card_key, period_end, scope_id),
    -- value and n/a are mutually exclusive states
    CONSTRAINT chk_na_value CHECK (
        (is_na = TRUE  AND value_numeric IS NULL) OR
        (is_na = FALSE AND value_numeric IS NOT NULL)
    ),
    -- catalog rule: "Empty denominator => result n/a, never 0"
    CONSTRAINT chk_zero_denominator CHECK (
        denominator IS NULL OR denominator <> 0 OR is_na = TRUE
    ),
    -- catalog rule: "with data confidence < 70, the status must not be Green"
    CONSTRAINT chk_confidence_gate CHECK (
        NOT (rag = 'green' AND data_confidence < 70)
    )
);

-- Weighted parts of the component_tree family (Composite, Weighted Sum/Avg,
-- Index, Score, Monetary Risk). A component is either another card
-- (child_card_key, e.g. STD-052 = 0.40*STD-.. + ...) or a named sub-score.
-- Reconciliation invariant: SUM(contribution) = parent value_numeric.
CREATE TABLE fact_kpi_component (
    component_id    BIGINT      PRIMARY KEY,
    parent_value_id BIGINT      NOT NULL REFERENCES fact_kpi_value(value_id)
                                ON DELETE CASCADE,
    child_card_key  INTEGER     REFERENCES dim_card(card_key),
    component_label TEXT,                            -- subscore_id
    weight          NUMERIC     NOT NULL,
    weight_version  TEXT,                            -- catalog: weights_version
    component_value NUMERIC,
    contribution    NUMERIC,                         -- weight * component_value
    CONSTRAINT chk_component_ref CHECK (
        child_card_key IS NOT NULL OR component_label IS NOT NULL
    )
);

-- The drill terminus: one row per raw record feeding a card in a period.
-- GROUP BY over this table losslessly re-produces the aggregates above -
-- the star schema makes the catalog's reconciliation invariant structural.
CREATE TABLE fact_evidence_item (
    evidence_pk     BIGINT      PRIMARY KEY,
    card_key        INTEGER     NOT NULL REFERENCES dim_card(card_key),
    value_id        BIGINT      REFERENCES fact_kpi_value(value_id),
    record_id       TEXT        NOT NULL,            -- catalog: record_id
    evidence_ref    TEXT,                            -- catalog: evidence_ref
    scope_id        TEXT        NOT NULL,
    period_start    DATE,
    period_end      DATE        NOT NULL,
    date_key        INTEGER     REFERENCES dim_date(date_key),
    org_key         INTEGER     REFERENCES dim_org_unit(org_key),
    owner_key       INTEGER     REFERENCES dim_owner(owner_key),
    asset_key       INTEGER     REFERENCES dim_asset(asset_key),
    service_key     INTEGER     REFERENCES dim_service(service_key),
    source_key      INTEGER     REFERENCES dim_source(source_key),
    control_key     INTEGER     REFERENCES dim_control(control_key),
    severity_key    INTEGER     REFERENCES dim_severity(severity_key),
    status          TEXT,                            -- catalog: status
    event_at        TIMESTAMP,                       -- occurred/observed_at
    detected_at     TIMESTAMP,
    resolved_at     TIMESTAMP,                       -- contained/closed/remediated
    due_at          TIMESTAMP,                       -- sla_due / due_date
    numeric_value   NUMERIC,                         -- durations, costs, scores
    in_numerator    BOOLEAN     NOT NULL DEFAULT FALSE,
    in_denominator  BOOLEAN     NOT NULL DEFAULT FALSE,
    attributes      JSONB       NOT NULL DEFAULT '{}',
    loaded_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (card_key, scope_id, period_end, record_id),
    -- catalog rule: "The numerator is a subset of the denominator"
    CONSTRAINT chk_numerator_subset CHECK (
        in_numerator = FALSE OR in_denominator = TRUE
    )
);

-- Data-quality signals per card/source/day. Feeds fact_kpi_value.data_confidence
-- per the catalog's confidence_production_rule.
CREATE TABLE fact_data_quality (
    dq_id           BIGINT      PRIMARY KEY,
    card_key        INTEGER     REFERENCES dim_card(card_key),
    source_key      INTEGER     NOT NULL REFERENCES dim_source(source_key),
    date_key        INTEGER     NOT NULL REFERENCES dim_date(date_key),
    coverage_pct    NUMERIC     CHECK (coverage_pct    BETWEEN 0 AND 100),
    freshness_hours NUMERIC,
    completeness_pct NUMERIC    CHECK (completeness_pct BETWEEN 0 AND 100),
    parse_success_pct NUMERIC   CHECK (parse_success_pct BETWEEN 0 AND 100),
    confidence_score NUMERIC    CHECK (confidence_score BETWEEN 0 AND 100)
);


-- ============================================================================
-- SECTION 3 - INDEXES (drill-path accelerators)
-- ============================================================================

CREATE INDEX ix_value_card_period   ON fact_kpi_value    (card_key, period_end);
CREATE INDEX ix_value_org           ON fact_kpi_value    (org_key);
CREATE INDEX ix_comp_parent         ON fact_kpi_component(parent_value_id);
CREATE INDEX ix_ev_card_scope_per   ON fact_evidence_item(card_key, scope_id, period_end);
CREATE INDEX ix_ev_value            ON fact_evidence_item(value_id);
CREATE INDEX ix_ev_asset            ON fact_evidence_item(asset_key);
CREATE INDEX ix_ev_owner            ON fact_evidence_item(owner_key);
CREATE INDEX ix_ev_source           ON fact_evidence_item(source_key);
-- PostgreSQL only (comment out on engines without GIN):
-- CREATE INDEX ix_ev_attributes    ON fact_evidence_item USING GIN (attributes);


-- ============================================================================
-- SECTION 4 - RECONCILIATION & REPORTING VIEWS
-- ============================================================================

-- Latest value per card x scope (current reporting state).
CREATE VIEW vw_kpi_current AS
SELECT v.*
FROM fact_kpi_value v
JOIN (
    SELECT card_key, scope_id, MAX(period_end) AS max_pe
    FROM fact_kpi_value GROUP BY card_key, scope_id
) latest
  ON latest.card_key = v.card_key
 AND latest.scope_id = v.scope_id
 AND latest.max_pe   = v.period_end;

-- Ratio/Count reconciliation: stored numerator/denominator must equal the
-- evidence flags. A row with recon_status <> 'OK' is a data error by
-- definition of the standard ("a path that does not add up is a data error").
CREATE VIEW vw_recon_ratio_count AS
SELECT v.value_id, v.card_key, v.scope_id, v.period_end,
       v.numerator, v.denominator,
       SUM(CASE WHEN e.in_numerator   THEN 1 ELSE 0 END) AS evidence_numerator,
       SUM(CASE WHEN e.in_denominator THEN 1 ELSE 0 END) AS evidence_denominator,
       CASE WHEN v.numerator   = SUM(CASE WHEN e.in_numerator   THEN 1 ELSE 0 END)
             AND v.denominator = SUM(CASE WHEN e.in_denominator THEN 1 ELSE 0 END)
            THEN 'OK' ELSE 'MISMATCH' END AS recon_status
FROM fact_kpi_value v
JOIN fact_evidence_item e ON e.value_id = v.value_id
GROUP BY v.value_id, v.card_key, v.scope_id, v.period_end,
         v.numerator, v.denominator;

-- Component-tree reconciliation: contributions must sum to the parent
-- (tolerance 0.5 for rounding of 0-100 scores).
CREATE VIEW vw_recon_component AS
SELECT v.value_id, v.card_key, v.scope_id, v.period_end,
       v.value_numeric                       AS parent_value,
       SUM(c.contribution)                   AS component_sum,
       CASE WHEN ABS(v.value_numeric - SUM(c.contribution)) <= 0.5
            THEN 'OK' ELSE 'MISMATCH' END    AS recon_status
FROM fact_kpi_value v
JOIN fact_kpi_component c ON c.parent_value_id = v.value_id
GROUP BY v.value_id, v.card_key, v.scope_id, v.period_end, v.value_numeric;


-- ============================================================================
-- SECTION 5 - DRILL QUERY PATTERNS (one per mechanic, real card IDs)
-- ============================================================================
--
-- RATIO (AI-001, AI Asset Inventory & Approval Coverage):
--   Board value -> split by owner -> open items -> raw record.
--   SELECT o.owner_id,
--          100.0 * SUM(CASE WHEN e.in_numerator THEN 1 ELSE 0 END)
--                / NULLIF(SUM(CASE WHEN e.in_denominator THEN 1 ELSE 0 END),0)
--   FROM fact_evidence_item e
--   JOIN dim_card  c USING (card_key)
--   LEFT JOIN dim_owner o USING (owner_key)
--   WHERE c.card_id='AI-001' AND c.is_current AND e.period_end = DATE '2026-07-31'
--   GROUP BY o.owner_id;
--   -- NULLIF encodes "empty denominator => n/a, never 0" at query level too.
--
-- DURATION (AIM-003, Mean Time to Investigate):
--   SELECT s.name,
--          PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
--            EXTRACT(EPOCH FROM e.resolved_at - e.detected_at)/3600) AS p50_h,
--          PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY
--            EXTRACT(EPOCH FROM e.resolved_at - e.detected_at)/3600) AS p90_h
--   FROM fact_evidence_item e
--   JOIN dim_card c USING (card_key) LEFT JOIN dim_service s USING (service_key)
--   WHERE c.card_id='AIM-003' AND e.in_denominator GROUP BY s.name;
--
-- COUNT (AI-003) : SUM over in_denominator rows, split by any axis key.
--
-- DELTA (STD-074, Expected vs Actual Risk Reduction):
--   baseline aggregate minus current aggregate; store both periods in
--   fact_kpi_value, drill each side by its own evidence.
--
-- COMPONENT TREE (STD-052, Cloud Incident Blast Radius = 0.40/0.30/0.30):
--   SELECT COALESCE(cc.card_id, c.component_label) AS component,
--          c.weight, c.component_value, c.contribution
--   FROM fact_kpi_component c
--   LEFT JOIN dim_card cc ON cc.card_key = c.child_card_key
--   WHERE c.parent_value_id = :value_id;
--   -- then each child drills on by ITS own mechanic - recursively.
--
-- RANKING (STD-003, Top Business Services by Cyber Risk):
--   SELECT s.name, v.value_numeric,
--          RANK() OVER (ORDER BY v.value_numeric DESC) AS rnk
--   FROM vw_kpi_current v JOIN dim_service s USING (service_key)
--   JOIN dim_card c USING (card_key) WHERE c.card_id='STD-003';
--
-- ============================================================================
-- PORTABILITY NOTES
--   * Keys are plain INTEGER/BIGINT; attach sequences/IDENTITY per platform
--     (PostgreSQL: GENERATED ALWAYS AS IDENTITY; Snowflake: AUTOINCREMENT).
--   * JSONB -> use JSON/VARIANT/TEXT on engines without JSONB.
--   * PERCENTILE_CONT / RANK examples require window-function support.
-- ============================================================================
