from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import create_app
from app.extensions import db
from app.models import RoomType, UserRole
from app.services import rooms, users


def seed_users():
    if not users.get_user_by_name('admin'):
        users.create_user(name='admin', password='admin1234', role=UserRole.admin.value)
    if not users.get_user_by_name('teacher'):
        users.create_user(name='teacher', password='teacher1234', role=UserRole.teacher.value)
    if not users.get_user_by_name('student'):
        users.create_user(name='student', password='student1234', role=UserRole.student.value)
    if not users.get_user_by_name('guest'):
        users.create_user(name='guest', password='guest1234', role=UserRole.student.value)


def seed_rooms():
    existing = {room.name: room for room in rooms.list_rooms()}
    defaults = [
        ('B101', RoomType.public),
        ('B102', RoomType.public),
        ('A200', RoomType.admin),
        ('S001', RoomType.service),
    ]
    for name, room_type in defaults:
        if name not in existing:
            room = rooms.create_room(name=name, room_type=room_type)
            rooms.sync_room_qr(room)


def seed_reservations():
    from app.services import reservations

    teacher = users.get_user_by_name('teacher')
    student = users.get_user_by_name('student')
    guest = users.get_user_by_name('guest')
    if not teacher or not student:
        return

    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0, tzinfo=None)

    def ensure_booking(room_name: str, *, user_id: int, start: datetime, end: datetime) -> None:
        room_obj = rooms.get_room_by_name(room_name)
        if not room_obj:
            return
        duration = end - start
        now_local = datetime.utcnow()
        create_start = start if start >= now_local else now_local + timedelta(minutes=5)
        create_end = create_start + duration
        try:
            reservation = reservations.create_reservation(
                room=room_obj,
                user_id=user_id,
                start=create_start,
                end=create_end,
            )
            reservation.start_time = start
            reservation.end_time = end
            db.session.commit()
        except ValueError:
            pass

    ensure_booking(
        'B101',
        user_id=teacher.id,
        start=now - timedelta(minutes=30),
        end=now + timedelta(hours=1, minutes=30),
    )

    ensure_booking(
        'B102',
        user_id=student.id,
        start=now + timedelta(hours=2),
        end=now + timedelta(hours=4),
    )

    if guest:
        ensure_booking(
            'A200',
            user_id=guest.id,
            start=now + timedelta(hours=6),
            end=now + timedelta(hours=8),
        )


def run():
    app = create_app()
    with app.app_context():
        seed_users()
        seed_rooms()
        seed_reservations()
        print('Seed completed')


if __name__ == '__main__':
    # TODO: добавить импорт данных из CSV
    run()
