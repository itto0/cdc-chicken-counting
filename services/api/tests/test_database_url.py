from services.api.src.db.session import resolve_database_url


def test_resolve_sqlite_url():
    url = "sqlite:///custom_path.db"
    assert resolve_database_url(url) == url


def test_resolve_render_postgres_prefix():
    raw_render_url = "postgres://usr:pwd@dpg-xxx-a.oregon-postgres.render.com/chicken_counting"
    resolved = resolve_database_url(raw_render_url)
    assert resolved.startswith("postgresql+psycopg://") or resolved.startswith("postgresql+psycopg2://")
    assert "dpg-xxx-a.oregon-postgres.render.com" in resolved
    assert not resolved.startswith("postgres://")


def test_resolve_postgresql_prefix():
    url = "postgresql://usr:pwd@localhost:5432/chicken_counting"
    resolved = resolve_database_url(url)
    assert resolved.startswith("postgresql+psycopg://") or resolved.startswith("postgresql+psycopg2://")
