"""Local command-line demonstration."""

import argparse
import json
import sys
from dataclasses import asdict
from uuid import uuid4

from dotenv import load_dotenv

from fantasy_cards.adapters import ImageGenerationError, deterministic_idempotency_key
from fantasy_cards.config import ConfigurationError, build_local_application
from fantasy_cards.domain import CardGenerationRequest


def main() -> int:
    load_dotenv()
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
    try:
        job = build_local_application().service.generate(request)
    except (ConfigurationError, ImageGenerationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(job), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
