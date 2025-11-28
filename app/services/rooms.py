from __future__ import annotations

from datetime import datetime, time
from typing import Iterable, Optional, Sequence

from sqlalchemy import Select, and_, exists, func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Reservation, ReservationStatus, Room, RoomType
from ..utils import generate_room_qr
from ..utils.pagination import Page, paginate_select


def get_room(room_id: int) -> Optional[Room]:
    return db.session.get(Room, room_id)


def get_room_by_name(name: str) -> Optional[Room]:
    return db.session.execute(db.select(Room).filter_by(name=name)).scalar_one_or_none()


def list_rooms() -> list[Room]:
    return list(db.session.execute(db.select(Room).order_by(Room.name)).scalars())


def search_rooms(
    *,
    search: str | None = None,
    room_types: Iterable[RoomType] | None = None,
    is_blocked: bool | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> Page:
    query: Select[tuple[Room]] = (
        select(Room)
        .options(selectinload(Room.reservations))
        .order_by(Room.name)
    )

    conditions = []
    if search:
        token = f"%{search.lower()}%"
        conditions.append(func.lower(Room.name).like(token))
    if room_types:
        conditions.append(Room.type.in_(tuple(room_types)))
    if is_blocked is not None:
        conditions.append(Room.is_blocked.is_(is_blocked))

    now = datetime.utcnow()
    active_exists = (
        select(Reservation.id)
        .filter(
            Reservation.room_id == Room.id,
            Reservation.status == ReservationStatus.active,
            Reservation.start_time <= now,
            Reservation.end_time > now,
        )
        .limit(1)
    )

    if status == "occupied":
        conditions.append(exists(active_exists))
    elif status == "available":
        conditions.append(~exists(active_exists))
        conditions.append(Room.is_blocked.is_(False))
    elif status == "blocked":
        conditions.append(Room.is_blocked.is_(True))

    if conditions:
        query = query.filter(and_(*conditions))

    page_obj = paginate_select(query, page=page, per_page=per_page)

    return page_obj


def create_room(
    *,
    name: str,
    room_type: RoomType,
    qr_code_url: str | None = None,
    booking_start: time | None = None,
    booking_end: time | None = None,
) -> Room:
    room = Room(
        name=name,
        type=room_type,
        qr_code_url=qr_code_url,
        booking_start=booking_start,
        booking_end=booking_end,
    )
    db.session.add(room)
    db.session.commit()
    if not qr_code_url:
        sync_room_qr(room)
    return room


_UNSET = object()


def update_room(
    room: Room,
    *,
    name: str | None = None,
    room_type: RoomType | None = None,
    is_blocked: bool | None = None,
    booking_start: time | None | object = _UNSET,
    booking_end: time | None | object = _UNSET,
) -> Room:
    if name is not None:
        room.name = name
    if room_type is not None:
        room.type = room_type
    if is_blocked is not None:
        room.is_blocked = is_blocked
    if booking_start is not _UNSET:
        room.booking_start = booking_start  # type: ignore[assignment]
    if booking_end is not _UNSET:
        room.booking_end = booking_end  # type: ignore[assignment]
    db.session.commit()
    return room


def sync_room_qr(room: Room) -> Room:
    _, public_url = generate_room_qr(room.id)
    room.qr_code_url = public_url
    db.session.commit()
    return room


def bulk_set_block_status(room_ids: Sequence[int], *, is_blocked: bool) -> int:
    if not room_ids:
        return 0
    updated = (
        db.session.execute(
            db.update(Room)
            .where(Room.id.in_(tuple(room_ids)))
            .values(is_blocked=is_blocked)
            .execution_options(synchronize_session=False)
        )
    )
    db.session.commit()
    return updated.rowcount or 0
