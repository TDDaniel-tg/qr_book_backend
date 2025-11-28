from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import selectinload

from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import Reservation, ReservationStatus, Room, User
from ..utils.pagination import Page, paginate_select

RESERVATION_LOOKAHEAD_HOURS = 24


class ReservationConflictError(ValueError):
    """Raised when a requested reservation overlaps an existing booking."""


def room_schedule(room: Room) -> List[Reservation]:
    return list(
        db.session.execute(
            db.select(Reservation)
            .options(selectinload(Reservation.user))
            .filter_by(room_id=room.id)
            .order_by(Reservation.start_time.asc())
        ).scalars()
    )


def active_reservations_for_room(room_id: int) -> Sequence[Reservation]:
    return list(
        db.session.execute(
            db.select(Reservation)
            .filter(
                Reservation.room_id == room_id,
                Reservation.status == ReservationStatus.active,
            )
            .order_by(Reservation.start_time.asc())
        ).scalars()
    )


def current_active_reservation(room_id: int, *, at: datetime | None = None) -> Reservation | None:
    ref = at or datetime.utcnow()
    return db.session.execute(
        select(Reservation)
        .options(selectinload(Reservation.user))
        .filter(
            Reservation.room_id == room_id,
            Reservation.status == ReservationStatus.active,
            Reservation.start_time <= ref,
            Reservation.end_time > ref,
        )
        .order_by(Reservation.start_time.asc())
    ).scalars().first()


def next_reservation(room_id: int, *, after: datetime | None = None) -> Reservation | None:
    ref = after or datetime.utcnow()
    return db.session.execute(
        select(Reservation)
        .options(selectinload(Reservation.user))
        .filter(
            Reservation.room_id == room_id,
            Reservation.status == ReservationStatus.active,
            Reservation.start_time > ref,
        )
        .order_by(Reservation.start_time.asc())
    ).scalars().first()


def reservations_for_user(user_id: int) -> Sequence[Reservation]:
    return list(
        db.session.execute(
            db.select(Reservation)
            .options(selectinload(Reservation.room))
            .filter_by(user_id=user_id)
            .order_by(Reservation.start_time.desc())
        ).scalars()
    )


def get_reservation(reservation_id: int) -> Optional[Reservation]:
    return db.session.get(Reservation, reservation_id)


def _validate_time_range(start: datetime, end: datetime) -> None:
    # Проверяем корректность времени
    # Нельзя создать бронь в прошлом
    if start >= end:
        raise ValueError("Invalid time range: start must be before end")
    if start < datetime.utcnow():
        raise ValueError("Cannot create reservation in the past")


def _ensure_within_room_hours(room: Room, start: datetime, end: datetime) -> None:
    booking_start: time | None = getattr(room, "booking_start", None)
    booking_end: time | None = getattr(room, "booking_end", None)
    if booking_start is None and booking_end is None:
        return
    if booking_start and start.time() < booking_start:
        raise ValueError("Reservation starts before allowed time")
    if booking_end and end.time() > booking_end:
        raise ValueError("Reservation ends after allowed time")


def _check_conflicts(*, room_id: int, start: datetime, end: datetime, exclude_id: int | None = None) -> None:
    query = (
        select(Reservation)
        .filter(
        Reservation.room_id == room_id,
        Reservation.status == ReservationStatus.active,
        or_(
            and_(Reservation.start_time <= start, Reservation.end_time > start),
            and_(Reservation.start_time < end, Reservation.end_time >= end),
            and_(Reservation.start_time >= start, Reservation.end_time <= end),
        ),
        )
        .order_by(Reservation.start_time.asc())
        .with_for_update(of=Reservation)
    )
    if exclude_id is not None:
        query = query.filter(Reservation.id != exclude_id)

    conflict_exists = db.session.execute(query).first()
    if conflict_exists:
        raise ReservationConflictError("Reservation conflicts with existing booking")


