from __future__ import annotations

from datetime import datetime, timezone, time
from http import HTTPStatus

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from ..extensions import limiter
from ..models import AuditAction, RoomType
from ..security import authenticated_rate_limit_key
from ..services import audit, reservations, rooms
from ..services.reservations import ReservationConflictError
from ..utils.datetime import as_utc_iso

bp = Blueprint("rooms", __name__, url_prefix="/rooms")

def _current_user_id() -> int | None:
    identity = get_jwt_identity()
    try:
        return int(identity) if identity is not None else None
    except (TypeError, ValueError):
        return None


def _serialize_room(room, *, now: datetime):
    active = reservations.current_active_reservation(room.id, at=now)
    upcoming = reservations.next_reservation(room.id, after=now)
    if room.is_blocked:
        status = "blocked"
    elif active:
        status = "occupied"
    else:
        status = "available"
    return {
        "id": room.id,
        "name": room.name,
        "type": room.type.value,
        "is_blocked": room.is_blocked,
        "qr_code_url": room.qr_code_url,
        "status": status,
        "current_reservation": (
            {
                "id": active.id,
                "user_id": active.user_id,
                "user_name": active.user.name if active.user else None,
                "end_time": as_utc_iso(active.end_time),
            }
            if active
            else None
        ),
        "next_reservation": (
            {
                "id": upcoming.id,
                "start_time": as_utc_iso(upcoming.start_time),
                "user_name": upcoming.user.name if upcoming.user else None,
            }
            if upcoming
            else None
        ),
        "booking_window": {
            "start": _format_time(room.booking_start),
            "end": _format_time(room.booking_end),
        },
    }


def _format_time(value: time | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%H:%M")


def _parse_datetime(value: str | None) -> datetime:
    if not value:
        raise ValueError("datetime value is required")
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError as exc:
        raise ValueError("Invalid datetime format. Use ISO 8601.") from exc


@bp.get("")
@limiter.limit("1200 per minute")
def list_rooms():
    # Контроллер только получает запрос,
    # вся логика должна быть вынесена в services/reservations.py
    now = datetime.utcnow()
    data = [_serialize_room(room, now=now) for room in rooms.list_rooms()]
    return jsonify({"rooms": data}), HTTPStatus.OK


@bp.get("/<int:room_id>")
@limiter.limit("600 per minute")
def room_detail(room_id: int):
    # TODO: добавить защиту от попыток спама (rate-limiting)
    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND

    schedule = [
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
    free_slots = [
        {"start": as_utc_iso(slot["start"]), "end": as_utc_iso(slot["end"])}
        for slot in reservations.upcoming_free_windows(room)
    ]

    now = datetime.utcnow()
    room_payload = _serialize_room(room, now=now)

    return (
        jsonify(
            {
                "room": room_payload,
                "schedule": schedule,
                "free_slots": free_slots,
            }
        ),
        HTTPStatus.OK,
    )


@bp.post("/<int:room_id>/reserve")
@limiter.limit("180 per minute", key_func=authenticated_rate_limit_key)
def reserve_room(room_id: int):
    verify_jwt_in_request()
    user_id = _current_user_id()
    if user_id is None:
        return jsonify({"msg": "invalid user identity"}), HTTPStatus.UNAUTHORIZED
    payload = request.get_json(silent=True) or {}

    try:
        start = _parse_datetime(payload.get("start_time"))
        end = _parse_datetime(payload.get("end_time"))
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    room = rooms.get_room(room_id)
    if not room:
        return jsonify({"msg": "room not found"}), HTTPStatus.NOT_FOUND
    if room.type != RoomType.public:
        return jsonify({"msg": "room is not available for booking"}), HTTPStatus.FORBIDDEN
    if room.is_blocked:
        return jsonify({"msg": "room is temporarily unavailable"}), HTTPStatus.CONFLICT

    # Проверяем корректность времени
    # Нельзя создать бронь в прошлом
    try:
        reservation = reservations.create_reservation(
            room=room,
            user_id=user_id,
            start=start,
            end=end,
        )
    except ReservationConflictError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.CONFLICT
    except ValueError as exc:
        return jsonify({"msg": str(exc)}), HTTPStatus.BAD_REQUEST

    audit.record_action(
        user_id=user_id,
        action=AuditAction.create_reservation,
        description="Created reservation",
        payload={
            "reservation_id": reservation.id,
            "room_id": room.id,
            "start_time": as_utc_iso(reservation.start_time),
            "end_time": as_utc_iso(reservation.end_time),
        },
    )

    return (
        jsonify(
            {
                "reservation": {
                    "id": reservation.id,
                    "room_id": reservation.room_id,
                    "room_name": room.name,
                "start_time": as_utc_iso(reservation.start_time),
                "end_time": as_utc_iso(reservation.end_time),
                    "status": reservation.status.value,
                }
            }
        ),
        HTTPStatus.CREATED,
    )
