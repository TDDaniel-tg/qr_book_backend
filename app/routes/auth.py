from __future__ import annotations

from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_limiter.util import get_remote_address

from ..extensions import limiter

from ..models import AuditAction, UserRole
from ..security import (
    authenticated_rate_limit_key,
    clear_tokens,
    issue_tokens,
    login_rate_limit_key,
    role_required,
)
from ..services import audit, users

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/login")
@limiter.limit("6 per minute", key_func=login_rate_limit_key, error_message="Слишком много попыток входа. Повторите позже.")
def login():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    password = payload.get("password")
    if not name or not password:
        return jsonify({"msg": "name and password required"}), HTTPStatus.BAD_REQUEST

    user = users.get_user_by_name(name)
    if not user:
        return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED
    if not users.verify_password(user, password):
        # TODO: Добавить логирование подозрительных попыток входа
        return jsonify({"msg": "invalid credentials"}), HTTPStatus.UNAUTHORIZED

    response = jsonify({"msg": "login successful", "role": user.role.value})
    issue_tokens(response, user)
    return response, HTTPStatus.OK


@bp.post("/logout")
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def logout():
    verify_jwt_in_request(optional=True)
    identity = get_jwt_identity()
    response = jsonify({"msg": "logout successful"})
    clear_tokens(response)
    if identity:
        audit.record_action(
            user_id=identity,
            action=AuditAction.logout,
            description="User logged out",
        )
    return response, HTTPStatus.OK


@bp.post("/register")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def register():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    password = payload.get("password")
    role = payload.get("role", UserRole.student.value)

    if not name or not password:
        return jsonify({"msg": "name and password required"}), HTTPStatus.BAD_REQUEST

    if users.get_user_by_name(name):
        return jsonify({"msg": "user already exists"}), HTTPStatus.CONFLICT

    try:
        user = users.create_user(name=name, password=password, role=role)
    except ValueError as exc:  # invalid role
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    actor_id = get_jwt_identity()
    audit.record_action(
        user_id=actor_id,
        action=AuditAction.create_user,
        description="Admin registered new user",
        payload={"new_user": user.id, "role": user.role.value},
    )

    return jsonify({"msg": "user created", "id": user.id}), HTTPStatus.CREATED


@bp.post("/signup")
@limiter.limit("10 per minute", key_func=lambda: f"signup:{get_remote_address()}")
def signup():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    password = payload.get("password")
    requested_role = payload.get("role", UserRole.student.value)

    if not name or not password:
        return jsonify({"msg": "name and password required"}), HTTPStatus.BAD_REQUEST

    if requested_role not in {UserRole.student.value, UserRole.teacher.value}:
        return jsonify({"msg": "role not allowed for self-signup"}), HTTPStatus.FORBIDDEN

    if users.get_user_by_name(name):
        return jsonify({"msg": "user already exists"}), HTTPStatus.CONFLICT

    try:
        user = users.create_user(name=name, password=password, role=requested_role)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    response = jsonify({
        "id": user.id,
        "name": user.name,
        "role": user.role.value,
    })
    issue_tokens(response, user)

    audit.record_action(
        user_id=user.id,
        action=AuditAction.create_user,
        description="Self registration",
        payload={"role": user.role.value},
    )

    return response, HTTPStatus.CREATED


@bp.post("/refresh")
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def refresh():
    verify_jwt_in_request(refresh=True)
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    response = jsonify({"msg": "token refreshed"})
    from flask_jwt_extended import set_access_cookies

    set_access_cookies(response, access_token)
    return response, HTTPStatus.OK


@bp.get("/me")
@jwt_required()
@limiter.limit("120 per minute", key_func=authenticated_rate_limit_key)
def me():
    identity = get_jwt_identity()
    user = users.get_user_by_id(identity)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND
    return (
        jsonify(
            {
                "id": user.id,
                "name": user.name,
                "role": user.role.value,
            }
        ),
        HTTPStatus.OK,
    )
