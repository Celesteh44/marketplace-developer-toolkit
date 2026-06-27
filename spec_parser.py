from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import openpyxl


HEADER_ALIASES = {
    "product_type": [
        "product type", "producttype", "category", "item type", "itemtype"
    ],
    "name": [
        "attribute name", "attribute", "field", "field name", "name", "property", "property name"
    ],
    "path": [
        "path", "json path", "xml path", "feed path", "attribute path", "xpath"
    ],
    "required": [
        "required", "is required", "requirement", "mandatory", "required?"
    ],
    "data_type": [
        "data type", "datatype", "type", "field type", "attribute type"
    ],
    "array": [
        "array", "is array", "multiple", "repeatable", "max occurrences"
    ],
    "description": [
        "description", "definition", "attribute definition", "notes"
    ],
    "example": [
        "example", "sample", "sample value"
    ],
    "min": [
        "min", "minimum", "min length", "minimum length", "min value"
    ],
    "max": [
        "max", "maximum", "max length", "maximum length", "max value"
    ],
    "allowed_values": [
        "allowed values", "enum", "enumerations", "valid values", "accepted values"
    ],
}


@dataclass
class AttributeSpec:
    product_type: str
    name: str
    path: str = ""
    required: bool = False
    data_type: str = ""
    is_array: bool = False
    description: str = ""
    example: str = ""
    min_value: str = ""
    max_value: str = ""
    allowed_values: str = ""

    def signature(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "data_type": self.data_type,
            "is_array": self.is_array,
            "path": self.path,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "allowed_values": self.allowed_values,
        }


@dataclass
class Spec:
    source_file: str
    attributes: list[AttributeSpec] = field(default_factory=list)

    def product_types(self) -> list[str]:
        return sorted({a.product_type for a in self.attributes if a.product_type})

    def by_key(self) -> dict[tuple[str, str], AttributeSpec]:
        return {(a.product_type, a.name): a for a in self.attributes}

    def required_attributes(self) -> list[AttributeSpec]:
        return [a for a in self.attributes if a.required]

    def summary(self) -> dict[str, Any]:
        return {
            "source_file": self.source_file,
            "product_type_count": len(self.product_types()),
            "product_types": self.product_types(),
            "attribute_count": len(self.attributes),
            "required_attribute_count": len(self.required_attributes()),
        }


