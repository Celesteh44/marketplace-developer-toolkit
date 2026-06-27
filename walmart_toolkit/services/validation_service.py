import json
from datetime import datetime, timezone
from xml.etree import ElementTree

from ..db import get_db
from .spec_repository import latest_spec


def validate_payload(payload_text, product_type="", payload_format="json"):
    issues = []
    parsed = None
    if payload_format == "xml":
        try:
            parsed = _xml_to_dict(ElementTree.fromstring(payload_text))
        except ElementTree.ParseError as exc:
            issues.append(_issue("Invalid XML", str(exc), "Fix the XML syntax before checking business rules."))
    else:
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            issues.append(_issue("Invalid JSON", str(exc), "Fix the JSON syntax before checking business rules."))

    spec = latest_spec()
    if parsed is not None and spec:
        rows = _attributes_for(product_type, spec["id"])
        for row in rows:
            value, exists = _value_at_path(parsed, row["path"])
            if row["required"] and not exists:
                issues.append(_issue(
                    "Missing required field",
                    f"{row['path']} is required by spec version {spec['version']}.",
                    "Add the field or confirm the seller is using the correct product type.",
                ))
                continue
            if exists:
                expected_type = (row["data_type"] or "").lower()
                if expected_type and not _matches_type(value, expected_type):
                    issues.append(_issue(
                        "Incorrect data type",
                        f"{row['path']} should be {row['data_type']}, but the payload sends {type(value).__name__}.",
                        "Update the payload value to match the current spec type.",
                    ))
                enums = json.loads(row["enum_values"] or "[]")
                if enums and str(value) not in [str(enum) for enum in enums]:
                    issues.append(_issue(
                        "Invalid enum",
                        f"{row['path']} has value '{value}', which is not in the allowed values.",
                        f"Use one of: {', '.join(map(str, enums[:12]))}.",
                    ))
    elif parsed is not None:
        issues.append(_issue(
            "No cached specification",
            "No Walmart spec has been imported yet.",
            "Run Developer Portal Sync or upload a spec file, then validate again.",
        ))

    status = "pass" if not issues else "needs_review"
    summary = "No issues found against the latest cached spec." if not issues else f"{len(issues)} issue(s) found."
    db = get_db()
    db.execute(
        "INSERT INTO validations (created_at, payload_format, product_type, spec_file_id, status, issue_count, summary) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_now(), payload_format, product_type, spec["id"] if spec else None, status, len(issues), summary),
    )
    db.commit()
    return {"status": status, "summary": summary, "issues": issues, "spec": spec}


def _attributes_for(product_type, spec_id):
    if product_type:
        return get_db().execute(
            "SELECT * FROM attributes WHERE spec_file_id = ? AND product_type = ?",
            (spec_id, product_type),
        ).fetchall()
    return get_db().execute(
        "SELECT * FROM attributes WHERE spec_file_id = ? AND required = 1",
        (spec_id,),
    ).fetchall()


def _value_at_path(payload, path):
    current = payload
    parts = [part for part in path.replace("/", ".").split(".") if part and part != "$"]
    for part in parts:
        if part == "[]":
            if isinstance(current, list) and current:
                current = current[0]
                continue
            return None, False
        if isinstance(current, list):
            if not current:
                return None, False
            current = current[0]
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True


def _matches_type(value, expected):
    if "array" in expected or "list" in expected:
        return isinstance(value, list)
    if "object" in expected or "complex" in expected:
        return isinstance(value, dict)
    if "integer" in expected or "int" in expected:
        return isinstance(value, int) and not isinstance(value, bool)
    if "number" in expected or "decimal" in expected or "float" in expected:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if "boolean" in expected or "bool" in expected:
        return isinstance(value, bool)
    if "string" in expected or "text" in expected:
        return isinstance(value, str)
    return True


def _xml_to_dict(element):
    children = list(element)
    if not children:
        return {element.tag: (element.text or "").strip()}
    return {element.tag: {key: value for child in children for key, value in _xml_to_dict(child).items()}}


def _issue(title, detail, guidance):
    return {"title": title, "detail": detail, "guidance": guidance}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
