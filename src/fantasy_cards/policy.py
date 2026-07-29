"""Deterministic fail-closed policy for user-authored generation input."""

import re
import unicodedata


CONTENT_POLICY_ID = "original-fantasy-closed-v1"
CONTENT_POLICY_VERSION = "1"
FOUNDRY_RAI_POLICY_NAME = "rai-fantasy-cards-v1"
CONTENT_POLICY_REFUSAL = (
    "This request can't be used to create an image. Please describe an original, "
    "fictional subject without real people, protected characters or brands, named "
    "artists, or any depiction of minors."
)

_ASCII_TEXT = re.compile(r"^[A-Za-z]+(?: [A-Za-z]+)*[.]?$")
_APPROVED_TITLES = frozenset(
    {
        "ancient citadel",
        "crystal guardian",
        "ember sentinel",
        "frost warden",
    }
)
_APPROVED_DESCRIPTIONS = frozenset(
    {
        "adult original fantasy dragon flying above ancient citadel",
        "adult original fantasy guardian with crystal shield",
        "adult original fantasy knight made of living flame",
        "adult original fantasy ranger with silver armor",
    }
)


class ContentPolicyError(ValueError):
    """A safe refusal that never includes submitted text."""

    code = "content_policy_rejected"

    def __init__(self) -> None:
        super().__init__(CONTENT_POLICY_REFUSAL)


def validate_content_policy(title: str, description: str) -> None:
    """Accept only the versioned original-fantasy grammar; reject uncertainty."""
    if (
        _validated_phrase(title) not in _APPROVED_TITLES
        or _validated_phrase(description) not in _APPROVED_DESCRIPTIONS
    ):
        raise ContentPolicyError()


def _validated_phrase(value: str) -> str:
    if (
        not value
        or value != unicodedata.normalize("NFKC", value)
        or not value.isascii()
        or _ASCII_TEXT.fullmatch(value) is None
    ):
        raise ContentPolicyError()
    return value.casefold()
