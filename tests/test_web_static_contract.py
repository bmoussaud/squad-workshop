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

    def test_css_centralizes_green_background_palette(self) -> None:
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

        self.assertIn("--paper: #e4f1df;", css)
        self.assertIn("--surface: #f7fcf4;", css)
        self.assertIn("--muted: #556052;", css)
        self.assertIn("--coral: #9e3a31;", css)
        self.assertIn("--gold: #7a5d16;", css)
        self.assertIn("--line: #697564;", css)
        self.assertIn("background: var(--paper);", css)
        self.assertIn("background-color: var(--paper);", css)
        self.assertIn("background: rgba(228, 241, 223, 0.96);", css)
        self.assertIn("background: #d8ecd2;", css)
        outdated_paper = "#" + "f7" + "f3" + "e8"
        outdated_masthead = "rgba(" + ", ".join(("247", "243", "232"))
        self.assertNotIn(outdated_paper, css)
        self.assertNotIn(outdated_masthead, css)

    def test_green_palette_preserves_text_and_ui_contrast(self) -> None:
        backgrounds = {
            "paper": "#e4f1df",
            "surface": "#f7fcf4",
            "result": "#d8ecd2",
        }
        normal_text = {
            "ink": "#17251d",
            "muted": "#556052",
            "coral": "#9e3a31",
            "gold": "#7a5d16",
        }
        ui_components = {
            "line": "#697564",
            "focus": "#0b6c88",
            "forest": "#24513a",
            "forest-deep": "#173a29",
        }

        for background_name, background in backgrounds.items():
            for foreground_name, foreground in normal_text.items():
                with self.subTest(
                    background=background_name, foreground=foreground_name
                ):
                    self.assertGreaterEqual(
                        _contrast_ratio(foreground, background), 4.5
                    )
            for foreground_name, foreground in ui_components.items():
                with self.subTest(
                    background=background_name, foreground=foreground_name
                ):
                    self.assertGreaterEqual(
                        _contrast_ratio(foreground, background), 3.0
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
        self.assertNotIn("window.location", script)


if __name__ == "__main__":
    unittest.main()