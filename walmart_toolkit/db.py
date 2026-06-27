import sqlite3
from pathlib import Path

from flask import current_app, g


SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    message TEXT,
    files_downloaded INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS spec_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    source_url TEXT,
    cached_path TEXT,
    file_type TEXT,
    checksum TEXT NOT NULL,
    downloaded_at TEXT NOT NULL,
    UNIQUE(name, version, checksum)
);

CREATE TABLE IF NOT EXISTS attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spec_file_id INTEGER NOT NULL,
    product_type TEXT NOT NULL,
    path TEXT NOT NULL,
    name TEXT NOT NULL,
    required INTEGER DEFAULT 0,
    data_type TEXT,
    enum_values TEXT,
    description TEXT,
    example TEXT,
    raw_json TEXT,
    FOREIGN KEY(spec_file_id) REFERENCES spec_files(id)
);

CREATE INDEX IF NOT EXISTS idx_attributes_product_type ON attributes(product_type);
CREATE INDEX IF NOT EXISTS idx_attributes_name ON attributes(name);
CREATE INDEX IF NOT EXISTS idx_attributes_path ON attributes(path);
CREATE INDEX IF NOT EXISTS idx_attributes_spec_product_path ON attributes(spec_file_id, product_type, path);

CREATE TABLE IF NOT EXISTS attribute_snapshots (
    spec_file_id INTEGER NOT NULL,
    product_type TEXT NOT NULL,
    path TEXT NOT NULL,
    name TEXT,
    required INTEGER DEFAULT 0,
    data_type TEXT,
    enum_values TEXT,
    PRIMARY KEY(spec_file_id, product_type, path),
    FOREIGN KEY(spec_file_id) REFERENCES spec_files(id)
);

CREATE INDEX IF NOT EXISTS idx_attribute_snapshots_spec_product_path ON attribute_snapshots(spec_file_id, product_type, path);

CREATE TABLE IF NOT EXISTS spec_parse_stats (
    spec_file_id INTEGER PRIMARY KEY,
    attribute_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(spec_file_id) REFERENCES spec_files(id)
);

CREATE TABLE IF NOT EXISTS validations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    payload_format TEXT NOT NULL,
    product_type TEXT,
    spec_file_id INTEGER,
    status TEXT NOT NULL,
    issue_count INTEGER NOT NULL,
    summary TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_stats (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    Path(app.config["DATA_DIR"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
    with app.app_context():
        db = sqlite3.connect(app.config["DATABASE"])
        db.executescript(SCHEMA)
        db.close()
    app.teardown_appcontext(close_db)
