from flask import Blueprint, render_template, request

from spec_registry import SPEC_REGISTRY

from ..services.spec_repository import list_attributes, list_product_types

bp = Blueprint("product_types", __name__, url_prefix="/product-types")


@bp.get("/")
def index():
    query = request.args.get("q", "")
    selected = request.args.get("product_type", "")
    required = request.args.get("required", "")
    product_types = list_product_types(query)
    registry_items = _registry_items(query)
    return render_template(
        "product_types.html",
        query=query,
        selected=selected,
        required=required,
        product_types=product_types,
        registry_items=registry_items,
        attributes=list_attributes(selected, query, required),
    )


def _registry_items(query=""):
    needle = query.strip().lower()
    items = []
    for key, value in SPEC_REGISTRY.items():
        searchable = " ".join(
            str(part or "")
            for part in (
                key,
                value.get("name"),
                value.get("feed_type"),
                value.get("category"),
                value.get("recommended"),
                value.get("previous"),
            )
        ).lower()
        if needle and needle not in searchable:
            continue
        items.append({"key": key, **value})
    return items
