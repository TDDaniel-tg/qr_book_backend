from __future__ import annotations

import enum
from datetime import datetime, time

from sqlalchemy import Enum, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .extensions import db


def utcnow() -> datetime:
    return datetime.utcnow()


class RoomType(enum.Enum):
    public = "public"
    admin = "admin"
    service = "service"


class ReservationStatus(enum.Enum):
    active = "active"
    finished = "finished"
    cancelled = "cancelled"


class UserRole(enum.Enum):
    student = "student"
    teacher = "teacher"
    admin = "admin"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=utcnow, onupdate=utcnow, nullable=False
    )


class User(db.Model, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False)
    hashed_password: Mapped[str]

    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation", back_populates="user", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        "AuditLog", back_populates="actor", cascade="all, delete-orphan"
    )


class Room(db.Model, TimestampMixin):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True, nullable=False)
    type: Mapped[RoomType] = mapped_column(Enum(RoomType), nullable=False)
    qr_code_url: Mapped[str | None]
    is_blocked: Mapped[bool] = mapped_column(default=False, nullable=False)
    booking_start: Mapped[time | None] = mapped_column(Time, nullable=True)
    booking_end: Mapped[time | None] = mapped_column(Time, nullable=True)

    reservations: Mapped[list[Reservation]] = relationship(
        "Reservation", back_populates="room", cascade="all, delete-orphan"
    )


class Reservation(db.Model, TimestampMixin):
    __tablename__ = "reservations"
    __table_args__ = (
        UniqueConstraint("room_id", "start_time", "end_time", name="uq_room_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(db.ForeignKey("rooms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(db.ForeignKey("users.id"), nullable=False)
    start_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(nullable=False, index=True)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.active, nullable=False
    )

    room: Mapped[Room] = relationship("Room", back_populates="reservations")
    user: Mapped[User] = relationship("User", back_populates="reservations")


class AuditAction(enum.Enum):
    create_reservation = "create_reservation"
    cancel_reservation = "cancel_reservation"
    update_reservation = "update_reservation"
    update_room = "update_room"
    create_user = "create_user"
    login = "login"
    logout = "logout"


class AuditLog(db.Model, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(db.ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    description: Mapped[str | None]
    payload: Mapped[dict | None] = mapped_column(db.JSON)

    actor: Mapped[User | None] = relationship("User", back_populates="audit_logs")
