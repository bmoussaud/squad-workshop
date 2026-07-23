import os
import re
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


class WebStaticContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output_directory = TemporaryDirectory()
        self.addCleanup(self.output_directory.cleanup)
        self.environment = {
            "FANTASY_CARD_IMAGE_GENERATOR": "in-memory",
            "FANTASY_CARD_ARTIFACT_STORE": "filesystem",
            "FANTASY_CARD_OUTPUT_DIR": self.output_directory.name,
        }

    def test_html_exposes_landmarks_constraints_and_repository_owned_assets(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
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

    def test_javascript_is_progressive_enhancement_not_required_navigation(self) -> None:
        from fastapi.testclient import TestClient
        from fantasy_cards.web import create_app

        with patch.dict(os.environ, self.environment, clear=True):
            with TestClient(create_app()) as client:
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