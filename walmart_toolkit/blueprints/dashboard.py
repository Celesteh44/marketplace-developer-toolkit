from flask import Blueprint, render_template

from spec_registry import SPEC_REGISTRY

from ..services.spec_repository import latest_spec, quick_stats, recent_validations
from ..services.sync_service import latest_sync_run

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    stats = quick_stats()
    sync_run = latest_sync_run()
    registry_items = [
        {"key": key, **value}
        for key, value in SPEC_REGISTRY.items()
        if value.get("recommended") or value.get("diff_report")
    ]
    return render_template(
        "dashboard.html",
        latest_spec=latest_spec(),
        stats=stats,
        validations=recent_validations(),
        sync_run=sync_run,
        registry_items=registry_items,
    )
