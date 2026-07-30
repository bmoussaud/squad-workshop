import os
import re
from hashlib import sha256
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from itsdangerous import URLSafeTimedSerializer


def _contrast_ratio(foreground: str, background: str) -> float:
    def luminance(hex_color: str) -> float:
        channels = (
            int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)
        )
        linear = [
            value / 12.92
            if value <= 0.03928
            else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


class WebStaticContractTests(unittest.TestCase):
    session_secret = "s" * 48

    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "in-memory",
            "FANTASY_CARD_ARTIFACT_STORE": "filesystem",
            "FANTASY_CARD_OUTPUT_DIR": self.output_directory.name,
            "AZURE_TENANT_ID": "11111111-1111-4111-8111-111111111111",
            "FANTASY_CARD_OIDC_CLIENT_ID": "22222222-2222-4222-8222-222222222222",
            "FANTASY_CARD_OIDC_CLIENT_SECRET": "test-client-credential",
            "FANTASY_CARD_APPLICATION_BASE_URL": "http://localhost:8000",
            "FANTASY_CARD_SESSION_SECRET_CURRENT": self.session_secret,
        }

    def authenticate(self, client: object) -> None:
        serializer = URLSafeTimedSerializer(
            self.session_secret,
            salt="fantasy-cards-session-v1",
            signer_kwargs={"digest_method": sha256},
        )
        client.cookies.set(
            "fantasy-cards-session",
            serializer.dumps(
                {"owner_subject": "owner-a", "csrf_token": "csrf-token"}
            ),
        )

    def test_html_exposes_landmarks_constraints_and_repository_owned_assets(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client)
                response = client.get("/")

        html = response.text
        self.assertEqual(response.status_code, 200)
        for landmark in ("main", "form"):
            self.assertRegex(html, rf"<{landmark}(?:\s|>)")
        self.assertRegex(html, r'<input[^>]+id="title"[^>]+maxlength="80"')
        self.assertRegex(
            html, r'<textarea[^>]+id="description"[^>]+maxlength="1000"'
        )
        self.assertRegex(html, r'<button[^>]+type="submit"[^>]*>')
        self.assertRegex(html, r'<[^>]+(?:id|role)="[^"]*result[^"]*"')
        self.assertNotRegex(html, r'https?://[^"\s]+\.(?:js|css)')

        asset_paths = re.findall(r'(?:href|src)="(/static/[^"]+)"', html)
        self.assertTrue(asset_paths)
        for asset_path in asset_paths:
            with self.subTest(asset=asset_path):
                asset = client.get(asset_path)
                self.assertEqual(asset.status_code, 200)
                self.assertTrue(asset.content)

    def test_css_has_focus_reduced_motion_and_responsive_overflow_guards(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client)
                html = client.get("/").text
                stylesheet_path = re.search(
                    r'href="(?P<path>/static/[^"]+\.css)"', html
                ).group("path")
                css = client.get(stylesheet_path).text

        compact = re.sub(r"\s+", " ", css.lower())
        self.assertIn(":focus-visible", compact)
        self.assertIn("prefers-reduced-motion: reduce", compact)
        self.assertIn("@media", compact)
        self.assertTrue(
            re.search(r"max-width\s*:\s*100%", compact)
            or re.search(r"width\s*:\s*min\(100%", compact)
        )
        self.assertIn("minmax(0, 1fr)", compact)
        self.assertRegex(compact, r"min-width\s*:\s*0")
        self.assertRegex(compact, r"@media\s*\(max-width:")
        self.assertRegex(compact, r"min-height\s*:\s*(?:44px|48px|2\.75rem|3rem)")

    def test_css_uses_semantic_surface_and_interaction_tokens(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client)
                html = client.get("/").text
                stylesheet_path = re.search(
                    r'href="(?P<path>/static/[^"]+\.css)"', html
                ).group("path")
                css = client.get(stylesheet_path).text.lower()

        for token in (
            "--canvas:",
            "--surface:",
            "--surface-subtle:",
            "--border:",
            "--accent:",
            "--accent-strong:",
            "--focus:",
            "--danger:",
            "--success:",
        ):
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertIn("background: linear-gradient(", css)
        self.assertNotIn("data:image/svg+xml", css)

    def test_visual_tokens_preserve_text_and_ui_contrast(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client)
                html = client.get("/").text
                stylesheet_path = re.search(
                    r'href="(?P<path>/static/[^"]+\.css)"', html
                ).group("path")
                stylesheet = client.get(stylesheet_path)

        self.assertEqual(stylesheet.status_code, 200)
        root = re.search(
            r":root\s*\{(?P<declarations>.*?)\}", stylesheet.text, re.DOTALL
        )
        self.assertIsNotNone(root, "served stylesheet must declare :root design tokens")
        declared_tokens = dict(
            re.findall(
                r"(?m)^\s*(--[a-z-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;",
                root.group("declarations"),
            )
        )
        expected_tokens = {
            "--ink": "#172033",
            "--muted": "#4b5565",
            "--canvas": "#f7f9fc",
            "--surface": "#ffffff",
            "--surface-subtle": "#f1f5f9",
            "--accent": "#2f5be7",
            "--accent-strong": "#2448b8",
            "--accent-subtle": "#e8efff",
            "--success": "#157347",
            "--danger": "#b42318",
            "--focus": "#0b63ce",
        }
        for token, expected_value in expected_tokens.items():
            with self.subTest(token=token):
                self.assertEqual(declared_tokens.get(token), expected_value)

        result_gradient = re.search(
            r"background\s*:\s*linear-gradient\(\s*145deg\s*,\s*"
            r"var\((--[a-z-]+)\)\s+0%\s*,\s*"
            r"var\((--[a-z-]+)\)\s+100%\s*\)",
            stylesheet.text,
        )
        self.assertIsNotNone(
            result_gradient, "result surface must retain its token-based gradient"
        )
        self.assertEqual(
            result_gradient.groups(), ("--surface", "--accent-subtle")
        )
        _, result_surface_end = result_gradient.groups()

        text_pairs = (
            ("--ink", "--canvas"),
            ("--ink", "--surface"),
            ("--ink", result_surface_end),
            ("--muted", "--canvas"),
            ("--muted", "--surface"),
            ("--muted", "--surface-subtle"),
            ("--muted", result_surface_end),
            ("--accent-strong", "--surface"),
            ("--success", result_surface_end),
            ("--danger", "--surface"),
        )
        ui_pairs = (
            ("--accent", "--surface"),
            ("--accent", result_surface_end),
            ("--focus", "--surface"),
            ("--focus", result_surface_end),
        )
        for foreground, background in text_pairs:
            with self.subTest(foreground=foreground, background=background):
                self.assertGreaterEqual(
                    _contrast_ratio(
                        declared_tokens[foreground], declared_tokens[background]
                    ),
                    4.5,
                )
        for foreground, background in ui_pairs:
            with self.subTest(foreground=foreground, background=background):
                self.assertGreaterEqual(
                    _contrast_ratio(
                        declared_tokens[foreground], declared_tokens[background]
                    ),
                    3.0,
                )

    def test_javascript_is_progressive_enhancement_not_required_navigation(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
                self.authenticate(client)
                html = client.get("/").text
                script_path = re.search(
                    r'src="(?P<path>/static/[^"]+\.js)"', html
                ).group("path")
                script = client.get(script_path).text.lower()

        self.assertIn("submit", script)
        self.assertIn("fetch(", script)
        self.assertIn("disabled", script)
        self.assertTrue("aria-busy" in script or "aria-live" in html.lower())
        self.assertIn("prefers-reduced-motion: reduce", script)
        self.assertNotIn("window.location", script)


if __name__ == "__main__":
    unittest.main()