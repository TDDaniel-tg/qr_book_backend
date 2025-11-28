from __future__ import annotations

from datetime import datetime
from typing import Dict

from sqlalchemy import and_, func, select

from ..extensions import db
from ..models import (
    Reservation,
    ReservationStatus,
    Room,
    RoomType,
    User,
    UserRole,
)
from ..utils.datetime import as_utc_iso


def _enum_counter(enum_cls) -> Dict[str, int]:
    return {member.value: 0 for member in enum_cls}


def dashboard_snapshot() -> dict:
    """Collect aggregated metrics for the admin dashboard."""
    now = datetime.utcnow()

    total_rooms = db.session.execute(
        select(func.count()).select_from(Room)
    ).scalar_one()
    blocked_rooms = db.session.execute(
        select(func.count()).select_from(Room).filter(Room.is_blocked.is_(True))
    ).scalar_one()

    rooms_by_type = _enum_counter(RoomType)
    for room_type, count in db.session.execute(
        select(Room.type, func.count()).group_by(Room.type)
    ):
        rooms_by_type[room_type.value] = count

    active_reservations = db.session.execute(
        select(func.count()).select_from(Reservation).filter(
            Reservation.status == ReservationStatus.active,
            Reservation.start_time <= now,
            Reservation.end_time > now,
        )
    ).scalar_one()

    upcoming_reservations = db.session.execute(
        select(func.count()).select_from(Reservation).filter(
            Reservation.status == ReservationStatus.active,
            Reservation.start_time > now,
        )
    ).scalar_one()

    reservations_by_status = _enum_counter(ReservationStatus)
    for status, count in db.session.execute(
        select(Reservation.status, func.count()).group_by(Reservation.status)
    ):
        reservations_by_status[status.value] = count

    users_by_role = _enum_counter(UserRole)
    for role, count in db.session.execute(
        select(User.role, func.count()).group_by(User.role)
    ):
        users_by_role[role.value] = count

    total_reservations = sum(reservations_by_status.values())

    return {
        "rooms": {
            "total": total_rooms,
            "blocked": blocked_rooms,
            "available": max(total_rooms - blocked_rooms - active_reservations, 0),
            "active_now": active_reservations,
            "by_type": rooms_by_type,
        },
        "reservations": {
            "total": total_reservations,
            "active": active_reservations,
            "upcoming": upcoming_reservations,
            "by_status": reservations_by_status,
        },
        "users": {
            "total": sum(users_by_role.values()),
            "by_role": users_by_role,
        },
        "updated_at": as_utc_iso(now),
    }

