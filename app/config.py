import os
from datetime import timedelta
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent
    DEFAULT_DATABASE_URI = "postgresql+psycopg://qrbooks:qrbooks@localhost:5432/qrbooks_dev"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    
    # Railway предоставляет DATABASE_URL в формате postgresql://
    # Конвертируем в postgresql+psycopg:// для использования psycopg3
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URI)
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = database_url
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-dev-secret")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_SECURE = os.getenv("JWT_COOKIE_SECURE", "False").lower() == "true"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_CSRF_CHECK_FORM = os.getenv("JWT_CSRF_CHECK_FORM", "True").lower() == "true"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    STATIC_QR_PATH = os.getenv(
        "STATIC_QR_PATH",
        str(Path(__file__).resolve().parent / "static" / "qr"),
    )
    FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    QR_BASE_URL = os.getenv("QR_BASE_URL")
    SERVER_EXTERNAL_BASE = os.getenv("SERVER_EXTERNAL_BASE", "http://localhost:5000/")
    CORS_ORIGINS = [origin.strip() for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:5174,https://qrbook-front.vercel.app"
    ).split(",") if origin.strip()]
    CORS_HEADERS = [
        header.strip()
        for header in os.getenv(
            "CORS_HEADERS",
            "Content-Type,Authorization,X-CSRF-Token,X-CSRFToken,x-csrf-token",
        ).split(",")
        if header.strip()
    ]
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULTS = [
        limit.strip()
        for limit in os.getenv("RATELIMIT_DEFAULTS", "6000 per hour;100000 per day").split(";")
        if limit.strip()
    ]
    RATELIMIT_HEADERS_ENABLED = True

    @staticmethod
    def init_app(app):
        Path(app.config["STATIC_QR_PATH"]).mkdir(parents=True, exist_ok=True)
