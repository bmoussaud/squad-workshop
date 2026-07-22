import base64
from io import BytesIO
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx
import openai
from PIL import Image

from fantasy_cards.adapters import (
    FoundryImageGenerator,
    ImageGenerationError,
    create_foundry_client,
    normalize_azure_openai_endpoint,
)


def valid_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return output.getvalue()


class FoundryImageGeneratorTests(unittest.TestCase):
    @patch("openai.OpenAI")
    @patch("azure.identity.get_bearer_token_provider")
    @patch("azure.identity.DefaultAzureCredential")
    def test_client_uses_entra_timeout_and_disables_retries(
        self,
        credential_type: Mock,
        token_provider_factory: Mock,
        openai_type: Mock,
    ) -> None:
        credential = credential_type.return_value
        token_provider = token_provider_factory.return_value

        client = create_foundry_client(
            "https://example.openai.azure.com/", 45.0
        )

        self.assertIs(client, openai_type.return_value)
        credential_type.assert_called_once_with()
        token_provider_factory.assert_called_once_with(
            credential, "https://ai.azure.com/.default"
        )
        openai_type.assert_called_once_with(
            base_url="https://example.openai.azure.com/openai/v1",
            api_key=token_provider,
            timeout=45.0,
            max_retries=0,
        )

    @patch("azure.identity.get_bearer_token_provider", return_value=lambda: "token")
    @patch("azure.identity.DefaultAzureCredential")
    def test_foundry_services_request_uses_exact_images_route_and_arguments(
        self,
        credential_type: Mock,
        token_provider_factory: Mock,
    ) -> None:
        requests: list[httpx.Request] = []

        def handle_request(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return httpx.Response(
                200,
                request=request,
                json={
                    "created": 0,
                    "data": [
                        {"b64_json": base64.b64encode(valid_png()).decode()}
                    ],
                },
            )

        client = create_foundry_client(
            "https://foundry-j7hqwc4422gp4.services.ai.azure.com/openai/v1/",
            45.0,
        )
        client._client._transport = httpx.MockTransport(handle_request)

        client.images.generate(
            model="gpt-image-2",
            prompt="an original fantasy citadel",
            n=1,
            size="1024x1024",
        )

        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0].url.path, "/openai/v1/images/generations")
        request_body = json.loads(requests[0].content)
        self.assertEqual(
            request_body,
            {
                "model": "gpt-image-2",
                "prompt": "an original fantasy citadel",
                "n": 1,
                "size": "1024x1024",
            },
        )
        token_provider_factory.assert_called_once_with(
            credential_type.return_value, "https://ai.azure.com/.default"
        )

    @patch("openai.OpenAI")
    @patch("azure.identity.DefaultAzureCredential")
    def test_rejects_unsafe_endpoint_before_credential_construction(
        self, credential_type: Mock, openai_type: Mock
    ) -> None:
        invalid_endpoints = (
            "http://example.openai.azure.com",
            "https://user@example.openai.azure.com",
            "https://example.openai.azure.com?redirect=https://evil.example",
            "https://example.openai.azure.com#fragment",
            "https://example.openai.azure.com.evil.example",
            "https://openai.azure.com",
            "https://example.openai.azure.com/models",
            "https://example.openai.azure.com:444",
            "https://example.openai.azure.com ",
            "https://services.ai.azure.com/openai/v1",
            "https://example.services.ai.azure.com",
            "https://example.services.ai.azure.com/",
            "https://example.services.ai.azure.com/models",
            "https://example.services.ai.azure.com/openai/v1/models",
            "https://example.services.ai.azure.com.evil.example/openai/v1",
            "https://example.services.ai.azure.com@evil.example/openai/v1",
        )

        for endpoint in invalid_endpoints:
            with self.subTest(endpoint=endpoint):
                with self.assertRaisesRegex(ValueError, "endpoint is invalid"):
                    create_foundry_client(endpoint, 60.0)

        credential_type.assert_not_called()
        openai_type.assert_not_called()

    def test_normalizes_documented_azure_openai_resource_endpoint(self) -> None:
        for path in ("", "/", "/openai/v1", "/openai/v1/"):
            with self.subTest(path=path):
                self.assertEqual(
                    normalize_azure_openai_endpoint(
                        f"https://Fantasy-Images.openai.azure.com:443{path}"
                    ),
                    "https://fantasy-images.openai.azure.com/openai/v1",
                )

    def test_normalizes_documented_foundry_services_endpoint(self) -> None:
        expected = "https://foundry-j7hqwc4422gp4.services.ai.azure.com/openai/v1"

        for endpoint in (
            "https://foundry-j7hqwc4422gp4.services.ai.azure.com/openai/v1",
            "https://foundry-j7hqwc4422gp4.services.ai.azure.com/openai/v1/",
        ):
            with self.subTest(endpoint=endpoint):
                self.assertEqual(normalize_azure_openai_endpoint(endpoint), expected)

    def test_invalid_endpoint_message_does_not_echo_endpoint(self) -> None:
        endpoint = "https://private.example:invalid"

        with self.assertRaises(ValueError) as raised:
            normalize_azure_openai_endpoint(endpoint)

        self.assertNotIn(endpoint, str(raised.exception))

    def test_decodes_one_inline_base64_png(self) -> None:
        png = valid_png()
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(png).decode())]
        )
        factory = Mock(return_value=client)
        generator = FoundryImageGenerator(
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=factory,
        )

        image = generator.generate("an original fantasy citadel")

        self.assertEqual(image.content, png)
        self.assertEqual(image.media_type, "image/png")
        self.assertEqual(image.generator_name, "foundry")
        factory.assert_called_once_with(
            "https://example.openai.azure.com", 60.0
        )
        client.images.generate.assert_called_once_with(
            model="image-deployment",
            prompt="an original fantasy citadel",
            n=1,
            size="1024x1024",
        )

    def test_rejects_valid_png_with_trailing_bytes(self) -> None:
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(valid_png() + b"trailing").decode()
                )
            ]
        )
        generator = FoundryImageGenerator(
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=Mock(return_value=client),
        )

        with self.assertRaises(ImageGenerationError) as raised:
            generator.generate("private prompt")

        self.assertEqual(raised.exception.code, "invalid_response")

    def test_rejects_missing_or_truncated_iend(self) -> None:
        png = valid_png()

        for content in (png[:-12], png[:-8], png[:-1]):
            with self.subTest(content_length=len(content)):
                client = Mock()
                client.images.generate.return_value = SimpleNamespace(
                    data=[
                        SimpleNamespace(
                            b64_json=base64.b64encode(content).decode()
                        )
                    ]
                )
                generator = FoundryImageGenerator(
                    endpoint="https://example.openai.azure.com",
                    deployment="image-deployment",
                    timeout_seconds=60.0,
                    client_factory=Mock(return_value=client),
                )

                with self.assertRaises(ImageGenerationError) as raised:
                    generator.generate("private prompt")

                self.assertEqual(raised.exception.code, "invalid_response")

    def test_constructs_client_lazily_and_reuses_it(self) -> None:
        png = valid_png()
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(
            data=[SimpleNamespace(b64_json=base64.b64encode(png).decode())]
        )
        factory = Mock(return_value=client)
        generator = FoundryImageGenerator(
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=factory,
        )

        factory.assert_not_called()
        generator.generate("first")
        generator.generate("second")

        factory.assert_called_once()

    def test_rejects_malformed_responses(self) -> None:
        invalid_responses = [
            SimpleNamespace(data=[]),
            SimpleNamespace(
                data=[
                    SimpleNamespace(b64_json=base64.b64encode(b"first").decode()),
                    SimpleNamespace(b64_json=base64.b64encode(b"second").decode()),
                ]
            ),
            SimpleNamespace(data=[SimpleNamespace(b64_json=None)]),
            SimpleNamespace(data=[SimpleNamespace(b64_json="not base64")]),
            SimpleNamespace(
                data=[SimpleNamespace(b64_json=base64.b64encode(b"").decode())]
            ),
            SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json=base64.b64encode(
                            b"\x89PNG\r\n\x1a\nsignature-and-junk"
                        ).decode()
                    )
                ]
            ),
            SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json=base64.b64encode(valid_png()[:-8]).decode()
                    )
                ]
            ),
            SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json=base64.b64encode(
                            valid_png()[:24] + b"corrupt" + valid_png()[31:]
                        ).decode()
                    )
                ]
            ),
        ]

        for response in invalid_responses:
            with self.subTest(response=response):
                client = Mock()
                client.images.generate.return_value = response
                generator = FoundryImageGenerator(
                    endpoint="https://example.openai.azure.com",
                    deployment="image-deployment",
                    timeout_seconds=60.0,
                    client_factory=Mock(return_value=client),
                )

                with self.assertRaisesRegex(
                    ImageGenerationError, "invalid response"
                ) as raised:
                    generator.generate("private prompt")

                self.assertEqual(raised.exception.code, "invalid_response")

    def test_rejects_png_dimensions_above_pixel_limit(self) -> None:
        png = valid_png()
        oversized_ihdr = png[:16] + (5000).to_bytes(4, "big") + (
            5000
        ).to_bytes(4, "big") + png[24:]
        client = Mock()
        client.images.generate.return_value = SimpleNamespace(
            data=[
                SimpleNamespace(
                    b64_json=base64.b64encode(oversized_ihdr).decode()
                )
            ]
        )
        generator = FoundryImageGenerator(
            endpoint="https://example.openai.azure.com",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=Mock(return_value=client),
        )

        with self.assertRaises(ImageGenerationError) as raised:
            generator.generate("private prompt")

        self.assertEqual(raised.exception.code, "invalid_response")

    def test_translates_provider_failures_without_leaking_details(self) -> None:
        cases = [
            (SimpleNamespace(status_code=401, code="secret"), "authentication_failed"),
            (SimpleNamespace(status_code=429, code="secret"), "throttled"),
            (SimpleNamespace(status_code=503, code="secret"), "provider_unavailable"),
            (SimpleNamespace(status_code=400, code="content_policy_violation"), "safety_rejected"),
        ]

        for provider_error, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                error = RuntimeError("provider body with private prompt")
                error.status_code = provider_error.status_code
                error.code = provider_error.code
                client = Mock()
                client.images.generate.side_effect = error
                generator = FoundryImageGenerator(
                    endpoint="https://secret.example",
                    deployment="secret-deployment",
                    timeout_seconds=60.0,
                    client_factory=Mock(return_value=client),
                )

                with self.assertRaises(ImageGenerationError) as raised:
                    generator.generate("private prompt")

                self.assertEqual(raised.exception.code, expected_code)
                safe_message = str(raised.exception)
                self.assertNotIn("private prompt", safe_message)
                self.assertNotIn("secret", safe_message)
                client.images.generate.assert_called_once()

    def test_translates_real_openai_internal_server_error(self) -> None:
        request = httpx.Request(
            "POST",
            "https://example.services.ai.azure.com/openai/v1/images/generations",
        )
        response = httpx.Response(
            500,
            request=request,
            json={"error": {"message": "Unable to get resource information."}},
        )
        client = Mock()
        client.images.generate.side_effect = openai.InternalServerError(
            "Unable to get resource information.",
            response=response,
            body=response.json(),
        )
        generator = FoundryImageGenerator(
            endpoint="https://example.services.ai.azure.com/openai/v1",
            deployment="image-deployment",
            timeout_seconds=60.0,
            client_factory=Mock(return_value=client),
        )

        with self.assertRaises(ImageGenerationError) as raised:
            generator.generate("private prompt")

        self.assertEqual(raised.exception.code, "provider_unavailable")
        self.assertEqual(
            str(raised.exception),
            "The image provider is temporarily unavailable.",
        )


if __name__ == "__main__":
    unittest.main()