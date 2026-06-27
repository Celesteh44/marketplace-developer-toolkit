# Walmart Marketplace Developer Toolkit

Internal Flask toolkit for Marketplace API Support teams working with Walmart Marketplace item specifications, payload validation, and seller case triage.

## Features

- Enterprise dashboard for recent syncs, spec status, quick stats, and validations
- Developer Portal sync for configured public Walmart specification ZIP, JSON, XML, and XLSX files
- Local SQLite cache for parsed specifications and compare-ready snapshots
- Spec Explorer with official diff report support and deep local comparison
- Product Type Explorer with searchable attributes, required status, data types, enums, examples, and descriptions
- Payload Validator for pasted or uploaded JSON/XML seller payloads
- Case Helper for issue summaries, troubleshooting steps, internal notes, and seller-facing responses

## Local-first cache

The app downloads public specification files into the local `instance/` folder. That folder is ignored by Git so Walmart documentation, cached ZIP files, and the SQLite database stay on the user's computer instead of being embedded in the repository.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
flask --app run:app run --host 127.0.0.1 --port 5001
```

Open:

```text
http://127.0.0.1:5001
```

## Project structure

```text
walmart_toolkit/
  blueprints/   Flask route modules
  services/     sync, parsing, comparison, validation, and case helper logic
  static/       dashboard CSS and JavaScript
  templates/    Jinja templates
run.py          Flask application entry point
```