def create_reservation(*, room: Room, user_id: int, start: datetime, end: datetime) -> Reservation:
    _validate_time_range(start, end)
    try:
        with db.session.begin_nested():
            _check_conflicts(room_id=room.id, start=start, end=end)
            reservation = Reservation(
                room_id=room.id,
                user_id=user_id,
                start_time=start,
                end_time=end,
                status=ReservationStatus.active,
            )
            db.session.add(reservation)
        db.session.commit()
        db.session.refresh(reservation)
        return reservation
    except ReservationConflictError:
        db.session.rollback()
        raise
    except IntegrityError as exc:
        db.session.rollback()
        raise ReservationConflictError("Reservation conflicts with existing booking") from exc


def search_reservations(
    *,
    search: str | None = None,
    room_ids: Sequence[int] | None = None,
    user_ids: Sequence[int] | None = None,
    statuses: Sequence[ReservationStatus] | None = None,
    start_from: datetime | None = None,
    start_to: datetime | None = None,
    end_from: datetime | None = None,
    end_to: datetime | None = None,
    page: int = 1,
    per_page: int = 20,
) -> Page:
    query: Select[tuple[Reservation]] = (
        select(Reservation)
        .options(
            selectinload(Reservation.room),
            selectinload(Reservation.user),
        )
        .order_by(Reservation.start_time.desc())
    )

    conditions = []
    if room_ids:
        conditions.append(Reservation.room_id.in_(tuple(room_ids)))
    if user_ids:
        conditions.append(Reservation.user_id.in_(tuple(user_ids)))
    if statuses:
        conditions.append(Reservation.status.in_(tuple(statuses)))
    if start_from:
        conditions.append(Reservation.start_time >= start_from)
    if start_to:
        conditions.append(Reservation.start_time <= start_to)
    if end_from:
        conditions.append(Reservation.end_time >= end_from)
    if end_to:
        conditions.append(Reservation.end_time <= end_to)
    if search:
        token = f"%{search.lower()}%"
        conditions.append(
            or_(
                Reservation.room.has(func.lower(Room.name).like(token)),
                Reservation.user.has(func.lower(User.name).like(token)),
            )
        )

    if conditions:
        query = query.filter(and_(*conditions))

    return paginate_select(query, page=page, per_page=per_page)


def update_reservation_times(
    reservation: Reservation,
    *,
    start: datetime,
    end: datetime,
) -> Reservation:
    _validate_time_range(start, end)
    _check_conflicts(room_id=reservation.room_id, start=start, end=end, exclude_id=reservation.id)

    reservation.start_time = start
    reservation.end_time = end
    db.session.commit()
    return reservation


def cancel_reservation(reservation: Reservation) -> Reservation:
    if reservation.status == ReservationStatus.cancelled:
        return reservation
    reservation.status = ReservationStatus.cancelled
    db.session.commit()
    return reservation


def set_status(reservation: Reservation, *, status: ReservationStatus) -> Reservation:
    reservation.status = status
    db.session.commit()
    return reservation


def bulk_cancel_reservations(reservation_ids: Sequence[int]) -> int:
    if not reservation_ids:
        return 0
    updated = db.session.execute(
        db.update(Reservation)
        .where(Reservation.id.in_(tuple(reservation_ids)))
        .values(status=ReservationStatus.cancelled)
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    return updated.rowcount or 0


def reassign_reservation(reservation: Reservation, *, user_id: int) -> Reservation:
    reservation.user_id = user_id
    db.session.commit()
    return reservation


def upcoming_free_windows(room: Room, *, period_hours: int = RESERVATION_LOOKAHEAD_HOURS) -> list[dict[str, datetime]]:
    start_range = datetime.utcnow()
    end_range = start_range + timedelta(hours=period_hours)
    slots: list[dict[str, datetime]] = []

    reservations = [
        r
        for r in active_reservations_for_room(room.id)
        if r.end_time > start_range and r.start_time < end_range
    ]

    pointer = start_range
    for res in reservations:
        if res.start_time > pointer:
            slots.append({"start": pointer, "end": min(res.start_time, end_range)})
        pointer = max(pointer, res.end_time)

    if pointer < end_range:
        slots.append({"start": pointer, "end": end_range})

    return slots
