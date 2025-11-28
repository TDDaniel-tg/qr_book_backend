from __future__ import annotations

from typing import Iterable, Optional, Sequence

from sqlalchemy import Select, and_, func, select

from ..extensions import bcrypt, db
from ..models import User, UserRole
from ..utils.pagination import Page, paginate_select


def get_user_by_name(name: str) -> Optional[User]:
    return db.session.execute(db.select(User).filter_by(name=name)).scalar_one_or_none()


def get_user_by_id(user_id: int) -> Optional[User]:
    return db.session.get(User, user_id)


def verify_password(user: User, password: str) -> bool:
    return bcrypt.check_password_hash(user.hashed_password, password)


def create_user(name: str, password: str, role: str) -> User:
    # TODO: валидировать сложность пароля и роль пользователя
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    role_enum = UserRole(role)
    user = User(name=name, hashed_password=hashed, role=role_enum)
    db.session.add(user)
    db.session.commit()
    return user


def search_users(
    *,
    search: str | None = None,
    roles: Iterable[UserRole] | None = None,
    page: int = 1,
    per_page: int = 20,
) -> Page:
    query: Select[tuple[User]] = select(User).order_by(User.name.asc())
    conditions = []
    if search:
        token = f"%{search.lower()}%"
        conditions.append(func.lower(User.name).like(token))
    if roles:
        conditions.append(User.role.in_(tuple(roles)))

    if conditions:
        query = query.filter(and_(*conditions))

    return paginate_select(query, page=page, per_page=per_page)


def update_user(
    user: User,
    *,
    name: str | None = None,
    role: UserRole | None = None,
) -> User:
    if name:
        user.name = name
    if role:
        user.role = role
    db.session.commit()
    return user


def set_password(user: User, password: str) -> User:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    user.hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    db.session.commit()
    return user
