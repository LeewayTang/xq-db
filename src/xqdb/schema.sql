PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    url         TEXT,
    fetched_at  TEXT,
    license     TEXT,
    trust       TEXT NOT NULL DEFAULT 'unknown'
                CHECK (trust IN ('primary', 'secondary', 'tertiary', 'unknown')),
    notes       TEXT
);

CREATE TABLE IF NOT EXISTS work (
    id                TEXT PRIMARY KEY,
    title             TEXT NOT NULL,
    title_alt         TEXT,
    author            TEXT,
    attributed_author TEXT,
    era               TEXT,
    content_era       TEXT,
    genre             TEXT,
    relevance         TEXT NOT NULL DEFAULT 'unknown'
                      CHECK (relevance IN ('core', 'extended', 'peripheral',
                                           'irrelevant', 'unknown')),
    summary           TEXT,
    canonical         INTEGER NOT NULL DEFAULT 0,
    first_attested    TEXT
);

CREATE TABLE IF NOT EXISTS edition (
    id               TEXT PRIMARY KEY,
    work_id          TEXT NOT NULL REFERENCES work(id),
    source_id        TEXT NOT NULL REFERENCES source(id),
    title_in_source  TEXT,
    path             TEXT,
    sha256           TEXT,
    char_count       INTEGER,
    review_status    TEXT NOT NULL DEFAULT 'pending',
    quality_grade    TEXT,
    provenance_class TEXT,
    batch_id         TEXT,
    simhash          TEXT,
    fetched_at       TEXT
);

CREATE INDEX IF NOT EXISTS idx_edition_work ON edition(work_id);

