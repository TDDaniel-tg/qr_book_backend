from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus
from typing import Iterable, Sequence

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity

from ..extensions import limiter
from ..models import AuditAction, ReservationStatus, RoomType, UserRole
from ..security import authenticated_rate_limit_key, role_required
from ..services import audit, reports, reservations, rooms, users
from ..utils.datetime import as_utc_iso
from .rooms import _serialize_room

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _parse_datetime(value: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError as exc:
        raise ValueError("Invalid datetime format") from exc


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError("Invalid boolean value")


def _coerce_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        parsed = _parse_bool(value)
        if parsed is None:
            raise ValueError("Invalid boolean value")
        return parsed
    if isinstance(value, (int, float)):
        if value in {0, 1}:
            return bool(value)
    raise ValueError("Invalid boolean value")


def _serialize_reservation(reservation) -> dict:
    room = reservation.room
    user = reservation.user
    return {
        "id": reservation.id,
        "room": {"id": room.id, "name": room.name} if room else None,
        "user": (
            {"id": user.id, "name": user.name, "role": user.role.value}
            if user
            else None
        ),
        "start_time": as_utc_iso(reservation.start_time),
        "end_time": as_utc_iso(reservation.end_time),
        "status": reservation.status.value,
        "created_at": as_utc_iso(reservation.created_at),
        "updated_at": as_utc_iso(reservation.updated_at),
    }


def _serialize_user(user) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "role": user.role.value,
        "created_at": as_utc_iso(user.created_at),
        "updated_at": as_utc_iso(user.updated_at),
    }


def _parse_pagination_args() -> tuple[int, int] | tuple[None, None]:
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        return page, per_page
    except (TypeError, ValueError):
        return None, None


@bp.get("/rooms")
@role_required({UserRole.admin})
@limiter.limit("60 per minute", key_func=authenticated_rate_limit_key)
def admin_list_rooms():
    page, per_page = _parse_pagination_args()
    if page is None or per_page is None:
        return jsonify({"msg": "invalid pagination parameters"}), HTTPStatus.BAD_REQUEST

    search = request.args.get("q")
    status = request.args.get("status")
    if status and status not in {"available", "occupied", "blocked"}:
        return jsonify({"msg": "invalid status filter"}), HTTPStatus.BAD_REQUEST

    type_params = request.args.getlist("type")
    room_types: Iterable[RoomType] | None = None
    if type_params:
        try:
            room_types = tuple(RoomType(value) for value in type_params)
        except ValueError:
            return jsonify({"msg": "invalid room type"}), HTTPStatus.BAD_REQUEST

    try:
        is_blocked = _parse_bool(request.args.get("is_blocked"))
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    page_obj = rooms.search_rooms(
        search=search,
        room_types=room_types,
        is_blocked=is_blocked,
        status=status,
        page=page,
        per_page=per_page,
    )

    now = datetime.utcnow()
    data = [_serialize_room(room, now=now) for room in page_obj.items]

    return (
        jsonify(
            {
                "rooms": data,
                "pagination": {
                    "page": page_obj.page,
                    "per_page": page_obj.per_page,
                    "total": page_obj.total,
                    "pages": page_obj.pages,
                },
            }
        ),
        HTTPStatus.OK,
    )


@bp.post("/rooms")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def create_room():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    room_type_value = payload.get("type", RoomType.public.value)

    if not name:
        return jsonify({"msg": "name is required"}), HTTPStatus.BAD_REQUEST

    try:
        room_type = RoomType(room_type_value)
    except ValueError:
        return jsonify({"msg": "invalid room type"}), HTTPStatus.BAD_REQUEST

    room = rooms.create_room(name=name, room_type=room_type)
    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.update_room,
        description="Admin created room",
        payload={"room_id": room.id},
    )
    now = datetime.utcnow()
    return jsonify({"room": _serialize_room(room, now=now)}), HTTPStatus.CREATED


