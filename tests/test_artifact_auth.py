from hashlib import sha256
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from itsdangerous import URLSafeTimedSerializer

from fantasy_cards.auth import AuthSettings, AuthlibOidcClient
from fantasy_cards.config import build_web_application
from fantasy_cards.web import create_app


class FakeOidcClient:
    def __init__(self, subject: str = "owner-a") -> None:
        self.subject = subject

    async def authorize_redirect(self, request: object) -> RedirectResponse:
        request.session["_state_entra_test"] = {"data": {"nonce": "nonce"}}
        return RedirectResponse("https://login.microsoftonline.com/authorize")

    async def authenticate(self, request: object) -> str:
        return self.subject


class ArtifactAuthenticationTests(unittest.TestCase):
    tenant_id = "11111111-1111-4111-8111-111111111111"
    client_id = "22222222-2222-4222-8222-222222222222"
    current_secret = "c" * 48
    previous_secret = "p" * 48
    csrf_token = "csrf-token"

    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "in-memory",
            "FANTASY_CARD_ARTIFACT_STORE": "filesystem",
            "FANTASY_CARD_OUTPUT_DIR": self.output_directory.name,
            "FANTASY_CARD_MAX_GENERATION_CONCURRENCY": "1",
            "FANTASY_CARD_RATE_LIMIT_ATTEMPTS": "10",
            "FANTASY_CARD_RATE_LIMIT_WINDOW_SECONDS": "600",
            "AZURE_TENANT_ID": self.tenant_id,
            "FANTASY_CARD_OIDC_CLIENT_ID": self.client_id,
            "FANTASY_CARD_OIDC_CLIENT_SECRET": "test-client-credential",
            "FANTASY_CARD_APPLICATION_BASE_URL": "http://localhost:8000",
            "FANTASY_CARD_SESSION_SECRET_CURRENT": self.current_secret,
            "FANTASY_CARD_SESSION_SECRET_PREVIOUS": self.previous_secret,
            "FANTASY_CARD_SESSION_MAX_AGE_SECONDS": "300",
            "USERPROFILE": str(Path.home()),
        }

    def serializer(self, secret: str) -> URLSafeTimedSerializer:
        return URLSafeTimedSerializer(
            secret,
            salt="fantasy-cards-session-v1",
            signer_kwargs={"digest_method": sha256},
        )

    def authenticate(
        self, client: TestClient, owner_subject: str, secret: str | None = None
    ) -> None:
        client.cookies.clear()
        client.cookies.set(
            "fantasy-cards-session",
            self.serializer(secret or self.current_secret).dumps(
                {
                    "owner_subject": owner_subject,
                    "csrf_token": self.csrf_token,
                }
            ),
        )
        client.headers["X-CSRF-Token"] = self.csrf_token

    def test_owner_can_read_but_non_owner_and_ownerless_artifacts_cannot(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            application = build_web_application()
            with TestClient(create_app(application=application)) as client:
                self.authenticate(client, "owner-a")
                generated = client.post(
                    "/api/generations",
                    json={"title": "Card", "description": "Description"},
                    headers={
                        "Idempotency-Key": "same",
                        "X-CSRF-Token": self.csrf_token,
                    },
                )
                artifact = generated.json()["artifact"]
                owner_response = client.get(artifact["url"])

                self.authenticate(client, "owner-b")
                non_owner_response = client.get(artifact["url"])

                application.artifact_reader._owners.pop(artifact["artifact_id"])
                self.authenticate(client, "owner-a")
                ownerless_response = client.get(artifact["url"])

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(owner_response.headers["cache-control"], "private, no-store")
        self.assertEqual(non_owner_response.status_code, 404)
        self.assertEqual(ownerless_response.status_code, 404)
        self.assertEqual(
            non_owner_response.json()["error"]["code"],
            ownerless_response.json()["error"]["code"],
        )
        self.assertEqual(
            non_owner_response.json()["error"]["message"],
            ownerless_response.json()["error"]["message"],
        )
        self.assertNotIn(artifact["artifact_id"], non_owner_response.text)

    def test_same_idempotency_key_cannot_cross_users(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                responses = []
                for owner in ("owner-a", "owner-b"):
                    self.authenticate(client, owner)
                    responses.append(
                        client.post(
                            "/api/generations",
                            json={"title": "Card", "description": "Description"},
                            headers={
                                "Idempotency-Key": "same",
                                "X-CSRF-Token": self.csrf_token,
                            },
                        )
                    )

        self.assertEqual([response.status_code for response in responses], [200, 200])
        self.assertNotEqual(
            responses[0].json()["artifact"]["artifact_id"],
            responses[1].json()["artifact"]["artifact_id"],
        )

    def test_missing_tampered_and_expired_sessions_fail_before_artifact_read(self) -> None:
        reader = Mock()
        application = SimpleNamespace(artifact_reader=reader)
        artifact_url = "/api/artifacts/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app(application=application)) as client:
                missing = client.get(artifact_url)
                client.cookies.set("fantasy-cards-session", "tampered")
                tampered = client.get(artifact_url)
                with patch("itsdangerous.timed.time.time", return_value=1_000):
                    expired_cookie = self.serializer(self.current_secret).dumps(
                        {
                            "owner_subject": "owner-a",
                            "csrf_token": self.csrf_token,
                        }
                    )
                client.cookies.set("fantasy-cards-session", expired_cookie)
                with patch("itsdangerous.timed.time.time", return_value=1_301):
                    expired = client.get(artifact_url)

        self.assertEqual(
            [missing.status_code, tampered.status_code, expired.status_code],
            [404, 404, 404],
        )
        for response in (tampered, expired):
            self.assertEqual(
                missing.json()["error"]["code"], response.json()["error"]["code"]
            )
            self.assertEqual(
                missing.json()["error"]["message"],
                response.json()["error"]["message"],
            )
        reader.read.assert_not_called()

    def test_generation_requires_authenticated_session_and_csrf(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                anonymous = client.post(
                    "/api/generations",
                    json={"title": "Card", "description": "Description"},
                )
                self.authenticate(client, "owner-a")
                missing_csrf = client.post(
                    "/api/generations",
                    json={"title": "Card", "description": "Description"},
                    headers={"X-CSRF-Token": ""},
                )

        self.assertEqual(anonymous.status_code, 401)
        self.assertEqual(missing_csrf.status_code, 401)

    def test_oidc_callback_rotates_session_and_sets_secure_cookie(self) -> None:
        settings = AuthSettings.from_environment(
            {
                **self.environment,
                "FANTASY_CARD_APPLICATION_BASE_URL": "https://cards.example",
            }
        )
        oidc_client = FakeOidcClient()
        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(
                create_app(auth_settings=settings, oidc_client=oidc_client),
                base_url="https://cards.example",
            ) as client:
                login = client.get("/auth/login", follow_redirects=False)
                callback = client.get("/auth/callback", follow_redirects=False)
                home = client.get("/")

        self.assertEqual(login.status_code, 307)
        self.assertEqual(
            login.headers["location"],
            "https://login.microsoftonline.com/authorize",
        )
        self.assertEqual(callback.status_code, 302)
        self.assertEqual(home.status_code, 200)
        cookie = callback.headers["set-cookie"]
        self.assertIn("__Host-fantasy-cards-session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Secure", cookie)
        self.assertNotIn("_state_entra_test", self.serializer(self.current_secret).loads(
            client.cookies["__Host-fantasy-cards-session"]
        ))

    def test_previous_session_key_is_accepted_and_rotated(self) -> None:
        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client, "owner-a", self.previous_secret)
                response = client.get("/")

        self.assertEqual(response.status_code, 200)
        cookie_header = response.headers["set-cookie"]
        rotated = cookie_header.split("fantasy-cards-session=", 1)[1].split(";", 1)[0]
        payload = self.serializer(self.current_secret).loads(rotated)
        self.assertEqual(payload["owner_subject"], "owner-a")

    def test_authlib_is_single_tenant_and_enforces_pkce(self) -> None:
        settings = AuthSettings.from_environment(self.environment)
        registered_client = Mock()
        with patch(
            "fantasy_cards.auth.OAuth.register", return_value=registered_client
        ) as register:
            AuthlibOidcClient(settings)

        arguments = register.call_args.kwargs
        self.assertEqual(arguments["server_metadata_url"], settings.metadata_url)
        self.assertIn(self.tenant_id, arguments["server_metadata_url"])
        self.assertNotIn("/common/", arguments["server_metadata_url"])
        self.assertEqual(
            arguments["client_kwargs"]["code_challenge_method"], "S256"
        )


if __name__ == "__main__":
    unittest.main()
