from __future__ import annotations

from datetime import datetime, timezone
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, verify_jwt_in_request

from ..extensions import limiter
from ..models import AuditAction, ReservationStatus, UserRole
from ..security import authenticated_rate_limit_key, role_required
from ..services import audit, reservations, rooms
from ..utils.datetime import as_utc_iso

bp = Blueprint("reservations", __name__, url_prefix="/reservations")

def _current_user_id() -> int | None:
    identity = get_jwt_identity()
    try:
        return int(identity) if identity is not None else None
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        raise ValueError("datetime is required")
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError as exc:
        raise ValueError("Invalid datetime format") from exc


@bp.get("/mine")
@limiter.limit("600 per minute", key_func=authenticated_rate_limit_key)
def my_reservations():
    verify_jwt_in_request()
    user_id = _current_user_id()
    if user_id is None:
        return jsonify({"msg": "invalid user identity"}), HTTPStatus.UNAUTHORIZED
    data = [
        {
            "id": reservation.id,
            "room_id": reservation.room_id,
            "room_name": reservation.room.name if reservation.room else None,
            "start_time": as_utc_iso(reservation.start_time),
            "end_time": as_utc_iso(reservation.end_time),
            "status": reservation.status.value,
        }
        for reservation in reservations.reservations_for_user(user_id)
    ]
    return jsonify({"reservations": data}), HTTPStatus.OK


@bp.patch("/<int:reservation_id>")
@role_required({UserRole.teacher, UserRole.admin})
@limiter.limit("120 per minute", key_func=authenticated_rate_limit_key)
def update_reservation(reservation_id: int):
    reservation = reservations.get_reservation(reservation_id)
    if not reservation:
        return jsonify({"msg": "reservation not found"}), HTTPStatus.NOT_FOUND
    if reservation.status != ReservationStatus.active:
        return jsonify({"msg": "only active reservations can be updated"}), HTTPStatus.BAD_REQUEST

    payload = request.get_json(silent=True) or {}
    try:
        start = _parse_datetime(payload.get("start_time"))
        end = _parse_datetime(payload.get("end_time"))
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    try:
        updated = reservations.update_reservation_times(reservation, start=start, end=end)
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    # TODO: добавить уведомление пользователям за 10 минут до брони
    actor_id = _current_user_id()
    audit.record_action(
        user_id=actor_id,
        action=AuditAction.update_reservation,
        description="Reservation updated",
        payload={"reservation_id": updated.id, "room_id": updated.room_id},
    )

    return jsonify({
        "reservation": {
            "id": updated.id,
            "start_time": as_utc_iso(updated.start_time),
            "end_time": as_utc_iso(updated.end_time),
            "status": updated.status.value,
        }
    }), HTTPStatus.OK


@bp.delete("/<int:reservation_id>")
@limiter.limit("180 per minute", key_func=authenticated_rate_limit_key)
def cancel_reservation(reservation_id: int):
    verify_jwt_in_request()
    reservation = reservations.get_reservation(reservation_id)
    if not reservation:
        return jsonify({"msg": "reservation not found"}), HTTPStatus.NOT_FOUND

    identity = _current_user_id()
    if identity is None:
        return jsonify({"msg": "invalid user identity"}), HTTPStatus.UNAUTHORIZED
    claims = get_jwt()
    role = claims.get("role")

    if reservation.user_id != identity and role not in {UserRole.teacher.value, UserRole.admin.value}:
        return jsonify({"msg": "insufficient permissions"}), HTTPStatus.FORBIDDEN

    updated = reservations.cancel_reservation(reservation)

    audit.record_action(
        user_id=identity,
        action=AuditAction.cancel_reservation,
        description="Reservation cancelled",
        payload={"reservation_id": updated.id, "room_id": updated.room_id},
    )

    return jsonify({"status": updated.status.value}), HTTPStatus.OK


@bp.get("/room/<int:room_id>/history")
@role_required({UserRole.teacher, UserRole.admin})
@limiter.limit("180 per minute", key_func=authenticated_rate_limit_key)
def room_history(room_id: int):
    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND

    history = [
        {
            "id": reservation.id,
            "user_id": reservation.user_id,
            "user_name": reservation.user.name if reservation.user else None,
            "start_time": as_utc_iso(reservation.start_time),
            "end_time": as_utc_iso(reservation.end_time),
            "status": reservation.status.value,
        }
        for reservation in reservations.room_schedule(room)
    ]

    return jsonify({"reservations": history}), HTTPStatus.OK
