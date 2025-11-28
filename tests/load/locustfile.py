from __future__ import annotations

import os
import random
import threading
from datetime import datetime, timedelta
from itertools import cycle

from locust import HttpUser, between, task


USER_PREFIX = os.getenv("LOADTEST_USER_PREFIX", "load_student_")
USER_PASSWORD = os.getenv("LOADTEST_USER_PASSWORD", "loadtest123")
USER_POOL_SIZE = int(os.getenv("LOADTEST_USER_POOL_SIZE", "120"))
RESERVATION_MIN_OFFSET_MIN = int(os.getenv("LOADTEST_MIN_OFFSET_MIN", "30"))
RESERVATION_MAX_OFFSET_MIN = int(os.getenv("LOADTEST_MAX_OFFSET_MIN", "720"))
RESERVATION_DURATION_MIN = int(os.getenv("LOADTEST_DURATION_MIN", "45"))


class QRBooksUser(HttpUser):
    wait_time = between(0.5, 1.5)

    _user_iterator = cycle(range(USER_POOL_SIZE))
    _lock = threading.Lock()
    _public_room_ids: list[int] | None = None

    def on_start(self) -> None:
        self.username = self._acquire_username()
        self._authenticate()
        if QRBooksUser._public_room_ids is None:
            self._warm_up_rooms()

    def _acquire_username(self) -> str:
        with QRBooksUser._lock:
            next_idx = next(QRBooksUser._user_iterator)
        return f"{USER_PREFIX}{next_idx:03d}"

    def _authenticate(self) -> None:
        response = self.client.post(
            "/auth/login",
            json={
                "name": self.username,
                "password": USER_PASSWORD,
            },
            name="auth_login",
        )
        if response.status_code != 200:
            response.raise_for_status()
        self._csrf_access_token = self.client.cookies.get("csrf_access_token")
        self._csrf_refresh_token = self.client.cookies.get("csrf_refresh_token")

    def _csrf_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._csrf_access_token:
            headers["X-CSRF-TOKEN"] = self._csrf_access_token
        return headers

    def _warm_up_rooms(self) -> None:
        response = self.client.get("/rooms", name="rooms_list")
        response.raise_for_status()
        payload = response.json()
        QRBooksUser._public_room_ids = [
            room["id"] for room in payload.get("rooms", []) if room.get("type") == "public"
        ]
        if not QRBooksUser._public_room_ids:
            raise RuntimeError("No public rooms available for load test.")

    @task(4)
    def list_rooms(self) -> None:
        self.client.get("/rooms", name="rooms_list")

    @task(2)
    def view_my_reservations(self) -> None:
        self.client.get("/reservations/mine", name="reservations_mine")

    @task(1)
    def create_reservation(self) -> None:
        if not QRBooksUser._public_room_ids:
            return
        room_id = random.choice(QRBooksUser._public_room_ids)
        now = datetime.utcnow().replace(second=0, microsecond=0)
        offset = random.randint(RESERVATION_MIN_OFFSET_MIN, RESERVATION_MAX_OFFSET_MIN)
        duration = RESERVATION_DURATION_MIN + random.randint(0, 30)
        start_time = now + timedelta(minutes=offset)
        end_time = start_time + timedelta(minutes=duration)
        payload = {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        }
        response = self.client.post(
            f"/rooms/{room_id}/reserve",
            json=payload,
            headers=self._csrf_headers(),
            name="rooms_reserve",
        )
        if response.status_code not in (201, 400, 401, 403, 409, 429):
            response.raise_for_status()

    def on_stop(self) -> None:
        self.client.post("/auth/logout", headers=self._csrf_headers(), name="auth_logout")

