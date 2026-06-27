import hashlib
import json
from datetime import datetime, timezone

from flask import current_app

from ..db import get_db
from .spec_parser import parse_spec_file


def latest_spec():
    return get_db().execute(
        "SELECT * FROM spec_files ORDER BY downloaded_at DESC, id DESC LIMIT 1"
    ).fetchone()


def list_specs():
    return get_db().execute(
        "SELECT sf.*, COALESCE(stats.attribute_count, 0) AS attribute_count, "
        "CASE WHEN COALESCE(stats.attribute_count, 0) > 0 THEN 1 ELSE 0 END AS has_attributes "
        "FROM spec_files sf "
        "LEFT JOIN spec_parse_stats stats ON stats.spec_file_id = sf.id "
        "ORDER BY sf.downloaded_at DESC, sf.id DESC"
    ).fetchall()


def default_compare_pair(specs):
    parsed_specs = [spec for spec in specs if spec["has_attributes"]]
    if len(parsed_specs) < 2:
        return None, None
    families = {}
    for spec in parsed_specs:
        families.setdefault(_spec_family(spec["name"]), []).append(spec)
    for family in ("item_setup", "maintenance", "wfs", "omni", "delete"):
        if len(families.get(family, [])) >= 2:
            dated_specs = [spec for spec in families[family] if _version_sort_key(spec["version"])[0]]
            candidates = dated_specs if len(dated_specs) >= 2 else families[family]
            pair = sorted(candidates, key=lambda spec: _version_sort_key(spec["version"]), reverse=True)[:2]
            return pair[1]["id"], pair[0]["id"]
    return parsed_specs[1]["id"], parsed_specs[0]["id"]


def get_spec(spec_id):
    return get_db().execute("SELECT * FROM spec_files WHERE id = ?", (spec_id,)).fetchone()


def list_product_types(query=""):
    sql = (
        "SELECT product_type, COUNT(*) AS attribute_count, "
        "SUM(required) AS required_count, MAX(spec_file_id) AS latest_spec_id "
        "FROM attributes "
    )
    params = []
    if query:
        sql += "WHERE product_type LIKE ? OR name LIKE ? OR path LIKE ? "
        like = f"%{query}%"
        params.extend([like, like, like])
    sql += "GROUP BY product_type ORDER BY product_type LIMIT 250"
    return get_db().execute(sql, params).fetchall()


def list_attributes(product_type="", query="", required=""):
    if not product_type and not query:
        return []
    sql = "SELECT a.*, sf.version FROM attributes a JOIN spec_files sf ON sf.id = a.spec_file_id WHERE 1=1 "
    params = []
    if product_type:
        sql += "AND a.product_type = ? "
        params.append(product_type)
    if query:
        sql += "AND (a.name LIKE ? OR a.path LIKE ? OR a.description LIKE ?) "
        like = f"%{query}%"
        params.extend([like, like, like])
    if required in {"0", "1"}:
        sql += "AND a.required = ? "
        params.append(int(required))
    sql += "ORDER BY a.product_type, a.path LIMIT 500"
    return get_db().execute(sql, params).fetchall()


def import_spec_file(path, name=None, version=None, source_url=None):
    path = current_app.config["CACHE_DIR"] / path.name if not path.is_absolute() else path
    checksum = _checksum(path)
    now = _now()
    spec_name = name or path.stem
    spec_version = version or _version_from_name(path.name)
    db = get_db()
    cursor = db.execute(
        "INSERT OR IGNORE INTO spec_files "
        "(name, version, source_url, cached_path, file_type, checksum, downloaded_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (spec_name, spec_version, source_url, str(path), path.suffix.lower().lstrip("."), checksum, now),
    )
    db.commit()
    spec = db.execute(
        "SELECT * FROM spec_files WHERE name = ? AND version = ? AND checksum = ?",
        (spec_name, spec_version, checksum),
    ).fetchone()
    spec_id = spec["id"]
    existing_attributes = db.execute(
        "SELECT COUNT(*) FROM attributes WHERE spec_file_id = ?", (spec_id,)
    ).fetchone()[0]
    if not cursor.rowcount and existing_attributes:
        return spec
    if not cursor.rowcount:
        db.execute("DELETE FROM attributes WHERE spec_file_id = ?", (spec_id,))
        db.commit()
    attrs = parse_spec_file(path)
    if attrs:
        db.executemany(
            "INSERT INTO attributes "
            "(spec_file_id, product_type, path, name, required, data_type, enum_values, description, example, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    spec_id,
                    attr.get("product_type") or "General",
                    attr.get("path") or attr.get("name") or "",
                    attr.get("name") or "",
                    1 if attr.get("required") else 0,
                    attr.get("data_type") or "",
                    json.dumps(attr.get("enum_values") or []),
                    attr.get("description") or "",
                    attr.get("example") or "",
                    json.dumps(attr.get("raw") or {}),
                )
                for attr in attrs
                if attr.get("name") or attr.get("path")
            ],
        )
        db.commit()
        refresh_attribute_snapshot(spec_id)
    return spec


