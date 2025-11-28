from __future__ import annotations

import argparse
import sys
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from app import create_app
from app.models import UserRole
from app.services import users


DEFAULT_PASSWORD = "loadtest123"
USER_PREFIX = "load_student_"


@dataclass
class Config:
    count: int
    prefix: str = USER_PREFIX
    password: str = DEFAULT_PASSWORD


def ensure_users(config: Config) -> None:
    app = create_app()
    created = 0
    skipped = 0
    with app.app_context():
        for idx in range(config.count):
            username = f"{config.prefix}{idx:03d}"
            if users.get_user_by_name(username):
                skipped += 1
                continue
            users.create_user(name=username, password=config.password, role=UserRole.student.value)
            created += 1
    print(f"Requested: {config.count}, created: {created}, skipped (already existed): {skipped}")


def parse_args() -> Config:
    parser = argparse.ArgumentParser(description="Generate load-testing student accounts.")
    parser.add_argument(
        "--count",
        type=int,
        default=120,
        help="Number of student accounts to ensure exist (default: %(default)s).",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default=USER_PREFIX,
        help="Username prefix to use for generated accounts (default: %(default)s).",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=DEFAULT_PASSWORD,
        help="Password to set for generated accounts (default: %(default)s).",
    )
    args = parser.parse_args()
    return Config(count=args.count, prefix=args.prefix, password=args.password)


def main() -> None:
    config = parse_args()
    ensure_users(config)


if __name__ == "__main__":
    main()

