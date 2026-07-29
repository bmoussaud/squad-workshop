"""Fail-closed product content-policy validation."""

import re
import unicodedata

_ZERO_WIDTH_CATEGORIES = {"Cf"}
MAX_TITLE_LENGTH = 80
MAX_PROMPT_LENGTH = 1000
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
_CONFUSABLE_TRANSLATION = str.maketrans(
    {
        "а": "a",
        "е": "e",
        "і": "i",
        "о": "o",
        "р": "p",
        "с": "c",
        "х": "x",
        "у": "y",
        "Α": "a",
        "Β": "b",
        "Ε": "e",
        "Ι": "i",
        "Κ": "k",
        "Μ": "m",
        "Ν": "n",
        "Ο": "o",
        "Ρ": "p",
        "Τ": "t",
        "Χ": "x",
        "Υ": "y",
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
    "crystal guardian",
    "hollow knight",
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
    r"(?<!\d)(?:[0-9]|1[0-7])[\s-]*(?:year|yr)(?:s)?(?:\s|-)*old(?!\w)|"
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"thirteen|fourteen|fifteen|sixteen|seventeen)[\s-]+"
    r"(?:year|yr)(?:s)?(?:\s|-)*old\b"
)
_NUMERIC_MONTH_AGE = re.compile(
    r"(?<!\d)(\d{1,3})[\s-]*month(?:s)?(?:\s|-)*old(?!\w)"
)
_WRITTEN_MONTH_AGE = re.compile(
    r"\b(?:[^\W\d_]+[\s-]+){1,5}month(?:s)?(?:\s|-)*old\b",
    re.IGNORECASE,
)
_NAMED_ARTIST_STYLE = re.compile(
    r"\b(?:in\s+(?:the\s+)?style\s+of|inspired\s+by|painted\s+by|"
    r"drawn\s+by|rendered\s+like)\s+[^\W\d_]+(?:\s+[^\W\d_]+){0,3}\b",
    re.IGNORECASE,
)
_IDENTIFIABLE_SUBJECT = re.compile(
    r"\b(?:named|called|look(?:ing)?\s+like|portrait\s+of|depict(?:ing)?|"
    r"featuring|played\s+by)\s+(?:[^\W\d_]+\s+){1,3}[^\W\d_]+\b",
    re.IGNORECASE,
)


class InvalidGenerationRequest(ValueError):
    """A generation request is malformed or outside supported bounds."""

    code = "invalid_request"

    def __init__(self) -> None:
        super().__init__("The card name or description is invalid.")


class ContentPolicyRejected(ValueError):
    """A request violates the product's content policy."""

    code = "content_policy_rejected"

    def __init__(self) -> None:
        super().__init__(
            "This request can't be used to create an image. Please describe an "
            "original, fictional subject without real people, protected characters "
            "or brands, named artists, or any depiction of minors."
        )


def validate_generation_fields(title: str, prompt: str) -> tuple[str, str]:
    """Return bounded fields or raise a deterministic, non-echoing error."""

    if not isinstance(title, str) or not isinstance(prompt, str):
        raise InvalidGenerationRequest()
    title = title.strip()
    prompt = prompt.strip()
    if not 1 <= len(title) <= MAX_TITLE_LENGTH:
        raise InvalidGenerationRequest()
    if not 1 <= len(prompt) <= MAX_PROMPT_LENGTH:
        raise InvalidGenerationRequest()
    return title, prompt


def validate_generation_request(title: str, prompt: str) -> None:
    """Raise a safe error before a rejected request can reach a provider."""

    combined = f"{title}\n{prompt}"
    normalized = _normalize(combined)
    compact = _compact(normalized)
    deobfuscated = _remove_format_characters(combined).translate(
        _CONFUSABLE_TRANSLATION
    )
    if any(character.isalpha() and not character.isascii() for character in deobfuscated):
        raise ContentPolicyRejected()
    if _NAMED_ARTIST_STYLE.search(deobfuscated):
        raise ContentPolicyRejected()
    if _IDENTIFIABLE_SUBJECT.search(deobfuscated):
        raise ContentPolicyRejected()
    has_minor_month_age = any(
        int(match.group(1)) < 18 * 12
        for match in _NUMERIC_MONTH_AGE.finditer(normalized)
    )
    if (
        _MINOR_AGE.search(normalized)
        or _WRITTEN_MONTH_AGE.search(normalized)
        or has_minor_month_age
        or any(
            _contains(normalized, compact, term) for term in _BLOCKED_TERMS
        )
    ):
        raise ContentPolicyRejected()


def _normalize(value: str) -> str:
    return (
        _remove_format_characters(value)
        .translate(_CONFUSABLE_TRANSLATION)
        .casefold()
    )


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