def compare_specs(left_id, right_id):
    added = _diff_paths(left_id, right_id, "added")
    removed = _diff_paths(left_id, right_id, "removed")
    modified = _modified_rows(left_id, right_id)
    required_changes = _field_changes(left_id, right_id, "required")
    enum_changes = _field_changes(left_id, right_id, "enum_values")
    type_changes = _field_changes(left_id, right_id, "data_type")
    renamed = []
    return {
        "added": added["rows"],
        "removed": removed["rows"],
        "renamed": renamed,
        "modified": modified["rows"],
        "required_changes": required_changes["rows"],
        "enum_changes": enum_changes["rows"],
        "type_changes": type_changes["rows"],
        "counts": {
            "added": added["count"],
            "removed": removed["count"],
            "renamed": 0,
            "modified": modified["count"],
            "required_changes": required_changes["count"],
            "enum_changes": enum_changes["count"],
            "type_changes": type_changes["count"],
        },
    }


def refresh_attribute_snapshot(spec_id):
    db = get_db()
    db.execute("DELETE FROM attribute_snapshots WHERE spec_file_id = ?", (spec_id,))
    db.execute(
        "INSERT INTO attribute_snapshots "
        "(spec_file_id, product_type, path, name, required, data_type, enum_values) "
        "SELECT spec_file_id, product_type, path, MAX(name), MAX(required), MAX(data_type), MAX(enum_values) "
        "FROM attributes WHERE spec_file_id = ? "
        "GROUP BY spec_file_id, product_type, path",
        (spec_id,),
    )
    attribute_count = db.execute(
        "SELECT COUNT(*) FROM attribute_snapshots WHERE spec_file_id = ?", (spec_id,)
    ).fetchone()[0]
    db.execute(
        "INSERT INTO spec_parse_stats (spec_file_id, attribute_count, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(spec_file_id) DO UPDATE SET "
        "attribute_count = excluded.attribute_count, updated_at = excluded.updated_at",
        (spec_id, attribute_count, _now()),
    )
    db.commit()