CREATE TABLE IF NOT EXISTS section (
    id          TEXT PRIMARY KEY,
    edition_id  TEXT NOT NULL REFERENCES edition(id) ON DELETE CASCADE,
    parent_id   TEXT REFERENCES section(id),
    idx         INTEGER NOT NULL,
    title       TEXT,
    level       INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_section_edition ON section(edition_id);

CREATE TABLE IF NOT EXISTS passage (
    id          TEXT PRIMARY KEY,
    section_id  TEXT NOT NULL REFERENCES section(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    text        TEXT NOT NULL,
    text_norm   TEXT NOT NULL,
    char_count  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_passage_section ON passage(section_id);

CREATE TABLE IF NOT EXISTS review_finding (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    edition_id  TEXT NOT NULL REFERENCES edition(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    severity    TEXT NOT NULL DEFAULT 'info',
    evidence    TEXT,
    reviewer    TEXT NOT NULL DEFAULT 'rules',
    decided_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finding_edition ON review_finding(edition_id);

CREATE TABLE IF NOT EXISTS entity (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    name        TEXT NOT NULL,
    name_alt    TEXT,
    description TEXT,
    era         TEXT
);

CREATE TABLE IF NOT EXISTS mention (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    passage_id TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    entity_id  TEXT NOT NULL REFERENCES entity(id),
    surface    TEXT,
    role       TEXT,
    confidence REAL
);

CREATE TABLE IF NOT EXISTS relation (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    src_entity           TEXT NOT NULL REFERENCES entity(id),
    dst_entity           TEXT NOT NULL REFERENCES entity(id),
    kind                 TEXT NOT NULL,
    evidence_passage_id  TEXT REFERENCES passage(id)
);

CREATE TABLE IF NOT EXISTS event (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    passage_id TEXT REFERENCES passage(id) ON DELETE CASCADE,
    date_text  TEXT,
    year_start INTEGER,
    year_end   INTEGER,
    confidence TEXT,
    basis      TEXT,
    place_id   TEXT REFERENCES place(id),
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS event_participant (
    event_id  TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    entity_id TEXT NOT NULL REFERENCES entity(id),
    role      TEXT,
    PRIMARY KEY (event_id, entity_id)
);

CREATE TABLE IF NOT EXISTS tag (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    category TEXT
);

CREATE TABLE IF NOT EXISTS passage_tag (
    passage_id TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    tag_id     TEXT NOT NULL REFERENCES tag(id),
    confidence REAL,
    PRIMARY KEY (passage_id, tag_id)
);

CREATE TABLE IF NOT EXISTS quotation (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    passage_id     TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    quoted_work_id TEXT,
    quoted_title   TEXT,
    confidence     REAL
);

CREATE TABLE IF NOT EXISTS note (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS story_seed (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL,
    premise    TEXT,
    status     TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seed_passage (
    seed_id    INTEGER NOT NULL REFERENCES story_seed(id) ON DELETE CASCADE,
    passage_id TEXT NOT NULL REFERENCES passage(id),
    PRIMARY KEY (seed_id, passage_id)
);

CREATE TABLE IF NOT EXISTS highlight (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    passage_id TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    kind       TEXT,
    note       TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS link (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    a_type  TEXT NOT NULL,
    a_id    TEXT NOT NULL,
    b_type  TEXT NOT NULL,
    b_id    TEXT NOT NULL,
    kind    TEXT
);

CREATE TABLE IF NOT EXISTS index_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS place (
    id             TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    type           TEXT,
    description    TEXT,
    era            TEXT,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS place_name (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id           TEXT NOT NULL REFERENCES place(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    name_type          TEXT NOT NULL,
    period             TEXT,
    source_passage_id  TEXT REFERENCES passage(id),
    is_preferred       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_place_name_name ON place_name(name);
CREATE INDEX IF NOT EXISTS idx_place_name_place ON place_name(place_id);

CREATE TABLE IF NOT EXISTS place_location (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    place_id         TEXT NOT NULL REFERENCES place(id) ON DELETE CASCADE,
    lat              REAL NOT NULL,
    lon              REAL NOT NULL,
    precision_m      INTEGER,
    valid_from       INTEGER,
    valid_to         INTEGER,
    modern_province  TEXT,
    modern_city      TEXT,
    modern_county    TEXT,
    modern_detail    TEXT,
    hypothesis       TEXT,
    confidence       REAL,
    evidence         TEXT,
    is_primary       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_place_location_place ON place_location(place_id);

CREATE TABLE IF NOT EXISTS place_hierarchy (
    child_id      TEXT NOT NULL REFERENCES place(id),
    parent_id     TEXT NOT NULL REFERENCES place(id),
    relation      TEXT NOT NULL DEFAULT 'within',
    period_start  INTEGER,
    period_end    INTEGER,
    PRIMARY KEY (child_id, parent_id, relation)
);

CREATE TABLE IF NOT EXISTS passage_place (
    passage_id  TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    place_id    TEXT NOT NULL REFERENCES place(id),
    role        TEXT NOT NULL DEFAULT 'mention',
    confidence  REAL,
    PRIMARY KEY (passage_id, place_id, role)
);

CREATE TABLE IF NOT EXISTS passage_time (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    passage_id  TEXT NOT NULL REFERENCES passage(id) ON DELETE CASCADE,
    year_start  INTEGER,
    year_end    INTEGER,
    confidence  TEXT,
    basis       TEXT
);

CREATE INDEX IF NOT EXISTS idx_passage_time_range
    ON passage_time(year_start, year_end);

CREATE TABLE IF NOT EXISTS event_place (
    event_id  TEXT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    place_id  TEXT NOT NULL REFERENCES place(id),
    role      TEXT NOT NULL DEFAULT 'site',
    seq       INTEGER,
    PRIMARY KEY (event_id, place_id, role)
);

CREATE TABLE IF NOT EXISTS annotation_state (
    chunk_id    TEXT PRIMARY KEY,
    section_id  TEXT NOT NULL REFERENCES section(id) ON DELETE CASCADE,
    status      TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    model       TEXT,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_annotation_state_section
    ON annotation_state(section_id, status);

CREATE VIRTUAL TABLE IF NOT EXISTS section_fts
    USING fts5(section_id UNINDEXED, text_norm, tokenize='trigram');
