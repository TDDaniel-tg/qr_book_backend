from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Iterable

from flask import Flask, jsonify, request
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
    verify_jwt_in_request,
)
from flask_limiter.util import get_remote_address

from .extensions import jwt
from .models import AuditAction, User, UserRole
from .services import audit, users


def register_security(app: Flask) -> JWTManager:
    _setup_jwt_callbacks()

    @app.after_request
    def add_security_headers(response):  # type: ignore[override]
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-XSS-Protection", "1; mode=block")
        return response

    return jwt


def _setup_jwt_callbacks() -> None:
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header: dict[str, Any], jwt_data: dict[str, Any]) -> User | None:
        identity = jwt_data["sub"]
        try:
            user_id = int(identity)
        except (TypeError, ValueError):
            return None
        return users.get_user_by_id(user_id)

    @jwt.additional_claims_loader
    def add_claims(identity: str) -> dict[str, Any]:
        try:
            user_id = int(identity)
        except (TypeError, ValueError):
            return {}
        user = users.get_user_by_id(user_id)
        if not user:
            return {}
        return {"role": user.role.value}

    @jwt.expired_token_loader
    def expired_token_loader(jwt_header: dict[str, Any], jwt_payload: dict[str, Any]):
        return jsonify({"msg": "token has expired"}), 401

    @jwt.unauthorized_loader
    def unauthorized_loader_callback(message: str):
        return jsonify({"msg": message or "missing authorization"}), 401

    @jwt.invalid_token_loader
    def invalid_token_loader_callback(message: str):
        return jsonify({"msg": message or "token invalid"}), 422


def issue_tokens(response, user: User):
    identity = str(user.id)
    access_token = create_access_token(identity=identity)
    refresh_token = create_refresh_token(identity=identity)
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    audit.record_action(user_id=user.id, action=AuditAction.login, description="User login")
    return response


def clear_tokens(response):
    unset_jwt_cookies(response)
    return response


def login_rate_limit_key() -> str:
    payload = request.get_json(silent=True) or {}
    identifier = str(payload.get("name") or "").lower()
    return f"login:{get_remote_address()}:{identifier}"


def authenticated_rate_limit_key() -> str:
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return f"ip:{get_remote_address()}"
    identity = get_jwt_identity()
    if identity is not None:
        return f"user:{identity}"
    return f"ip:{get_remote_address()}"


def role_required(roles: Iterable[UserRole] | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any):
            verify_jwt_in_request()
            claims = get_jwt()
            role = claims.get("role")
            if roles and role not in {r.value for r in roles}:
                return jsonify({"msg": "insufficient permissions"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_user() -> User | None:
    verify_jwt_in_request(optional=True)
    identity = get_jwt_identity()
    if identity is None:
        return None
    try:
        user_id = int(identity)
    except (TypeError, ValueError):
        return None
    return users.get_user_by_id(user_id)