def recent_validations(limit=6):
    return get_db().execute(
        "SELECT * FROM validations ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()


def quick_stats():
    db = get_db()
    rows = db.execute("SELECT key, value FROM app_stats").fetchall()
    if rows:
        cached = {row["key"]: row["value"] for row in rows}
        return {
            "specs": cached.get("specs", 0),
            "product_types": cached.get("product_types", 0),
            "attributes": cached.get("attributes", 0),
            "validations": db.execute("SELECT COUNT(*) FROM validations").fetchone()[0],
        }
    return {
        "specs": db.execute("SELECT COUNT(*) FROM spec_files").fetchone()[0],
        "product_types": db.execute(
            "SELECT COUNT(*) FROM (SELECT product_type FROM attributes GROUP BY product_type)"
        ).fetchone()[0],
        "attributes": db.execute("SELECT COUNT(*) FROM attributes").fetchone()[0],
        "validations": db.execute("SELECT COUNT(*) FROM validations").fetchone()[0],
    }


def refresh_stats():
    db = get_db()
    now = _now()
    stats = {
        "specs": db.execute("SELECT COUNT(*) FROM spec_files").fetchone()[0],
        "product_types": db.execute(
            "SELECT COUNT(*) FROM (SELECT product_type FROM attributes GROUP BY product_type)"
        ).fetchone()[0],
        "attributes": db.execute("SELECT COUNT(*) FROM attributes").fetchone()[0],
    }
    db.executemany(
        "INSERT INTO app_stats (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        [(key, value, now) for key, value in stats.items()],
    )
    db.commit()
    return stats


def _attribute_map(spec_id):
    rows = get_db().execute("SELECT * FROM attributes WHERE spec_file_id = ?", (spec_id,)).fetchall()
    return {
        f"{row['product_type']}.{row['path']}": {
            "name": row["name"],
            "product_type": row["product_type"],
            "path": row["path"],
            "required": bool(row["required"]),
            "data_type": row["data_type"] or "",
            "enum_values": row["enum_values"] or "[]",
        }
        for row in rows
    }


def _diff_paths(left_id, right_id, direction, limit=250):
    db = get_db()
    if direction == "added":
        source_id, other_id = right_id, left_id
    else:
        source_id, other_id = left_id, right_id
    join_sql = (
        "FROM attribute_snapshots source "
        "LEFT JOIN attribute_snapshots other ON other.spec_file_id = ? "
        "AND other.product_type = source.product_type AND other.path = source.path "
        "WHERE source.spec_file_id = ? AND other.path IS NULL"
    )
    count = db.execute(f"SELECT COUNT(*) {join_sql}", (other_id, source_id)).fetchone()[0]
    rows = db.execute(
        "SELECT source.product_type || '.' || source.path AS path "
        f"{join_sql} ORDER BY source.product_type, source.path LIMIT ?",
        (other_id, source_id, limit),
    ).fetchall()
    return {"count": count, "rows": [row["path"] for row in rows]}


def _modified_rows(left_id, right_id, limit=250):
    db = get_db()
    where = (
        "FROM attribute_snapshots left_attr "
        "JOIN attribute_snapshots right_attr ON right_attr.spec_file_id = ? "
        "AND right_attr.product_type = left_attr.product_type AND right_attr.path = left_attr.path "
        "WHERE left_attr.spec_file_id = ? AND ("
        "COALESCE(left_attr.name, '') != COALESCE(right_attr.name, '') OR "
        "COALESCE(left_attr.data_type, '') != COALESCE(right_attr.data_type, '') OR "
        "COALESCE(left_attr.enum_values, '') != COALESCE(right_attr.enum_values, '') OR "
        "COALESCE(left_attr.required, 0) != COALESCE(right_attr.required, 0))"
    )
    count = db.execute(f"SELECT COUNT(*) {where}", (right_id, left_id)).fetchone()[0]
    rows = db.execute(
        "SELECT left_attr.product_type || '.' || left_attr.path AS path, "
        "left_attr.name AS left_name, right_attr.name AS right_name, "
        "left_attr.data_type AS left_type, right_attr.data_type AS right_type, "
        "left_attr.required AS left_required, right_attr.required AS right_required, "
        "left_attr.enum_values AS left_enum, right_attr.enum_values AS right_enum "
        f"{where} ORDER BY left_attr.product_type, left_attr.path LIMIT ?",
        (right_id, left_id, limit),
    ).fetchall()
    return {
        "count": count,
        "rows": [
            {
                "path": row["path"],
                "changes": _row_change_keys(row),
            }
            for row in rows
        ],
    }


def _field_changes(left_id, right_id, field, limit=250):
    db = get_db()
    left_field = f"left_attr.{field}"
    right_field = f"right_attr.{field}"
    where = (
        "FROM attribute_snapshots left_attr "
        "JOIN attribute_snapshots right_attr ON right_attr.spec_file_id = ? "
        "AND right_attr.product_type = left_attr.product_type AND right_attr.path = left_attr.path "
        f"WHERE left_attr.spec_file_id = ? AND COALESCE({left_field}, '') != COALESCE({right_field}, '')"
    )
    count = db.execute(f"SELECT COUNT(*) {where}", (right_id, left_id)).fetchone()[0]
    rows = db.execute(
        "SELECT left_attr.product_type || '.' || left_attr.path AS path, "
        f"{left_field} AS before, {right_field} AS after "
        f"{where} ORDER BY left_attr.product_type, left_attr.path LIMIT ?",
        (right_id, left_id, limit),
    ).fetchall()
    return {
        "count": count,
        "rows": [{"path": row["path"], "before": row["before"], "after": row["after"]} for row in rows],
    }


def _row_change_keys(row):
    changes = {}
    if row["left_name"] != row["right_name"]:
        changes["name"] = True
    if row["left_type"] != row["right_type"]:
        changes["data_type"] = True
    if row["left_required"] != row["right_required"]:
        changes["required"] = True
    if row["left_enum"] != row["right_enum"]:
        changes["enum_values"] = True
    return changes


def _spec_family(name):
    normalized = (name or "").lower()
    if "maintenance" in normalized:
        return "maintenance"
    if "omni" in normalized:
        return "omni"
    if "wfs" in normalized:
        return "wfs"
    if "delete" in normalized:
        return "delete"
    if "item" in normalized or "setup" in normalized or "match" in normalized:
        return "item_setup"
    return "other"


def _version_sort_key(version):
    value = version or ""
    date_match = __import__("re").search(r"(\d{4})-(\d{2})-(\d{2})", value)
    if date_match:
        return 1, tuple(int(part) for part in date_match.groups())
    number_match = __import__("re").search(r"(\d+(?:\.\d+)*)", value)
    if number_match:
        return 0, tuple(int(part) for part in number_match.group(1).split("."))
    return 0, (0,)


def _detect_renames(left, right, removed, added):
    renames = []
    unmatched_added = set(added)
    for old_path in removed:
        old = left[old_path]
        for new_path in list(unmatched_added):
            new = right[new_path]
            if old["data_type"] == new["data_type"] and old["enum_values"] == new["enum_values"]:
                old_parent = ".".join(old_path.split(".")[:-1])
                new_parent = ".".join(new_path.split(".")[:-1])
                if old_parent == new_parent:
                    renames.append({"before": old_path, "after": new_path})
                    unmatched_added.remove(new_path)
                    break
    return renames


def _checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version_from_name(filename):
    match = None
    for pattern in (r"v?(\d+(?:\.\d+){1,3})", r"(\d{4}[-_]\d{2}[-_]\d{2})"):
        match = __import__("re").search(pattern, filename, __import__("re").I)
        if match:
            break
    return match.group(1).replace("_", "-") if match else datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
