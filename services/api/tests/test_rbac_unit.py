import pytest
from fastapi import HTTPException
from services.api.src.api.auth import UserDTO, require_role


def test_require_role_matching_role():
    checker = require_role(["admin", "manager"])
    user = UserDTO(id=1, username="alice", role="admin", is_active=True)
    res = checker(user)
    assert res == user


def test_require_role_case_insensitive():
    checker = require_role(["ADMIN"])
    user = UserDTO(id=1, username="alice", role="admin", is_active=True)
    res = checker(user)
    assert res == user

    checker_lower = require_role(["admin"])
    user_upper = UserDTO(id=1, username="alice", role="ADMIN", is_active=True)
    res2 = checker_lower(user_upper)
    assert res2 == user_upper


def test_require_role_forbidden():
    checker = require_role(["admin"])
    user = UserDTO(id=2, username="bob", role="operator", is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403
    assert "Required role: admin" in exc_info.value.detail


def test_require_role_forbidden_multiple_roles():
    checker = require_role(["admin", "supervisor"])
    user = UserDTO(id=2, username="bob", role="operator", is_active=True)
    with pytest.raises(HTTPException) as exc_info:
        checker(user)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Operation not permitted. Required role: admin, supervisor"


def test_require_role_strips_whitespace():
    checker = require_role([" admin "])
    user = UserDTO(id=3, username="carol", role=" admin ", is_active=True)
    res = checker(user)
    assert res == user
