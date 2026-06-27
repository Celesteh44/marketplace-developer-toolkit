# Walmart Spec Checker

A small Flask web app to compare Walmart spec files and validate a seller payload against a selected spec.

## What it does

- Upload an old spec and a new spec
- Detect product types
- Compare fields between versions
- Show added, deleted, and changed attributes
- Upload seller JSON/XML payload
- Validate missing required fields
- Identify basic array/object structure issues
- Give plain-English correction notes

## Supported files

Best support:
- Walmart spec spreadsheets: `.xlsx`
- Seller payloads: `.json` and `.xml`

Also supported:
- JSON spec files if they are already structured as product type + attributes

## Run locally

```bash
python -m venv venv
source venv/bin/activate   # Mac/Linux
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Notes

Walmart spec files can vary by format. This starter app uses flexible header matching for common columns like:

- Product Type
- Attribute Name
- Required
- Data Type
- Path
- Min / Max
- Description
- Definition
- Example

If your exact Walmart spec uses different column names, update `HEADER_ALIASES` in `spec_parser.py`.
