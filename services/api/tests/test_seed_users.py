import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from services.api.src.db.models import Base, User
from services.api.src.services.auth import verify_password
from services.api.src.main import init_db


def test_init_db_seeds_default_admin_and_operator():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Run database initialization on clean memory engine
    init_db(target_engine=engine)

    with Session(engine) as session:
        admin = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
        assert admin is not None
        assert admin.role.lower() == "admin"
        assert admin.is_active is True
        assert verify_password("admin123", admin.password_hash) is True

        operator = session.execute(select(User).where(User.username == "operator")).scalar_one_or_none()
        assert operator is not None
        assert operator.role.lower() == "operator"
        assert operator.is_active is True
        assert verify_password("operator123", operator.password_hash) is True


def test_init_db_idempotent():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)
    # Running again should not fail or duplicate users
    init_db(target_engine=engine)

    with Session(engine) as session:
        users = session.execute(select(User)).scalars().all()
        admin_count = sum(1 for u in users if u.username == "admin")
        op_count = sum(1 for u in users if u.username == "operator")
        assert admin_count == 1
        assert op_count == 1