@bp.patch("/rooms/<int:room_id>")
@role_required({UserRole.admin})
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def update_room(room_id: int):
    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    room_type_value = payload.get("type")
    is_blocked_raw = payload.get("is_blocked")
    is_blocked = None
    if is_blocked_raw is not None:
        try:
            is_blocked = _coerce_bool(is_blocked_raw)
        except ValueError as exc:
            return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    room_type = None
    if room_type_value is not None:
        try:
            room_type = RoomType(room_type_value)
        except ValueError:
            return jsonify({"msg": "invalid room type"}), HTTPStatus.BAD_REQUEST

    updated_room = rooms.update_room(
        room,
        name=name,
        room_type=room_type,
        is_blocked=is_blocked,
    )

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.update_room,
        description="Admin updated room",
        payload={"room_id": updated_room.id},
    )

    now = datetime.utcnow()

    return jsonify({"room": _serialize_room(updated_room, now=now)}), HTTPStatus.OK


@bp.post("/rooms/bulk/block")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def bulk_block_rooms():
    payload = request.get_json(silent=True) or {}
    room_ids = payload.get("room_ids")
    is_blocked = payload.get("is_blocked")

    if (
        not isinstance(room_ids, Sequence)
        or isinstance(room_ids, (str, bytes))
        or not room_ids
    ):
        return jsonify({"msg": "room_ids must be a non-empty list"}), HTTPStatus.BAD_REQUEST
    try:
        room_id_values = [int(value) for value in room_ids]
    except (TypeError, ValueError):
        return jsonify({"msg": "room_ids must contain integers"}), HTTPStatus.BAD_REQUEST

    if is_blocked is None:
        return jsonify({"msg": "is_blocked flag required"}), HTTPStatus.BAD_REQUEST

    try:
        flag = _coerce_bool(is_blocked)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    updated_count = rooms.bulk_set_block_status(room_id_values, is_blocked=flag)
    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.update_room,
        description="Admin bulk updated room block status",
        payload={"room_ids": room_id_values, "is_blocked": flag},
    )
    return jsonify({"updated": updated_count}), HTTPStatus.OK


@bp.post("/rooms/<int:room_id>/generate-qr")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def regenerate_qr(room_id: int):
    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND

    rooms.sync_room_qr(room)
    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.update_room,
        description="Admin regenerated room QR",
        payload={"room_id": room.id},
    )
    return jsonify({"qr_code_url": room.qr_code_url}), HTTPStatus.OK


@bp.post("/rooms/<int:room_id>/reserve")
@role_required({UserRole.admin})
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def create_reservation_for_room(room_id: int):
    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    if not user_id:
        return jsonify({"msg": "user_id is required"}), HTTPStatus.BAD_REQUEST

    user = users.get_user_by_id(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    if not start_time or not end_time:
        return jsonify({"msg": "start_time and end_time required"}), HTTPStatus.BAD_REQUEST

    try:
        start = _parse_datetime(start_time)
        end = _parse_datetime(end_time)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    try:
        reservation = reservations.create_reservation(
            room=room,
            user_id=user.id,
            start=start,
            end=end,
        )
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.create_reservation,
        description="Admin created reservation",
        payload={"reservation_id": reservation.id, "room_id": room.id},
    )

    return jsonify({"reservation_id": reservation.id}), HTTPStatus.CREATED


