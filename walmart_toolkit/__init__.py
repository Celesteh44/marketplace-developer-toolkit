from flask import Flask

from .config import Config
from .db import init_db


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config["SPEC_SOURCES"] = config_class.spec_sources()

    init_db(app)

    from .blueprints.case_helper import bp as case_helper_bp
    from .blueprints.dashboard import bp as dashboard_bp
    from .blueprints.product_types import bp as product_types_bp
    from .blueprints.specs import bp as specs_bp
    from .blueprints.sync import bp as sync_bp
    from .blueprints.validator import bp as validator_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(specs_bp)
    app.register_blueprint(product_types_bp)
    app.register_blueprint(validator_bp)
    app.register_blueprint(case_helper_bp)
    app.register_blueprint(sync_bp)

    return app
