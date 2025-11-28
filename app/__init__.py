from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from .config import Config
from .extensions import bcrypt, db, jwt, limiter, migrate
from .security import register_security


# Контроллер только получает запрос,
# вся логика должна быть вынесена в services/reservations.py

def create_app(config_class: type[Config] | None = None) -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static")
    app.config.from_object(config_class or Config())

    _ensure_database_connection(app)
    register_extensions(app)
    Config.init_app(app)
    register_security(app)
    register_blueprints(app)
    configure_logging(app)

    CORS(
        app,
        resources={r"/*": {"origins": app.config.get("CORS_ORIGINS", [])}},
        supports_credentials=True,
        allow_headers=app.config.get("CORS_HEADERS", "Content-Type"),
        methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    )

    return app


def _ensure_database_connection(app: Flask) -> None:
    """Проверяем подключение к БД и выдаём понятную ошибку, если его нет."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not uri:
        raise RuntimeError(
            "Переменная SQLALCHEMY_DATABASE_URI не задана. "
            "Укажите корректный DATABASE_URL (например, постгрес)."
        )

    engine = None
    try:
        engine = create_engine(uri, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        root_cause = exc.orig if hasattr(exc, "orig") else exc
        message = (
            "Не удалось подключиться к базе данных по адресу %s (%s). "
            "Проверьте, что PostgreSQL запущен и параметры DATABASE_URL корректны."
        ) % (uri, root_cause)
        app.logger.error(message)
        raise RuntimeError(message) from exc
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001
                pass


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    jwt.init_app(app)
    limiter.init_app(app)


def register_blueprints(app: Flask) -> None:
    # TODO: подключить auth, rooms и admin blueprints
    from .routes import admin, auth, health, reservations, rooms

    app.register_blueprint(health.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(rooms.bp)
    app.register_blueprint(reservations.bp)
    app.register_blueprint(admin.bp)


# TODO: добавить уведомление пользователям за 10 минут до брони

def configure_logging(app: Flask) -> None:
    if not app.debug:
        app.logger.setLevel(logging.INFO)