@bp.get("/reservations")
@role_required({UserRole.admin})
@limiter.limit("60 per minute", key_func=authenticated_rate_limit_key)
def admin_list_reservations():
    page, per_page = _parse_pagination_args()
    if page is None or per_page is None:
        return jsonify({"msg": "invalid pagination parameters"}), HTTPStatus.BAD_REQUEST

    status_params = request.args.getlist("status")
    statuses: Sequence[ReservationStatus] | None = None
    if status_params:
        try:
            statuses = tuple(ReservationStatus(value) for value in status_params)
        except ValueError:
            return jsonify({"msg": "invalid reservation status"}), HTTPStatus.BAD_REQUEST

    try:
        room_id = int(request.args["room_id"]) if "room_id" in request.args else None
    except ValueError:
        return jsonify({"msg": "room_id must be integer"}), HTTPStatus.BAD_REQUEST
    try:
        user_id = int(request.args["user_id"]) if "user_id" in request.args else None
    except ValueError:
        return jsonify({"msg": "user_id must be integer"}), HTTPStatus.BAD_REQUEST

    date_filters = {}
    for arg in ("start_from", "start_to", "end_from", "end_to"):
        value = request.args.get(arg)
        if value:
            try:
                date_filters[arg] = _parse_datetime(value)
            except ValueError as exc:
                return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    page_obj = reservations.search_reservations(
        search=request.args.get("q"),
        room_ids=[room_id] if room_id else None,
        user_ids=[user_id] if user_id else None,
        statuses=statuses,
        start_from=date_filters.get("start_from"),
        start_to=date_filters.get("start_to"),
        end_from=date_filters.get("end_from"),
        end_to=date_filters.get("end_to"),
        page=page,
        per_page=per_page,
    )

    data = [_serialize_reservation(reservation) for reservation in page_obj.items]
    return (
        jsonify(
            {
                "reservations": data,
                "pagination": {
                    "page": page_obj.page,
                    "per_page": page_obj.per_page,
                    "total": page_obj.total,
                    "pages": page_obj.pages,
                },
            }
        ),
        HTTPStatus.OK,
    )


@bp.patch("/reservations/<int:reservation_id>")
@role_required({UserRole.admin})
@limiter.limit("40 per minute", key_func=authenticated_rate_limit_key)
def admin_update_reservation(reservation_id: int):
    reservation = reservations.get_reservation(reservation_id)
    if not reservation:
        return jsonify({"msg": "reservation not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    start_time = payload.get("start_time")
    end_time = payload.get("end_time")
    status_value = payload.get("status")
    user_id = payload.get("user_id")

    updated = reservation

    if (start_time is not None) ^ (end_time is not None):
        return jsonify({"msg": "start_time and end_time must be provided together"}), HTTPStatus.BAD_REQUEST

    if start_time and end_time:
        try:
            start = _parse_datetime(start_time)
            end = _parse_datetime(end_time)
        except ValueError as exc:
            return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST
        try:
            updated = reservations.update_reservation_times(
                updated,
                start=start,
                end=end,
            )
        except ValueError as exc:
            return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    if user_id is not None:
        target_user = users.get_user_by_id(user_id)
        if not target_user:
            return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND
        updated = reservations.reassign_reservation(updated, user_id=target_user.id)

    if status_value:
        try:
            status_enum = ReservationStatus(status_value)
        except ValueError:
            return jsonify({"msg": "invalid reservation status"}), HTTPStatus.BAD_REQUEST
        if status_enum == ReservationStatus.cancelled:
            updated = reservations.cancel_reservation(updated)
        else:
            updated = reservations.set_status(updated, status=status_enum)

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.update_reservation,
        description="Admin updated reservation",
        payload={"reservation_id": updated.id},
    )

    return jsonify({"reservation": _serialize_reservation(updated)}), HTTPStatus.OK


@bp.post("/reservations/bulk-cancel")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def admin_bulk_cancel_reservations():
    payload = request.get_json(silent=True) or {}
    reservation_ids = payload.get("reservation_ids")
    if (
        not isinstance(reservation_ids, Sequence)
        or isinstance(reservation_ids, (str, bytes))
        or not reservation_ids
    ):
        return jsonify({"msg": "reservation_ids must be a non-empty list"}), HTTPStatus.BAD_REQUEST
    try:
        reservation_values = [int(value) for value in reservation_ids]
    except (TypeError, ValueError):
        return jsonify({"msg": "reservation_ids must contain integers"}), HTTPStatus.BAD_REQUEST

    affected = reservations.bulk_cancel_reservations(reservation_values)
    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.cancel_reservation,
        description="Admin bulk cancelled reservations",
        payload={"reservation_ids": reservation_values},
    )
    return jsonify({"cancelled": affected}), HTTPStatus.OK


