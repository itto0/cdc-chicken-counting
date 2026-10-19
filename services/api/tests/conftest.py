import pytest
from services.api.src.api.auth import get_current_user, UserDTO
from services.api.src.main import app


@pytest.fixture(autouse=True)
def default_auth_override(request):
    """
    Automatically bypass auth for existing functional tests (lines, counts, alarms, etc.)
    while preserving real auth evaluation for dedicated auth and RBAC test suites.
    """
    node_id = request.node.nodeid
    if any(auth_file in node_id for auth_file in ("test_auth_api", "test_rbac", "test_seed_users")):
        app.dependency_overrides.pop(get_current_user, None)
        yield
        app.dependency_overrides.pop(get_current_user, None)
        return

    app.dependency_overrides[get_current_user] = lambda: UserDTO(
        id=1, username="admin", role="admin", is_active=True
    )
    yield
    app.dependency_overrides.pop(get_current_user, None)
