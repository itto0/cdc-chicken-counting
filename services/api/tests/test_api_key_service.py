from services.api.src.services.auth import generate_api_key, hash_api_key
from services.api.src.db.models import ApiKey


def test_generate_api_key_format():
    raw_key, key_hash, prefix = generate_api_key()
    assert raw_key.startswith("cdc_live_")
    assert len(raw_key) == 73
    assert len(key_hash) == 64
    assert prefix == raw_key[:16]
    assert hash_api_key(raw_key) == key_hash


def test_generate_api_key_uniqueness():
    k1, h1, p1 = generate_api_key()
    k2, h2, p2 = generate_api_key()
    assert k1 != k2
    assert h1 != h2


def test_hash_api_key_deterministic():
    raw_key = "cdc_live_" + "a" * 64
    hash1 = hash_api_key(raw_key)
    hash2 = hash_api_key(raw_key)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_api_key_model_attributes():
    raw_key, key_hash, prefix = generate_api_key()
    key_obj = ApiKey(
        name="Line 1 Counter",
        key_hash=key_hash,
        prefix=prefix,
        role="OPERATOR",
    )
    assert key_obj.name == "Line 1 Counter"
    assert key_obj.key_hash == key_hash
    assert key_obj.prefix == prefix
    assert key_obj.role == "OPERATOR"
    assert key_obj.is_active is True
    assert key_obj.last_used_at is None
    assert "Line 1 Counter" in repr(key_obj)
    assert prefix in repr(key_obj)


def test_api_key_db_lifecycle_and_unique_constraint():
    from sqlalchemy import create_engine, select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session
    from services.api.src.db.models import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        raw_key, key_hash, prefix = generate_api_key()
        api_key = ApiKey(
            name="Edge Device 1",
            key_hash=key_hash,
            prefix=prefix,
        )
        session.add(api_key)
        session.commit()

        # Query back
        stmt = select(ApiKey).where(ApiKey.key_hash == key_hash)
        fetched = session.scalars(stmt).first()
        assert fetched is not None
        assert fetched.id is not None
        assert fetched.name == "Edge Device 1"
        assert fetched.role == "OPERATOR"
        assert fetched.is_active is True
        assert fetched.created_at is not None
        assert fetched.last_used_at is None

        # Duplicate key_hash should raise IntegrityError
        duplicate_key = ApiKey(
            name="Duplicate Device",
            key_hash=key_hash,
            prefix=prefix,
        )
        session.add(duplicate_key)
        import pytest
        with pytest.raises(IntegrityError):
            session.commit()