def normalize_header(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ")


def find_column(headers: list[str], canonical_name: str) -> int | None:
    aliases = HEADER_ALIASES[canonical_name]
    normalized = [normalize_header(h) for h in headers]
    for alias in aliases:
        if alias in normalized:
            return normalized.index(alias)
    return None


def cell(row: tuple, index: int | None) -> str:
    if index is None:
        return ""
    value = row[index] if index < len(row) else ""
    return str(value or "").strip()


def to_bool(value: str) -> bool:
    return str(value or "").strip().lower() in {"true", "yes", "y", "required", "mandatory", "1"}


def looks_like_array(value: str) -> bool:
    value = str(value or "").strip().lower()
    return value in {"true", "yes", "y", "array", "repeatable", "multiple"} or "unbounded" in value


def parse_xlsx_spec(path: Path) -> Spec:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    attributes: list[AttributeSpec] = []

    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            continue

        header_row_index = None
        header_columns = None

        # Search first 20 rows for a likely header row.
        for i, row in enumerate(rows[:20]):
            headers = [str(x or "").strip() for x in row]
            if find_column(headers, "name") is not None:
                header_row_index = i
                header_columns = headers
                break

        if header_row_index is None or header_columns is None:
            continue

        col_product_type = find_column(header_columns, "product_type")
        col_name = find_column(header_columns, "name")
        col_path = find_column(header_columns, "path")
        col_required = find_column(header_columns, "required")
        col_data_type = find_column(header_columns, "data_type")
        col_array = find_column(header_columns, "array")
        col_description = find_column(header_columns, "description")
        col_example = find_column(header_columns, "example")
        col_min = find_column(header_columns, "min")
        col_max = find_column(header_columns, "max")
        col_allowed = find_column(header_columns, "allowed_values")

        for row in rows[header_row_index + 1:]:
            name = cell(row, col_name)
            if not name:
                continue

            product_type = cell(row, col_product_type) or sheet.title
            attr = AttributeSpec(
                product_type=product_type,
                name=name,
                path=cell(row, col_path),
                required=to_bool(cell(row, col_required)),
                data_type=cell(row, col_data_type),
                is_array=looks_like_array(cell(row, col_array)),
                description=cell(row, col_description),
                example=cell(row, col_example),
                min_value=cell(row, col_min),
                max_value=cell(row, col_max),
                allowed_values=cell(row, col_allowed),
            )
            attributes.append(attr)

    if not attributes:
        raise ValueError("No attributes found in the spreadsheet. Check the column headers or update HEADER_ALIASES.")

    return Spec(source_file=path.name, attributes=attributes)


def flatten_json_spec(data: Any) -> list[AttributeSpec]:
    attributes: list[AttributeSpec] = []

    def walk_product(product_type: str, node: Any, prefix: str = ""):
        if isinstance(node, dict):
            for key, value in node.items():
                current_path = f"{prefix}.{key}" if prefix else key

                if isinstance(value, dict):
                    attr_name = value.get("name") or value.get("attributeName") or key
                    required = value.get("required") or value.get("isRequired") or False
                    data_type = value.get("type") or value.get("dataType") or ""
                    is_array = data_type == "array" or isinstance(value.get("items"), dict)

                    if any(k in value for k in ["required", "isRequired", "type", "dataType", "description", "enum"]):
                        attributes.append(AttributeSpec(
                            product_type=product_type,
                            name=str(attr_name),
                            path=current_path,
                            required=bool(required),
                            data_type=str(data_type),
                            is_array=is_array,
                            description=str(value.get("description", "")),
                            allowed_values=", ".join(map(str, value.get("enum", []))) if isinstance(value.get("enum"), list) else "",
                        ))

                    walk_product(product_type, value, current_path)
                elif isinstance(value, list):
                    attributes.append(AttributeSpec(
                        product_type=product_type,
                        name=key,
                        path=current_path,
                        data_type="array",
                        is_array=True,
                    ))

    if isinstance(data, dict):
        # Try common structures first.
        for product_type, node in data.items():
            if isinstance(node, (dict, list)):
                walk_product(str(product_type), node)

    return attributes


def parse_json_spec(path: Path) -> Spec:
    data = json.loads(path.read_text(encoding="utf-8"))
    attributes = flatten_json_spec(data)
    if not attributes:
        raise ValueError("No attributes found in JSON spec.")
    return Spec(source_file=path.name, attributes=attributes)


def parse_spec_file(path: Path) -> Spec:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return parse_xlsx_spec(path)
    if suffix == ".json":
        return parse_json_spec(path)
    raise ValueError(f"Unsupported spec file type: {suffix}. Use .xlsx or .json.")


def compare_specs(old_spec: Spec, new_spec: Spec) -> dict[str, Any]:
    old_keys = old_spec.by_key()
    new_keys = new_spec.by_key()

    added_keys = sorted(set(new_keys) - set(old_keys))
    deleted_keys = sorted(set(old_keys) - set(new_keys))
    shared_keys = sorted(set(old_keys) & set(new_keys))

    changed = []
    for key in shared_keys:
        old_attr = old_keys[key]
        new_attr = new_keys[key]
        old_sig = old_attr.signature()
        new_sig = new_attr.signature()

        diffs = {}
        for field_name in old_sig:
            if old_sig[field_name] != new_sig[field_name]:
                diffs[field_name] = {
                    "old": old_sig[field_name],
                    "new": new_sig[field_name],
                }

        if diffs:
            changed.append({
                "product_type": key[0],
                "attribute": key[1],
                "changes": diffs,
            })

    return {
        "product_types_added": sorted(set(new_spec.product_types()) - set(old_spec.product_types())),
        "product_types_deleted": sorted(set(old_spec.product_types()) - set(new_spec.product_types())),
        "attributes_added": [
            {"product_type": pt, "attribute": attr, "details": new_keys[(pt, attr)].signature()}
            for pt, attr in added_keys
        ],
        "attributes_deleted": [
            {"product_type": pt, "attribute": attr, "details": old_keys[(pt, attr)].signature()}
            for pt, attr in deleted_keys
        ],
        "attributes_changed": changed,
        "counts": {
            "added": len(added_keys),
            "deleted": len(deleted_keys),
            "changed": len(changed),
        },
    }
