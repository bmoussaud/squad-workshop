"""Local command-line demonstration."""

import argparse
import json
from dataclasses import asdict
from uuid import uuid4

from fantasy_cards.adapters import deterministic_idempotency_key
from fantasy_cards.config import build_local_application
from fantasy_cards.domain import CardGenerationRequest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a local fantasy card artifact")
    parser.add_argument("title")
    parser.add_argument("prompt")
    parser.add_argument("--correlation-id", default=None)
    parser.add_argument("--idempotency-key", default=None)
    arguments = parser.parse_args()

    request = CardGenerationRequest(
        title=arguments.title,
        prompt=arguments.prompt,
        correlation_id=arguments.correlation_id or str(uuid4()),
        idempotency_key=arguments.idempotency_key
        or deterministic_idempotency_key(arguments.title, arguments.prompt),
    )
    job = build_local_application().service.generate(request)
    print(json.dumps(asdict(job), indent=2))


if __name__ == "__main__":
    main()
