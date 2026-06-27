from flask import Blueprint, render_template, request

from ..services.case_service import build_case_assist

bp = Blueprint("case_helper", __name__, url_prefix="/case-helper")


@bp.route("/", methods=["GET", "POST"])
def index():
    result = None
    email = ""
    payload = ""
    if request.method == "POST":
        email = request.form.get("email", "")
        payload = request.form.get("payload", "")
        result = build_case_assist(email, payload)
    return render_template("case_helper.html", result=result, email=email, payload=payload)
