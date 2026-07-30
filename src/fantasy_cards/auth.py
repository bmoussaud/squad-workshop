"""Single-tenant Entra OIDC and signed browser sessions."""

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from hashlib import sha256
from http.cookies import SimpleCookie
import os
import re
from typing import Any, Protocol
from urllib.parse import urlsplit

from authlib.integrations.starlette_client import OAuth
from authlib.integrations.starlette_client.apps import StarletteOAuth2App
from authlib.oauth2.rfc6749.errors import OAuth2Error
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from joserfc.errors import JoseError
from starlette.requests import Request
from starlette.responses import Response

from fantasy_cards.domain import is_valid_owner_subject


_GUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_SESSION_COOKIE = "fantasy-cards-session"
_SECURE_SESSION_COOKIE = "__Host-fantasy-cards-session"
_SESSION_SALT = "fantasy-cards-session-v1"


class AuthenticationConfigurationError(ValueError):
    """A safe authentication configuration error."""


@dataclass(frozen=True, slots=True)
class AuthSettings:
    tenant_id: str
    client_id: str
    client_secret: str
    application_base_url: str
    session_secret_current: str
    session_secret_previous: str | None = None
    session_max_age_seconds: int = 8 * 60 * 60

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> "AuthSettings":
        values = os.environ if environment is None else environment
        try:
            max_age = int(
                values.get("FANTASY_CARD_SESSION_MAX_AGE_SECONDS", str(8 * 60 * 60))
            )
        except ValueError:
            raise AuthenticationConfigurationError(
                "Session lifetime must be an integer."
            ) from None
        required = {
            "tenant_id": values.get("AZURE_TENANT_ID", ""),
            "client_id": values.get("FANTASY_CARD_OIDC_CLIENT_ID", ""),
            "client_secret": values.get("FANTASY_CARD_OIDC_CLIENT_SECRET", ""),
            "application_base_url": values.get("FANTASY_CARD_APPLICATION_BASE_URL", ""),
            "session_secret_current": values.get(
                "FANTASY_CARD_SESSION_SECRET_CURRENT", ""
            ),
        }
        if any(not value.strip() for value in required.values()):
            raise AuthenticationConfigurationError(
                "Authentication configuration is incomplete."
            )
        return cls(
            **required,
            session_secret_previous=values.get(
                "FANTASY_CARD_SESSION_SECRET_PREVIOUS"
            ),
            session_max_age_seconds=max_age,
        ).validated()

    def validated(self) -> "AuthSettings":
        if not _GUID_PATTERN.fullmatch(self.tenant_id):
            raise AuthenticationConfigurationError("Tenant identifier is invalid.")
        if not _GUID_PATTERN.fullmatch(self.client_id):
            raise AuthenticationConfigurationError("Client identifier is invalid.")
        parsed_url = urlsplit(self.application_base_url)
        is_localhost = parsed_url.hostname in {"localhost", "127.0.0.1"}
        if (
            parsed_url.scheme not in ({"http", "https"} if is_localhost else {"https"})
            or parsed_url.username is not None
            or parsed_url.password is not None
            or not parsed_url.hostname
            or parsed_url.path not in ("", "/")
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise AuthenticationConfigurationError(
                "Application base URL is invalid."
            )
        if len(self.client_secret) < 16:
            raise AuthenticationConfigurationError(
                "OIDC client credential is invalid."
            )
        if len(self.session_secret_current) < 32 or (
            self.session_secret_previous is not None
            and len(self.session_secret_previous) < 32
        ):
            raise AuthenticationConfigurationError(
                "Session signing configuration is invalid."
            )
        if not 300 <= self.session_max_age_seconds <= 24 * 60 * 60:
            raise AuthenticationConfigurationError(
                "Session lifetime must be between 300 and 86400 seconds."
            )
        return self

    @property
    def issuer(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def metadata_url(self) -> str:
        return f"{self.issuer}/.well-known/openid-configuration"

    @property
    def callback_url(self) -> str:
        return f"{self.application_base_url.rstrip('/')}/auth/callback"

    @property
    def secure_cookie(self) -> bool:
        return urlsplit(self.application_base_url).scheme == "https"

    @property
    def session_cookie_name(self) -> str:
        return _SECURE_SESSION_COOKIE if self.secure_cookie else _SESSION_COOKIE


class OidcClient(Protocol):
    async def authorize_redirect(self, request: Request) -> Response: ...

    async def authenticate(self, request: Request) -> str: ...


class AuthlibOidcClient:
    def __init__(self, settings: AuthSettings) -> None:
        self._settings = settings
        oauth = OAuth()
        client = oauth.register(
            name="entra",
            client_id=settings.client_id,
            client_secret=settings.client_secret,
            server_metadata_url=settings.metadata_url,
            client_kwargs={
                "scope": "openid",
                "code_challenge_method": "S256",
            },
        )
        if client is None:
            raise AuthenticationConfigurationError(
                "Authentication client could not be configured."
            )
        self._client: StarletteOAuth2App = client

    async def authorize_redirect(self, request: Request) -> Response:
        return await self._client.authorize_redirect(
            request,
            self._settings.callback_url,
            code_challenge_method="S256",
        )

    async def authenticate(self, request: Request) -> str:
        token = await self._client.authorize_access_token(
            request,
            claims_options={
                "iss": {"essential": True, "value": self._settings.issuer},
                "sub": {"essential": True},
            },
        )
        claims = token.get("userinfo")
        if not isinstance(claims, Mapping):
            raise OAuth2Error(
                "invalid_token", description="The identity token is unavailable."
            )
        subject = claims.get("sub")
        if not is_valid_owner_subject(subject):
            raise OAuth2Error(
                "invalid_token", description="The identity subject is unavailable."
            )
        return str(subject)


class SignedSessionMiddleware:
    def __init__(self, app: Any, settings: AuthSettings) -> None:
        self.app = app
        self._settings = settings
        secrets = [
            settings.session_secret_current,
            *(
                [settings.session_secret_previous]
                if settings.session_secret_previous
                else []
            ),
        ]
        self._serializers = [
            URLSafeTimedSerializer(
                secret,
                salt=_SESSION_SALT,
                signer_kwargs={"digest_method": sha256},
            )
            for secret in secrets
        ]

    async def __call__(
        self, scope: dict[str, Any], receive: Any, send: Any
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        session = self._load_session(scope)
        scope["session"] = session

        async def session_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if session:
                    value = self._serializers[0].dumps(dict(session))
                    cookie = (
                        f"{self._settings.session_cookie_name}={value}; Path=/; "
                        f"Max-Age={self._settings.session_max_age_seconds}; "
                        "HttpOnly; SameSite=Lax"
                    )
                    if self._settings.secure_cookie:
                        cookie += "; Secure"
                else:
                    cookie = (
                        f"{self._settings.session_cookie_name}=; Path=/; Max-Age=0; "
                        "HttpOnly; SameSite=Lax"
                    )
                    if self._settings.secure_cookie:
                        cookie += "; Secure"
                headers.append((b"set-cookie", cookie.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, session_send)

    def _load_session(self, scope: Mapping[str, Any]) -> MutableMapping[str, Any]:
        headers = {
            key.lower(): value for key, value in scope.get("headers", [])
        }
        raw_cookie = headers.get(b"cookie")
        if raw_cookie is None:
            return {}
        parsed = SimpleCookie()
        try:
            parsed.load(raw_cookie.decode("latin-1"))
        except UnicodeDecodeError:
            return {}
        morsel = parsed.get(self._settings.session_cookie_name)
        if morsel is None:
            return {}
        for serializer in self._serializers:
            try:
                value = serializer.loads(
                    morsel.value,
                    max_age=self._settings.session_max_age_seconds,
                )
            except (BadSignature, SignatureExpired):
                continue
            if isinstance(value, dict):
                return value
        return {}


AUTH_FAILURES = (OAuth2Error, JoseError)
