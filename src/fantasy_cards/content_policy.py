"""Fail-closed product content-policy validation."""

import re
import unicodedata

_ZERO_WIDTH_CATEGORIES = {"Cf"}
_LEET_TRANSLATION = str.maketrans(
    {
        "@": "a",
        "$": "s",
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
    }
)

_BLOCKED_TERMS = (
    # Real-person likenesses and common indirection.
    "taylor swift",
    "barack obama",
    "donald trump",
    "robert downey jr",
    "actor who played",
    "celebrity",
    "real person",
    "lookalike",
    "impersonation",
    # Protected properties, characters, brands, and studios.
    "harry potter",
    "mickey mouse",
    "star wars",
    "pokemon",
    "pikachu",
    "marvel",
    "disney",
    "batman",
    "superman",
    "iron man",
    "lord of the rings",
    "game of thrones",
    # Named artist style imitation.
    "hayao miyazaki",
    "greg rutkowski",
    "vincent van gogh",
    # Minor depictions.
    "minor",
    "underage",
    "child",
    "kid",
    "toddler",
    "infant",
    "baby",
    "teen",
    "teenager",
    "schoolgirl",
    "schoolboy",
    "loli",
    # Attempts to override or bypass policy.
    "ignore all previous safety rules",
    "bypass safety",
    "bypass policy",
)
_MINOR_AGE = re.compile(
    r"(?<!\d)1[0-7][\s-]*(?:year|yr)(?:s)?(?:\s|-)*old(?!\w)"
)
_NAMED_ARTIST_STYLE = re.compile(
    r"\b(?:in\s+(?:the\s+)?style\s+of|inspired\s+by|painted\s+by)\s+"
    r"(?:[A-Z][A-Za-z'’-]*\s+){1,3}[A-Z][A-Za-z'’-]*\b"
)


class ContentPolicyRejected(ValueError):
    """A request violates the product's content policy."""

    code = "content_policy_rejected"

    def __init__(self) -> None:
        super().__init__(
            "This request can't be used to create an image. Please describe an "
            "original, fictional subject without real people, protected characters "
            "or brands, named artists, or any depiction of minors."
        )


def validate_generation_request(title: str, prompt: str) -> None:
    """Raise a safe error before a rejected request can reach a provider."""

    normalized = _normalize(f"{title}\n{prompt}")
    compact = _compact(normalized)
    if _NAMED_ARTIST_STYLE.search(_remove_format_characters(f"{title}\n{prompt}")):
        raise ContentPolicyRejected()
    if _MINOR_AGE.search(normalized) or any(
        _contains(normalized, compact, term) for term in _BLOCKED_TERMS
    ):
        raise ContentPolicyRejected()


def _normalize(value: str) -> str:
    return _remove_format_characters(value).casefold()


def _remove_format_characters(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    characters: list[str] = []
    for character in normalized:
        category = unicodedata.category(character)
        if category in _ZERO_WIDTH_CATEGORIES:
            continue
        characters.append(" " if category.startswith("C") else character)
    return "".join(characters)


def _compact(value: str) -> str:
    return "".join(
        character for character in value.translate(_LEET_TRANSLATION) if character.isalnum()
    )


def _contains(normalized: str, compact: str, term: str) -> bool:
    normalized_term = _normalize(term)
    if re.search(rf"(?<!\w){re.escape(normalized_term)}(?!\w)", normalized):
        return True
    return _compact(normalized_term) in compact
