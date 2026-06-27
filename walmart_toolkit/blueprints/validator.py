from flask import Blueprint, render_template, request

from ..services.spec_repository import list_product_types
from ..services.validation_service import validate_payload

bp = Blueprint("validator", __name__, url_prefix="/validator")


@bp.route("/", methods=["GET", "POST"])
def index():
    result = None
    payload = ""
    product_type = ""
    payload_format = "json"
    if request.method == "POST":
        payload_format = request.form.get("payload_format", "json")
        product_type = request.form.get("product_type", "")
        payload = request.form.get("payload", "")
        upload = request.files.get("payload_file")
        if upload and upload.filename:
            payload = upload.read().decode("utf-8", errors="replace")
        result = validate_payload(payload, product_type, payload_format)
    return render_template(
        "validator.html",
        result=result,
        payload=payload,
        product_type=product_type,
        payload_format=payload_format,
        product_types=list_product_types(),
    )
