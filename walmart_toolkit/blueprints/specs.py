from flask import Blueprint, redirect, render_template, request, url_for

from ..services.diff_report_service import load_diff_report
from ..services.spec_repository import compare_specs, default_compare_pair, get_spec, list_specs

bp = Blueprint("specs", __name__, url_prefix="/specs")


@bp.get("/")
def index():
    specs = list_specs()
    left = request.args.get("left", type=int)
    right = request.args.get("right", type=int)
    suggested_left, suggested_right = default_compare_pair(specs)
    if not left:
        left = suggested_left
    if not right:
        right = suggested_right
    should_compare = request.args.get("compare") == "1"
    comparison = compare_specs(left, right) if should_compare and left and right and left != right else None
    return render_template(
        "specs.html",
        specs=specs,
        left=left,
        right=right,
        left_spec=get_spec(left) if left else None,
        right_spec=get_spec(right) if right else None,
        comparison=comparison,
        diff_report=load_diff_report(request.args.get("report")),
    )


@bp.post("/compare")
def compare():
    return redirect(url_for("specs.index", left=request.form.get("left"), right=request.form.get("right"), compare=1))
