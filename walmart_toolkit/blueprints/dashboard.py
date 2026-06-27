from flask import Blueprint, render_template

from ..services.spec_repository import latest_spec, quick_stats, recent_validations
from ..services.sync_service import latest_sync_run

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    return render_template(
        "dashboard.html",
        latest_spec=latest_spec(),
        stats=quick_stats(),
        validations=recent_validations(),
        sync_run=latest_sync_run(),
    )
