from flask import Flask, render_template, request
from pathlib import Path
import tempfile

from spec_parser import parse_spec_file, compare_specs
from payload_validator import parse_payload_file, validate_payload_against_spec

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB


def save_upload(file_storage, folder: Path) -> Path:
    if not file_storage or not file_storage.filename:
        raise ValueError("Missing uploaded file.")
    safe_name = file_storage.filename.replace("/", "_").replace("\\", "_")
    path = folder / safe_name
    file_storage.save(path)
    return path


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None

    if request.method == "POST":
        try:
            with tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)

                old_spec_path = save_upload(request.files.get("old_spec"), folder)
                new_spec_path = save_upload(request.files.get("new_spec"), folder)
                payload_file = request.files.get("payload")

                old_spec = parse_spec_file(old_spec_path)
                new_spec = parse_spec_file(new_spec_path)

                comparison = compare_specs(old_spec, new_spec)

                payload_validation = None
                if payload_file and payload_file.filename:
                    payload_path = save_upload(payload_file, folder)
                    payload = parse_payload_file(payload_path)
                    payload_validation = validate_payload_against_spec(payload, new_spec)

                result = {
                    "old_summary": old_spec.summary(),
                    "new_summary": new_spec.summary(),
                    "comparison": comparison,
                    "payload_validation": payload_validation,
                }

        except Exception as exc:
            error = str(exc)

    return render_template("index.html", result=result, error=error)


if __name__ == "__main__":
    app.run(debug=True)
