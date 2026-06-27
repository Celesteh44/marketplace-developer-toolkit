from flask import Blueprint, render_template, request

from ..services.spec_repository import list_attributes, list_product_types

bp = Blueprint("product_types", __name__, url_prefix="/product-types")


@bp.get("/")
def index():
    query = request.args.get("q", "")
    selected = request.args.get("product_type", "")
    required = request.args.get("required", "")
    return render_template(
        "product_types.html",
        query=query,
        selected=selected,
        required=required,
        product_types=list_product_types(query),
        attributes=list_attributes(selected, query, required),
    )
