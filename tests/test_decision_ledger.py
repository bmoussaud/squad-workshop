"""Contract tests for the Squad decision-ledger v2 maintenance tool."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPOSITORY_ROOT / ".squad" / "scripts" / "decision_ledger.py"
FIXTURE_ROOT = Path(__file__).parent / "_decision_ledger_fixture"


def load_ledger_module():
    spec = importlib.util.spec_from_file_location("decision_ledger", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def entry(
    decision_id: str,
    *,
    supersedes: list[str] | None = None,
    body_size: int = 0,
    title: str | None = None,
) -> str:
    return (
        f"### {decision_id}: {title or 'Decision'}\n"
        f"**ID:** {decision_id}\n"
        "**Decided At:** 2026-07-28T22:16:16+02:00\n"
        "**By:** Switch\n"
        "**Status:** active\n"
        f"**Supersedes:** {json.dumps(supersedes or [])}\n"
        f"**What:** {'W' * body_size or 'A test decision.'}\n"
        "**Why:** Deterministic test coverage.\n"
    )


class DecisionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ledger = load_ledger_module()

    def setUp(self) -> None:
        shutil.rmtree(FIXTURE_ROOT, ignore_errors=True)
        (FIXTURE_ROOT / "decisions" / "inbox").mkdir(parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(FIXTURE_ROOT, ignore_errors=True)

    def write_canonical(self, *entries: str) -> Path:
        path = FIXTURE_ROOT / "decisions.md"
        path.write_text(
            self.ledger.CANONICAL_HEADER + "\n## Active Decisions\n\n" + "\n".join(entries),
            encoding="utf-8",
        )
        return path

    def test_migration_archives_legacy_bytes_and_manifest_segments(self) -> None:
        legacy = (
            b"# Squad Decisions\r\n\r\n"
            b"### 2026-07-01: First legacy decision\r\n"
            b"**By:** Team\r\n**What:** Keep this exact.\r\n**Why:** Audit.\r\n\r\n"
            b"### 2026-07-02: Second legacy decision\r\n"
            b"**By:** Team\r\n**What:** Preserve bytes.\r\n**Why:** Retrieval.\r\n"
        )
        decisions = FIXTURE_ROOT / "decisions.md"
        decisions.write_bytes(legacy)

        result = self.ledger.reconcile(FIXTURE_ROOT)

        source_hash = hashlib.sha256(legacy).hexdigest()
        archive = FIXTURE_ROOT / "decisions" / "archive" / f"legacy-{source_hash}.md"
        manifest = json.loads(
            (FIXTURE_ROOT / "decisions" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertTrue(result.migrated)
        self.assertEqual(archive.read_bytes(), legacy)
        self.assertIn(self.ledger.CANONICAL_HEADER.strip(), decisions.read_text(encoding="utf-8"))
        self.assertEqual(manifest["legacy_imports"][0]["source_sha256"], source_hash)
        legacy_id = manifest["legacy_imports"][0]["decisions"][0]["id"]
        self.assertEqual(
            self.ledger.retrieve(FIXTURE_ROOT, legacy_id),
            (
                b"### 2026-07-01: First legacy decision\r\n"
                b"**By:** Team\r\n**What:** Keep this exact.\r\n**Why:** Audit.\r\n\r\n"
            ),
        )

    def test_invalid_inbox_entry_is_quarantined_losslessly(self) -> None:
        self.write_canonical()
        raw = b"### invalid\n**ID:** D-invalid\n**By:** Switch\n"
        inbox = FIXTURE_ROOT / "decisions" / "inbox" / "switch-invalid.md"
        inbox.write_bytes(raw)

        result = self.ledger.reconcile(FIXTURE_ROOT)

        quarantine = FIXTURE_ROOT / "decisions" / "quarantine" / (
            f"{hashlib.sha256(raw).hexdigest()}.md"
        )
        self.assertEqual(result.quarantined, ["switch-invalid.md"])
        self.assertEqual(quarantine.read_bytes(), raw)
        self.assertFalse(inbox.exists())
        self.assertNotIn("D-invalid", (FIXTURE_ROOT / "decisions.md").read_text(encoding="utf-8"))

    def test_supersession_is_graph_derived_and_archived_with_verified_retrieval(self) -> None:
        original = entry("D-original", body_size=60000)
        successor = entry("D-successor", supersedes=["D-original"])
        path = self.write_canonical(original, successor)
        original_bytes = self.ledger._parse_blocks(path.read_bytes())[0][2]

        result = self.ledger.reconcile(FIXTURE_ROOT)

        self.assertEqual(result.archived_ids, ["D-original"])
        self.assertNotIn("D-original: Decision", (FIXTURE_ROOT / "decisions.md").read_text(encoding="utf-8"))
        self.assertEqual(
            self.ledger.retrieve(FIXTURE_ROOT, "D-original"),
            original_bytes,
        )
        archive = next((FIXTURE_ROOT / "decisions" / "archive").glob("D-original-*.md"))
        archive.write_text("corrupt", encoding="utf-8")
        with self.assertRaises(self.ledger.LedgerError):
            self.ledger.retrieve(FIXTURE_ROOT, "D-original")

    def test_unknown_and_duplicate_supersession_targets_fail_closed(self) -> None:
        self.write_canonical(entry("D-current"))
        unknown = entry("D-unknown", supersedes=["D-missing"])
        duplicate = entry("D-z-duplicate", supersedes=["D-current"])
        valid = entry("D-a-replacement", supersedes=["D-current"])
        inbox_dir = FIXTURE_ROOT / "decisions" / "inbox"
        (inbox_dir / "unknown.md").write_text(unknown, encoding="utf-8")
        (inbox_dir / "duplicate.md").write_text(duplicate, encoding="utf-8")
        (inbox_dir / "replacement.md").write_text(valid, encoding="utf-8")

        result = self.ledger.reconcile(FIXTURE_ROOT)

        self.assertEqual(result.quarantined, ["unknown.md", "duplicate.md"])
        self.assertEqual(result.accepted_inbox, ["replacement.md"])
        self.assertFalse((inbox_dir / "duplicate.md").exists())
        self.assertTrue(result.blocked_overflow is False)

    def test_all_recent_superseded_burst_compacts_to_target(self) -> None:
        entries: list[str] = []
        for index in range(30):
            old_id = f"D-old-{index:02d}"
            entries.append(entry(old_id, body_size=1700))
            entries.append(entry(f"D-new-{index:02d}", supersedes=[old_id], body_size=90))
        for index in range(12):
            entries.append(entry(f"D-foundation-{index:02d}", body_size=90))
        path = self.write_canonical(*entries)
        before = path.stat().st_size
        original_bytes = self.ledger._parse_blocks(path.read_bytes())[0][2]

        result = self.ledger.reconcile(FIXTURE_ROOT)

        self.assertGreater(before, self.ledger.HARD_CAP_BYTES)
        self.assertGreater(len(result.archived_ids), 0)
        self.assertLessEqual(path.stat().st_size, self.ledger.TARGET_BYTES)
        self.assertFalse(result.blocked_overflow)
        self.assertEqual(
            self.ledger.retrieve(FIXTURE_ROOT, "D-old-00"),
            original_bytes,
        )

    def test_active_only_overflow_blocks_inbox_without_data_loss(self) -> None:
        self.write_canonical(
            *(entry(f"D-foundation-{index:02d}", body_size=1800) for index in range(30))
        )
        inbox = FIXTURE_ROOT / "decisions" / "inbox" / "new-live.md"
        inbox.write_text(entry("D-new-live", body_size=100), encoding="utf-8")
        canonical_before = (FIXTURE_ROOT / "decisions.md").read_bytes()
        inbox_before = inbox.read_bytes()

        result = self.ledger.reconcile(FIXTURE_ROOT)

        self.assertTrue(result.blocked_overflow)
        self.assertEqual(result.blocked_inbox, ["new-live.md"])
        self.assertEqual((FIXTURE_ROOT / "decisions.md").read_bytes(), canonical_before)
        self.assertEqual(inbox.read_bytes(), inbox_before)
        self.assertEqual(result.archived_ids, [])


if __name__ == "__main__":
    unittest.main()
