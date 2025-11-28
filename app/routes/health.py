"""Health check endpoint для мониторинга Railway."""
from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("health", __name__, url_prefix="/api")


@bp.route("/health", methods=["GET"])
def health_check():
    """
    Простой health check endpoint.
    Проверяет подключение к базе данных.
    """
    try:
        # Проверяем подключение к базе данных
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        
        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 503

