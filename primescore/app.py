"""
PrimeScore Backend - Application Factory
"""

import sys
import os
import logging

from flask import Flask, jsonify, render_template

sys.path.insert(0, os.path.dirname(__file__))

import config as cfg

from routes.authentication_routes import auth_bp
from routes.favourites_routes import favourites_bp
from routes.match_routes import matches_bp
from routes.statistics_routes import stats_bp
from routes.notification_routes import notifications_bp
from routes.lookup_routes import utils_bp
from routes.profile_routes import profile_bp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.secret_key = cfg.SECRET_KEY
    app.config["SESSION_COOKIE_HTTPONLY"]    = cfg.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"]    = cfg.SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"]      = cfg.SESSION_COOKIE_SECURE
    app.config["PERMANENT_SESSION_LIFETIME"] = cfg.PERMANENT_SESSION_LIFETIME

    for bp in (auth_bp, favourites_bp, matches_bp, stats_bp,
               notifications_bp, utils_bp, profile_bp):
        app.register_blueprint(bp, url_prefix="/api")

    @app.route("/")
    def index():
        return render_template("dashboard_page.html")

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        logger.error("Internal server error")
        return jsonify({"error": "Internal server error"}), 500

    logger.info("PrimeScore initialized")
    return app


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    if debug_mode:
        logger.warning("Running in DEBUG mode")
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=debug_mode)
