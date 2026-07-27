import base64
import unittest
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

from fantasy_cards.adapters import FoundryImageGenerator, build_card_prompt


def valid_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return output.getvalue()


class CardPromptContractTests(unittest.TestCase):
    def test_build_card_prompt_states_the_card_layout_contract(self) -> None:
        prompt = build_card_prompt("Ember Sentinel", "A knight made of living flame")
        repeated = build_card_prompt("Ember Sentinel", "A knight made of living flame")

        self.assertEqual(prompt, repeated)
        self.assertIn("Ember Sentinel", prompt)
        self.assertIn("A knight made of living flame", prompt)
        lowered = prompt.lower()
        self.assertIn("border", lowered)
        self.assertIn("frame", lowered)
        self.assertIn("title banner", lowered)
        self.assertIn("top", lowered)
        self.assertIn("central illustration", lowered)
        self.assertIn("stats/description area", lowered)
        self.assertIn("bottom", lowered)

    def test_foundry_sends_card_prompt_and_portrait_size_to_provider(self) -> None:
        png = valid_png()
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(png).decode())]
        )
        generator = FoundryImageGenerator(
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=Mock(return_value=client),
        )

        image = generator.generate("Ember Sentinel", "A knight made of living flame")

        self.assertEqual(image.content, png)
        client.images.generate.assert_called_once_with(
            model="image-deployment",
            prompt=build_card_prompt(
                "Ember Sentinel", "A knight made of living flame"
            ),
            n=1,
            size="1024x1536",
        )


if __name__ == "__main__":
    unittest.main()
