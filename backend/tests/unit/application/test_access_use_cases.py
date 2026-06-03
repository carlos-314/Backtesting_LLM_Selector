"""Tests de los casos de uso del contexto Acceso (F2 §8.1, ADR-0006)."""
import uuid

import pytest

from app.application.access.authenticate_with_google import AuthenticateWithGoogle
from app.application.access.bootstrap_admin import BootstrapInitialAdmin
from app.application.access.get_user_by_access_token import GetUserByAccessToken
from app.application.access.register_user import RegisterUser
from app.domain.access.exceptions import (
    EmailAlreadyRegisteredError,
    GoogleUnreachableError,
    InvalidGoogleTokenError,
    NotPermittedError,
    UserNotAuthorizedError,
)
from app.domain.access.google_identity import GoogleIdentity
from app.domain.access.role import Role
from app.domain.access.user import User
from app.infrastructure.identity.security import create_access_token

from tests.unit.application.fakes.fake_google_verifier import FakeGoogleIdentityVerifier
from tests.unit.application.fakes.fake_user_repo import FakeUserRepository


def _user(role: Role = Role.ANALYST, **kw) -> User:
    return User(
        id=kw.pop("id", uuid.uuid4()),
        email=kw.pop("email", "u@x.com"),
        role=role,
        is_active=kw.pop("is_active", True),
        full_name=kw.pop("full_name", None),
        google_id=kw.pop("google_id", None),
    )


# ═══════════════════════ authenticate_with_google ═══════════════════════


async def test_authenticate_user_ya_vinculado_devuelve_user() -> None:
    repo = FakeUserRepository()
    user = _user(google_id="g1", email="known@x.com")
    repo.seed(user)
    verifier = FakeGoogleIdentityVerifier()
    verifier.set_identity("tok", GoogleIdentity(google_id="g1", email="known@x.com"))

    auth = AuthenticateWithGoogle(verifier, repo)
    got = await auth("tok")
    assert got.id == user.id
    assert got.email == "known@x.com"


async def test_authenticate_user_pre_aprobado_vincula_google_id() -> None:
    """ADR-0006: row con google_id=NULL → primer login completa."""
    repo = FakeUserRepository()
    pre_alta = _user(google_id=None, email="pre@x.com", role=Role.ANALYST)
    repo.seed(pre_alta)
    verifier = FakeGoogleIdentityVerifier()
    verifier.set_identity("tok", GoogleIdentity(google_id="g_fresh", email="pre@x.com"))

    auth = AuthenticateWithGoogle(verifier, repo)
    got = await auth("tok")
    assert got.google_id == "g_fresh"
    # Tras vincular, find_by_google_id debe encontrarlo
    found = await repo.find_by_google_id("g_fresh")
    assert found is not None and found.id == pre_alta.id


async def test_authenticate_email_no_autorizado_lanza_unauthorized() -> None:
    """No estás en la lista → 403."""
    repo = FakeUserRepository()
    verifier = FakeGoogleIdentityVerifier()
    verifier.set_identity("tok", GoogleIdentity(google_id="gX", email="random@x.com"))

    auth = AuthenticateWithGoogle(verifier, repo)
    with pytest.raises(UserNotAuthorizedError, match="not on the access list"):
        await auth("tok")


async def test_authenticate_email_vinculado_a_otra_cuenta_google_lanza_unauthorized() -> None:
    """Caso defensivo: email previamente vinculado, ahora viene otra google_id."""
    repo = FakeUserRepository()
    repo.seed(_user(google_id="g_original", email="shared@x.com"))
    verifier = FakeGoogleIdentityVerifier()
    verifier.set_identity("tok", GoogleIdentity(google_id="g_new", email="shared@x.com"))

    auth = AuthenticateWithGoogle(verifier, repo)
    with pytest.raises(UserNotAuthorizedError, match="different Google account"):
        await auth("tok")


async def test_authenticate_user_inactivo_lanza_unauthorized() -> None:
    repo = FakeUserRepository()
    repo.seed(_user(google_id="g1", email="inactive@x.com", is_active=False))
    verifier = FakeGoogleIdentityVerifier()
    verifier.set_identity("tok", GoogleIdentity(google_id="g1", email="inactive@x.com"))

    auth = AuthenticateWithGoogle(verifier, repo)
    with pytest.raises(UserNotAuthorizedError, match="inactive"):
        await auth("tok")


async def test_authenticate_token_invalido_propaga_invalid_google_token() -> None:
    repo = FakeUserRepository()
    verifier = FakeGoogleIdentityVerifier()
    auth = AuthenticateWithGoogle(verifier, repo)
    with pytest.raises(InvalidGoogleTokenError):
        await auth("bogus")


async def test_authenticate_google_caido_propaga_unreachable() -> None:
    repo = FakeUserRepository()
    verifier = FakeGoogleIdentityVerifier(fail_unreachable=True)
    auth = AuthenticateWithGoogle(verifier, repo)
    with pytest.raises(GoogleUnreachableError):
        await auth("anything")


