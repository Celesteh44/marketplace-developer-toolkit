from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..services.spec_repository import import_spec_file, list_specs
from ..services.sync_service import sync_configured_sources, sync_history

bp = Blueprint("sync", __name__, url_prefix="/sync")


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if request.form.get("action") == "refresh":
            run = sync_configured_sources()
            flash(run["message"], run["status"])
            return redirect(url_for("sync.index"))
        upload = request.files.get("spec_file")
        if upload and upload.filename:
            target = Path(current_app.config["CACHE_DIR"]) / upload.filename
            upload.save(target)
            import_spec_file(target, name=request.form.get("name") or None, version=request.form.get("version") or None)
            flash("Manual spec upload imported into the local cache.", "success")
            return redirect(url_for("sync.index"))
    return render_template(
        "sync.html",
        sources=current_app.config["SPEC_SOURCES"],
        history=sync_history(),
        specs=list_specs(),
    )
