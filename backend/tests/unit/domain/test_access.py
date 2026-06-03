"""Tests unitarios del dominio Acceso (F2 §5.1, §8.1)."""
import uuid

import pytest

from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User


# ─────────────────────── Role ───────────────────────


def test_role_tiene_tres_valores_cerrados() -> None:
    assert {r.value for r in Role} == {"viewer", "analyst", "admin"}


# ─────────────────────── User ───────────────────────


def _user(role: Role = Role.ANALYST, **kw) -> User:
    return User(
        id=uuid.uuid4(),
        email=kw.pop("email", "u@x.com"),
        role=role,
        is_active=kw.pop("is_active", True),
        full_name=kw.pop("full_name", "Test"),
        google_id=kw.pop("google_id", "g123"),
    )


def test_user_construye_con_role_valido() -> None:
    u = _user(role=Role.VIEWER)
    assert u.role == Role.VIEWER
    assert u.email == "u@x.com"


def test_user_email_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="email"):
        User(id=uuid.uuid4(), email="", role=Role.VIEWER)


def test_user_role_string_no_enum_lanza_typeerror() -> None:
    with pytest.raises(TypeError, match="Role"):
        User(id=uuid.uuid4(), email="u@x.com", role="viewer")  # type: ignore[arg-type]


def test_user_es_inmutable() -> None:
    u = _user()
    with pytest.raises(Exception):
        u.role = Role.ADMIN  # type: ignore[misc]


# ─────────────────── Capacidades por rol ───────────────────


def test_viewer_no_puede_crear_backtest() -> None:
    assert _user(role=Role.VIEWER).can_create_backtest() is False


def test_analyst_puede_crear_backtest() -> None:
    assert _user(role=Role.ANALYST).can_create_backtest() is True


def test_admin_puede_crear_backtest() -> None:
    """F0: 'el administrador puede todo lo que pueden los demás roles'."""
    assert _user(role=Role.ADMIN).can_create_backtest() is True


def test_usuario_inactivo_no_puede_crear_backtest_aunque_sea_analyst() -> None:
    assert _user(role=Role.ANALYST, is_active=False).can_create_backtest() is False


def test_solo_admin_puede_gestionar_usuarios() -> None:
    """ADR-0006: gestión de usuarios es capacidad exclusiva de admin."""
    assert _user(role=Role.ADMIN).can_manage_users() is True
    assert _user(role=Role.ANALYST).can_manage_users() is False
    assert _user(role=Role.VIEWER).can_manage_users() is False


def test_admin_inactivo_no_puede_gestionar_usuarios() -> None:
    assert _user(role=Role.ADMIN, is_active=False).can_manage_users() is False


def test_analyst_puede_cancelar_backtest() -> None:
    other = uuid.uuid4()
    assert _user(role=Role.ANALYST).can_cancel_backtest(created_by=other) is True


def test_viewer_no_puede_cancelar_backtest_propio() -> None:
    """F2 §6.5: viewer NO puede cancelar (ni siquiera los suyos)."""
    u = _user(role=Role.VIEWER)
    assert u.can_cancel_backtest(created_by=u.id) is False


# ─────────────────── is_linked ───────────────────


def test_user_con_google_id_None_no_esta_vinculado() -> None:
    """ADR-0006: pre-alta por admin → google_id NULL hasta primer login."""
    u = _user(google_id=None)
    assert u.is_linked() is False


def test_user_con_google_id_esta_vinculado() -> None:
    assert _user(google_id="g_real").is_linked() is True


# ─────────────────────── GoogleIdentity ───────────────────────


def test_google_identity_construye_con_google_id_y_email() -> None:
    gi = GoogleIdentity(google_id="g123", email="u@x.com", full_name="Test")
    assert gi.google_id == "g123"
    assert gi.email == "u@x.com"


def test_google_identity_google_id_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="google_id"):
        GoogleIdentity(google_id="", email="u@x.com")


def test_google_identity_email_vacio_lanza_error() -> None:
    with pytest.raises(ValueError, match="email"):
        GoogleIdentity(google_id="g123", email="")


def test_google_identity_es_inmutable() -> None:
    gi = GoogleIdentity(google_id="g", email="u@x.com")
    with pytest.raises(Exception):
        gi.email = "other@x.com"  # type: ignore[misc]