@bp.get("/users")
@role_required({UserRole.admin})
@limiter.limit("60 per minute", key_func=authenticated_rate_limit_key)
def admin_list_users():
    page, per_page = _parse_pagination_args()
    if page is None or per_page is None:
        return jsonify({"msg": "invalid pagination parameters"}), HTTPStatus.BAD_REQUEST

    roles_params = request.args.getlist("role")
    roles: Iterable[UserRole] | None = None
    if roles_params:
        try:
            roles = tuple(UserRole(value) for value in roles_params)
        except ValueError:
            return jsonify({"msg": "invalid user role"}), HTTPStatus.BAD_REQUEST

    page_obj = users.search_users(
        search=request.args.get("q"),
        roles=roles,
        page=page,
        per_page=per_page,
    )

    data = [_serialize_user(user) for user in page_obj.items]
    return (
        jsonify(
            {
                "users": data,
                "pagination": {
                    "page": page_obj.page,
                    "per_page": page_obj.per_page,
                    "total": page_obj.total,
                    "pages": page_obj.pages,
                },
            }
        ),
        HTTPStatus.OK,
    )


@bp.post("/users")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def admin_create_user():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    password = payload.get("password")
    role_value = payload.get("role", UserRole.student.value)

    if not name or not password:
        return jsonify({"msg": "name and password required"}), HTTPStatus.BAD_REQUEST

    try:
        user = users.create_user(name=name, password=password, role=role_value)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.create_user,
        description="Admin created user",
        payload={"user_id": user.id, "role": user.role.value},
    )

    return jsonify({"user": _serialize_user(user)}), HTTPStatus.CREATED


@bp.patch("/users/<int:user_id>")
@role_required({UserRole.admin})
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def admin_update_user(user_id: int):
    user = users.get_user_by_id(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    role_value = payload.get("role")

    role = None
    if role_value is not None:
        try:
            role = UserRole(role_value)
        except ValueError:
            return jsonify({"msg": "invalid user role"}), HTTPStatus.BAD_REQUEST

    updated = users.update_user(user, name=name, role=role)

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.create_user,
        description="Admin updated user",
        payload={"user_id": updated.id},
    )

    return jsonify({"user": _serialize_user(updated)}), HTTPStatus.OK


@bp.post("/users/<int:user_id>/reset-password")
@role_required({UserRole.admin})
@limiter.limit("20 per minute", key_func=authenticated_rate_limit_key)
def admin_reset_password(user_id: int):
    user = users.get_user_by_id(user_id)
    if not user:
        return jsonify({"msg": "user not found"}), HTTPStatus.NOT_FOUND

    payload = request.get_json(silent=True) or {}
    password = payload.get("password")
    if not password:
        return jsonify({"msg": "password is required"}), HTTPStatus.BAD_REQUEST

    try:
        updated = users.set_password(user, password=password)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    audit.record_action(
        user_id=get_jwt_identity(),
        action=AuditAction.create_user,
        description="Admin reset user password",
        payload={"user_id": updated.id},
    )

    return jsonify({"user": _serialize_user(updated)}), HTTPStatus.OK


@bp.get("/audit/logs")
@role_required({UserRole.admin})
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def get_audit_logs():
    logs = audit.list_logs(limit=200)
    return jsonify({
        "logs": [
            {
                "id": log.id,
                "actor_id": log.actor_id,
                "action": log.action.value,
                "description": log.description,
                "payload": log.payload,
                "created_at": as_utc_iso(log.created_at),
            }
            for log in logs
        ]
    }), HTTPStatus.OK


@bp.get("/stats")
@role_required({UserRole.admin})
@limiter.limit("30 per minute", key_func=authenticated_rate_limit_key)
def get_dashboard_stats():
    data = reports.dashboard_snapshot()
    return jsonify({"stats": data}), HTTPStatus.OK
