from pathlib import Path
from typing import Any
import json
import xmltodict

from spec_parser import Spec, AttributeSpec


def parse_payload_file(path: Path) -> Any:
    suffix = path.suffix.lower()

    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    if suffix == ".xml":
        return xmltodict.parse(path.read_text(encoding="utf-8"))

    raise ValueError("Unsupported payload file type. Use .json or .xml.")


def flatten_payload(node: Any, prefix: str = "") -> dict[str, Any]:
    flattened = {}

    if isinstance(node, dict):
        for key, value in node.items():
            clean_key = str(key).lstrip("@")
            path = f"{prefix}.{clean_key}" if prefix else clean_key
            flattened[path.lower()] = value
            flattened[clean_key.lower()] = value
            flattened.update(flatten_payload(value, path))

    elif isinstance(node, list):
        flattened[prefix.lower()] = node
        for index, item in enumerate(node):
            flattened.update(flatten_payload(item, f"{prefix}[{index}]"))

    return flattened


def find_payload_value(flattened: dict[str, Any], attr: AttributeSpec) -> tuple[bool, Any]:
    candidates = []

    if attr.path:
        candidates.append(attr.path.lower())
        candidates.append(attr.path.split(".")[-1].lower())

    candidates.append(attr.name.lower())

    for candidate in candidates:
        if candidate in flattened:
            return True, flattened[candidate]

    return False, None


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def check_type(value: Any, expected_type: str) -> str | None:
    expected = str(expected_type or "").lower()

    if not expected:
        return None

    if "string" in expected or "text" in expected:
        if not isinstance(value, str):
            return "Expected text/string value."
    elif "integer" in expected or "int" in expected:
        if not isinstance(value, int):
            return "Expected integer value."
    elif "decimal" in expected or "number" in expected or "float" in expected:
        if not isinstance(value, (int, float)):
            return "Expected numeric value."
    elif "boolean" in expected or "bool" in expected:
        if not isinstance(value, bool):
            return "Expected true/false boolean value."
    elif "array" in expected:
        if not isinstance(value, list):
            return "Expected array/list value."
    elif "object" in expected:
        if not isinstance(value, dict):
            return "Expected object value."

    return None


def validate_payload_against_spec(payload: Any, spec: Spec) -> dict[str, Any]:
    flattened = flatten_payload(payload)

    missing_required = []
    type_errors = []
    array_errors = []
    recommendations = []

    for attr in spec.required_attributes():
        found, value = find_payload_value(flattened, attr)

        if not found or is_empty(value):
            missing_required.append({
                "product_type": attr.product_type,
                "attribute": attr.name,
                "path": attr.path,
                "message": f"Missing required field: {attr.name}",
            })
            continue

        type_error = check_type(value, attr.data_type)
        if type_error:
            type_errors.append({
                "product_type": attr.product_type,
                "attribute": attr.name,
                "path": attr.path,
                "value_found": repr(value)[:200],
                "message": type_error,
            })

        if attr.is_array and not isinstance(value, list):
            array_errors.append({
                "product_type": attr.product_type,
                "attribute": attr.name,
                "path": attr.path,
                "value_found": repr(value)[:200],
                "message": "Spec indicates this should be an array/list, but payload did not send an array.",
            })

    if missing_required:
        recommendations.append("Add all missing required fields before resubmitting the feed.")
    if type_errors:
        recommendations.append("Correct fields where the submitted value does not match the expected data type.")
    if array_errors:
        recommendations.append("For array errors, wrap repeatable fields in a list/array structure, even when only one value is sent.")

    if not recommendations:
        recommendations.append("No required-field or basic array/type issues were detected by this starter validator.")

    return {
        "missing_required_count": len(missing_required),
        "type_error_count": len(type_errors),
        "array_error_count": len(array_errors),
        "missing_required": missing_required[:300],
        "type_errors": type_errors[:300],
        "array_errors": array_errors[:300],
        "recommendations": recommendations,
    }
