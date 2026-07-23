from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


class BlobArtifactStoreContractTests(unittest.TestCase):
    account_url = "https://cards.blob.core.windows.net"
    container_name = "generated-cards"

    def create_store(self, service_client: Mock):
        from fantasy_cards.adapters import BlobArtifactStore

        return BlobArtifactStore(
            account_url=self.account_url,
            container_name=self.container_name,
            service_client=service_client,
        )

    def test_save_uses_opaque_png_name_conditional_create_and_no_metadata(self) -> None:
        service_client = Mock()
        container_client = service_client.get_container_client.return_value
        blob_client = container_client.get_blob_client.return_value
        artifact_id = "11111111-1111-4111-8111-111111111111"
        store = self.create_store(service_client)

        with patch("fantasy_cards.adapters.uuid4", return_value=artifact_id):
            artifact = store.save(b"png-content", "image/png")

        service_client.get_container_client.assert_called_once_with(self.container_name)
        container_client.get_blob_client.assert_called_once_with(f"{artifact_id}.png")
        blob_client.upload_blob.assert_called_once()
        positional, keywords = blob_client.upload_blob.call_args
        self.assertEqual(positional[0], b"png-content")
        self.assertFalse(keywords.get("overwrite", True))
        self.assertNotIn("metadata", keywords)
        content_settings = keywords["content_settings"]
        self.assertEqual(content_settings.content_type, "image/png")
        self.assertEqual(artifact.artifact_id, artifact_id)
        self.assertEqual(artifact.file_path, f"{artifact_id}.png")
        self.assertEqual(artifact.media_type, "image/png")
        self.assertEqual(artifact.size_bytes, len(b"png-content"))

    def test_save_rejects_media_type_and_size_before_sdk_call(self) -> None:
        service_client = Mock()
        store = self.create_store(service_client)
        cases = ((b"content", "text/plain"), (b"x" * (10 * 1024 * 1024 + 1), "image/png"))

        for content, media_type in cases:
            with self.subTest(media_type=media_type, size=len(content)):
                with self.assertRaises(RuntimeError) as raised:
                    store.save(content, media_type)
                self.assertNotIn(media_type, str(raised.exception))

        service_client.get_container_client.assert_not_called()

    def test_collision_retries_three_times_without_overwrite(self) -> None:
        from azure.core.exceptions import ResourceExistsError

        service_client = Mock()
        container_client = service_client.get_container_client.return_value
        blob_client = container_client.get_blob_client.return_value
        blob_client.upload_blob.side_effect = ResourceExistsError("collision")
        ids = (
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
            "33333333-3333-4333-8333-333333333333",
        )
        store = self.create_store(service_client)

        with patch("fantasy_cards.adapters.uuid4", side_effect=ids):
            with self.assertRaises(RuntimeError) as raised:
                store.save(b"png", "image/png")

        self.assertEqual(blob_client.upload_blob.call_count, 3)
        self.assertNotIn("collision", str(raised.exception))
        for call in blob_client.upload_blob.call_args_list:
            self.assertFalse(call.kwargs.get("overwrite", True))

    def test_read_validates_uuid_before_network_and_returns_bounded_content(self) -> None:
        service_client = Mock()
        container_client = service_client.get_container_client.return_value
        blob_client = container_client.get_blob_client.return_value
        downloader = blob_client.download_blob.return_value
        downloader.properties = SimpleNamespace(
            size=3,
            content_settings=SimpleNamespace(content_type="image/png"),
        )
        downloader.readall.return_value = b"png"
        store = self.create_store(service_client)

        with self.assertRaises(RuntimeError):
            store.read("not-a-uuid")
        service_client.get_container_client.assert_not_called()

        artifact_id = "11111111-1111-4111-8111-111111111111"
        content = store.read(artifact_id)

        container_client.get_blob_client.assert_called_once_with(f"{artifact_id}.png")
        self.assertEqual(content.content, b"png")
        self.assertEqual(content.media_type, "image/png")
        self.assertEqual(content.size_bytes, 3)

    def test_configuration_uses_token_credential_and_rejects_secret_auth(self) -> None:
        from fantasy_cards.config import ConfigurationError, build_web_application

        safe_environment = {
            "FANTASY_CARD_ARTIFACT_STORE": "blob",
            "AZURE_STORAGE_ACCOUNT_URL": self.account_url,
            "FANTASY_CARD_BLOB_CONTAINER": self.container_name,
        }
        credential = Mock()
        with patch.dict("os.environ", safe_environment, clear=True), patch(
            "azure.identity.DefaultAzureCredential", return_value=credential
        ) as credential_type, patch(
            "azure.storage.blob.BlobServiceClient"
        ) as service_client_type:
            application = build_web_application()
            application.artifact_reader._container_client()

        credential_type.assert_called_once_with()
        service_client_type.assert_called_once_with(
            account_url=self.account_url, credential=credential
        )
        self.assertIsNotNone(application.artifact_reader)

        with patch.dict(
            "os.environ", {"FANTASY_CARD_ARTIFACT_STORE": "blob"}, clear=True
        ), self.assertRaises(ConfigurationError) as raised:
            build_web_application()
        self.assertNotIn("secret", str(raised.exception).lower())

        secret_environment = {
            **safe_environment,
            "AZURE_STORAGE_CONNECTION_STRING": "secret-connection-string",
            "AZURE_STORAGE_ACCOUNT_KEY": "secret-key",
            "AZURE_STORAGE_SAS_TOKEN": "secret-sas",
        }
        credential = Mock()
        with patch.dict("os.environ", secret_environment, clear=True), patch(
            "azure.identity.DefaultAzureCredential", return_value=credential
        ), patch("azure.storage.blob.BlobServiceClient") as client_type:
            application = build_web_application()
            application.artifact_reader._container_client()

        client_type.assert_called_once_with(
            account_url=self.account_url, credential=credential
        )


if __name__ == "__main__":
    unittest.main()