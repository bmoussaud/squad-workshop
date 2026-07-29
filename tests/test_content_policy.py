import unittest
from unittest.mock import Mock, patch

from fantasy_cards.application import GenerationService
from fantasy_cards.domain import CardGenerationRequest
from fantasy_cards.policy import (
    CONTENT_POLICY_REFUSAL,
    ContentPolicyError,
    validate_content_policy,
)


SAFE_TITLE = "Ember Sentinel"
SAFE_DESCRIPTION = "adult original fantasy knight made of living flame"


class ClosedVocabularyPolicyTests(unittest.TestCase):
    def test_accepts_only_declared_original_fantasy_grammar(self) -> None:
        validate_content_policy(SAFE_TITLE, SAFE_DESCRIPTION)

    def test_rejects_recognized_people_characters_and_unknown_entities(self) -> None:
        cases = (
            "adult original fantasy knight resembling Barack Obama",
            "adult original fantasy warrior beside Batman",
            "adult original fantasy Jedi knight",
            "adult original fantasy knight named qzxv",
        )
        self.assert_rejected(cases)

    def test_rejects_protected_phrases_composed_only_of_individually_safe_words(self) -> None:
        self.assert_rejected(
            (
                "adult original fantasy moon knight",
                "adult original fantasy knight with moon knight",
                "adult original fantasy storm shadow",
            )
        )

    def test_rejects_lowercase_and_unknown_artist_style_requests(self) -> None:
        self.assert_rejected(
            (
                "adult original fantasy knight in the style of banksy",
                "adult original fantasy knight in qzxv style",
                "adult original fantasy knight by rembrandt",
            )
        )

    def test_rejects_word_and_numeric_minor_requests_across_ranges(self) -> None:
        self.assert_rejected(
            tuple(
                f"adult original fantasy knight with {minor}"
                for minor in (
                    "baby",
                    "toddler",
                    "child",
                    "schoolgirl",
                    "teen",
                    "teenager",
                    "adolescent",
                    "age regressed",
                    "1 year old",
                    "12 years old",
                    "17 years old",
                    "117 years old",
                )
            )
        )

    def test_rejects_unicode_homoglyphs_and_noncanonical_normalization(self) -> None:
        self.assert_rejected(
            (
                "adult original fantasy knight with Bаtman armor",
                "ａｄｕｌｔ original fantasy knight",
                "adult original fantasy kni\u0301ght",
                "adult original fantasy knight\u200b",
                "\u00a0adult original fantasy knight made of living flame\u00a0",
                "\u2003adult original fantasy knight made of living flame\u2003",
            )
        )

    def test_rejects_missing_adult_original_or_fantasy_attestation(self) -> None:
        self.assert_rejected(
            (
                "original fantasy knight",
                "adult fantasy knight",
                "adult original knight",
                "adult original fantasy forest",
            )
        )

    def test_refusal_is_stable_and_never_echoes_input(self) -> None:
        private_prompt = "Barack Obama as Batman in banksy style age 12"
        with self.assertRaises(ContentPolicyError) as raised:
            validate_content_policy("Unknown Person", private_prompt)
        self.assertEqual(str(raised.exception), CONTENT_POLICY_REFUSAL)
        self.assertNotIn(private_prompt, str(raised.exception))

    def assert_rejected(self, descriptions: tuple[str, ...]) -> None:
        for description in descriptions:
            with self.subTest(description=description):
                with self.assertRaises(ContentPolicyError):
                    validate_content_policy(SAFE_TITLE, description)


class PolicyOrderingTests(unittest.TestCase):
    def test_policy_precedes_idempotency_repository_and_provider_access(self) -> None:
        image_generator = Mock()
        artifact_store = Mock()
        job_repository = Mock()
        service = GenerationService(
            image_generator=image_generator,
            artifact_store=artifact_store,
            job_repository=job_repository,
        )
        request = CardGenerationRequest(
            "Unknown Person",
            "Barack Obama as Batman",
            "correlation",
            "idempotency",
        )

        with self.assertRaises(ContentPolicyError):
            service.generate(request)

        job_repository.get_by_idempotency_key.assert_not_called()
        job_repository.save.assert_not_called()
        image_generator.generate.assert_not_called()
        artifact_store.save.assert_not_called()

    def test_direct_service_caller_cannot_bypass_boundary_validation(self) -> None:
        service = GenerationService(Mock(), Mock(), Mock())
        with patch(
            "fantasy_cards.application.validate_content_policy",
            side_effect=ContentPolicyError(),
        ) as validate:
            with self.assertRaises(ContentPolicyError):
                service.generate(
                    CardGenerationRequest(
                        SAFE_TITLE,
                        SAFE_DESCRIPTION,
                        "correlation",
                        "idempotency",
                    )
                )
        validate.assert_called_once_with(SAFE_TITLE, SAFE_DESCRIPTION)


if __name__ == "__main__":
    unittest.main()
