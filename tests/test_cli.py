import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from fantasy_cards.cli import main


class CliTests(unittest.TestCase):
    def test_prints_a_successful_job(self) -> None:
        output = StringIO()

        with patch(
            "sys.argv",
            [
                "fantasy-card",
                "Ember Sentinel",
                "A knight made of living flame",
                "--correlation-id",
                "corr-cli",
                "--idempotency-key",
                "idem-cli",
            ],
        ), redirect_stdout(output):
            main()

        job = json.loads(output.getvalue())
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["correlation_id"], "corr-cli")
        self.assertEqual(job["idempotency_key"], "idem-cli")
        self.assertEqual(job["generator_name"], "in-memory")
        self.assertEqual(job["artifact"]["media_type"], "text/plain")


if __name__ == "__main__":
    unittest.main()