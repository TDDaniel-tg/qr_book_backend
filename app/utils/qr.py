from __future__ import annotations

from pathlib import Path
from typing import Tuple
from urllib.parse import urljoin

import qrcode
from flask import current_app


def generate_room_qr(room_id: int) -> Tuple[str, str]:
    """Generate QR code PNG for given room and return (file_path, public_url)."""
    app = current_app
    qr_dir = Path(app.config["STATIC_QR_PATH"])
    qr_dir.mkdir(parents=True, exist_ok=True)

    target_base = app.config.get("QR_BASE_URL") or app.config.get("FRONTEND_BASE_URL")
    if target_base:
        target_base = target_base.rstrip("/") + "/"
    else:
        target_base = app.config.get("SERVER_EXTERNAL_BASE", "http://localhost:5000/")

    target_url = urljoin(target_base, f"rooms/{room_id}")

    file_name = f"{room_id}.png"
    file_path = qr_dir / file_name

    # TODO: добавить подпись QR-кода для слабовидящих пользователей
    image = qrcode.make(target_url)
    image.save(file_path)

    public_path = f"static/qr/{file_name}"
    public_url = urljoin(app.config.get("SERVER_EXTERNAL_BASE", "http://localhost:5000/"), public_path)
    return str(file_path), public_url