# ═══════════════════════ register_user ═══════════════════════


async def test_register_user_por_admin_crea_pre_alta() -> None:
    repo = FakeUserRepository()
    admin = _user(role=Role.ADMIN)
    use_case = RegisterUser(repo)
    new = await use_case(actor=admin, email="new@x.com", role=Role.VIEWER)
    assert new.email == "new@x.com"
    assert new.role == Role.VIEWER
    assert new.google_id is None  # pre-alta sin vincular


async def test_register_user_por_analyst_lanza_not_permitted() -> None:
    repo = FakeUserRepository()
    analyst = _user(role=Role.ANALYST)
    use_case = RegisterUser(repo)
    with pytest.raises(NotPermittedError):
        await use_case(actor=analyst, email="new@x.com", role=Role.VIEWER)


async def test_register_user_por_viewer_lanza_not_permitted() -> None:
    repo = FakeUserRepository()
    viewer = _user(role=Role.VIEWER)
    use_case = RegisterUser(repo)
    with pytest.raises(NotPermittedError):
        await use_case(actor=viewer, email="new@x.com", role=Role.VIEWER)


async def test_register_user_admin_inactivo_lanza_not_permitted() -> None:
    repo = FakeUserRepository()
    admin = _user(role=Role.ADMIN, is_active=False)
    use_case = RegisterUser(repo)
    with pytest.raises(NotPermittedError):
        await use_case(actor=admin, email="new@x.com", role=Role.VIEWER)


async def test_register_user_email_invalido_lanza_value_error() -> None:
    repo = FakeUserRepository()
    use_case = RegisterUser(repo)
    with pytest.raises(ValueError, match="Invalid email"):
        await use_case(actor=_user(role=Role.ADMIN), email="bogus", role=Role.VIEWER)


async def test_register_user_email_repetido_lanza_already_registered() -> None:
    repo = FakeUserRepository()
    repo.seed(_user(email="dup@x.com"))
    use_case = RegisterUser(repo)
    with pytest.raises(EmailAlreadyRegisteredError):
        await use_case(actor=_user(role=Role.ADMIN), email="dup@x.com", role=Role.VIEWER)


# ═══════════════════════ bootstrap_initial_admin ═══════════════════════


async def test_bootstrap_crea_admin_si_tabla_vacia() -> None:
    repo = FakeUserRepository()
    use_case = BootstrapInitialAdmin(repo)
    created = await use_case("admin@x.com")
    assert created is not None
    assert created.role == Role.ADMIN
    assert created.email == "admin@x.com"
    assert created.google_id is None


async def test_bootstrap_idempotente_si_ya_hay_admin() -> None:
    repo = FakeUserRepository()
    repo.seed(_user(role=Role.ADMIN, email="existing_admin@x.com"))
    use_case = BootstrapInitialAdmin(repo)
    result = await use_case("admin@x.com")
    assert result is None  # no hace nada
    assert len(await repo.list_all()) == 1


async def test_bootstrap_no_crea_si_initial_admin_email_vacio() -> None:
    repo = FakeUserRepository()
    use_case = BootstrapInitialAdmin(repo)
    assert await use_case("") is None
    assert await use_case(None) is None


async def test_bootstrap_no_promueve_si_el_email_existe_con_otro_role() -> None:
    """Caso defensivo: el operador no quiere que un viewer existente se
    promueva a admin por accidente."""
    repo = FakeUserRepository()
    repo.seed(_user(role=Role.VIEWER, email="admin@x.com"))
    use_case = BootstrapInitialAdmin(repo)
    result = await use_case("admin@x.com")
    assert result is None
    # El user sigue siendo viewer
    found = await repo.find_by_email("admin@x.com")
    assert found.role == Role.VIEWER


# ═══════════════════════ get_user_by_access_token ═══════════════════════


async def test_get_user_by_token_valido_devuelve_user() -> None:
    repo = FakeUserRepository()
    user = _user(google_id="g1", email="u@x.com")
    repo.seed(user)
    token = create_access_token(user.id)

    use_case = GetUserByAccessToken(repo)
    got = await use_case(token)
    assert got is not None and got.id == user.id


async def test_get_user_by_token_invalido_devuelve_none() -> None:
    repo = FakeUserRepository()
    use_case = GetUserByAccessToken(repo)
    assert await use_case("not.a.jwt") is None


async def test_get_user_by_token_user_inexistente_devuelve_none() -> None:
    repo = FakeUserRepository()
    token = create_access_token(uuid.uuid4())  # user id que no existe
    use_case = GetUserByAccessToken(repo)
    assert await use_case(token) is None


async def test_get_user_by_token_user_inactivo_devuelve_none() -> None:
    """Defensa: token válido pero el user fue desactivado."""
    repo = FakeUserRepository()
    user = _user(google_id="g1", is_active=False)
    repo.seed(user)
    token = create_access_token(user.id)
    use_case = GetUserByAccessToken(repo)
    assert await use_case(token) is None
