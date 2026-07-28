"""Lossless, fail-closed maintenance for Squad's decision ledger.

This tool is deliberately stdlib-only so Scribe can use it in a local-state
Squad without installing project dependencies.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


CANONICAL_HEADER = "<!-- squad-decision-ledger:2 -->\n# Squad Decisions\n"
HARD_CAP_BYTES = 50 * 1024
TARGET_BYTES = 20 * 1024
ID_PATTERN = re.compile(r"^(?:D|L)-[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
HEADING_PATTERN = re.compile(rb"(?m)^### [^\r\n]*")
FIELD_PATTERN = re.compile(r"(?m)^\*\*(ID|Decided At|By|Status|Supersedes|What|Why):\*\*\s*(.+)$")


class LedgerError(ValueError):
    """The ledger is malformed or a requested artifact failed verification."""


@dataclass(frozen=True)
class Decision:
    id: str
    heading: str
    block: bytes
    decided_at: str
    supersedes: tuple[str, ...]


@dataclass
class ReconcileResult:
    migrated: bool = False
    archived_ids: list[str] | None = None
    quarantined: list[str] | None = None
    accepted_inbox: list[str] | None = None
    blocked_overflow: bool = False
    blocked_inbox: list[str] | None = None

    def __post_init__(self) -> None:
        self.archived_ids = self.archived_ids or []
        self.quarantined = self.quarantined or []
        self.accepted_inbox = self.accepted_inbox or []
        self.blocked_inbox = self.blocked_inbox or []


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_v2(data: bytes) -> bool:
    return data.replace(b"\r\n", b"\n").startswith(CANONICAL_HEADER.encode("utf-8"))


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _load_manifest(team_root: Path) -> dict[str, Any]:
    path = team_root / "decisions" / "manifest.json"
    if not path.exists():
        return {"version": 2, "archives": [], "legacy_imports": [], "quarantine": []}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise LedgerError(f"manifest is not valid JSON: {error}") from error
    if value.get("version") != 2:
        raise LedgerError("manifest version must be 2")
    for key in ("archives", "legacy_imports", "quarantine"):
        if not isinstance(value.get(key), list):
            raise LedgerError(f"manifest {key} must be a list")
    return value


def _parse_blocks(data: bytes) -> list[tuple[int, int, bytes]]:
    matches = list(HEADING_PATTERN.finditer(data))
    return [
        (match.start(), matches[index + 1].start() if index + 1 < len(matches) else len(data),
         data[match.start(): matches[index + 1].start() if index + 1 < len(matches) else len(data)])
        for index, match in enumerate(matches)
    ]


def _parse_decision(block: bytes) -> Decision:
    try:
        text = block.decode("utf-8")
    except UnicodeDecodeError as error:
        raise LedgerError("decision must be UTF-8") from error
    lines = text.splitlines()
    if not lines or not lines[0].startswith("### "):
        raise LedgerError("decision must begin with a level-3 heading")
    fields = {name: value.strip() for name, value in FIELD_PATTERN.findall(text)}
    required = ("ID", "Decided At", "By", "Status", "Supersedes", "What", "Why")
    missing = [field for field in required if not fields.get(field)]
    if missing:
        raise LedgerError(f"missing required field(s): {', '.join(missing)}")
    decision_id = fields["ID"]
    if not ID_PATTERN.fullmatch(decision_id) or not decision_id.startswith("D-"):
        raise LedgerError("ID must be a D- prefixed safe identifier")
    try:
        parsed_time = datetime.fromisoformat(fields["Decided At"].replace("Z", "+00:00"))
    except ValueError as error:
        raise LedgerError("Decided At must be ISO-8601") from error
    if parsed_time.tzinfo is None:
        raise LedgerError("Decided At must include a timezone")
    if fields["Status"] != "active":
        raise LedgerError("writers may submit only Status: active")
    try:
        supersedes = json.loads(fields["Supersedes"])
    except json.JSONDecodeError as error:
        raise LedgerError("Supersedes must be a JSON list") from error
    if not isinstance(supersedes, list) or any(
        not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in supersedes
    ):
        raise LedgerError("Supersedes must contain only ledger IDs")
    if len(set(supersedes)) != len(supersedes):
        raise LedgerError("Supersedes contains duplicate IDs")
    if decision_id in supersedes:
        raise LedgerError("a decision cannot supersede itself")
    return Decision(
        id=decision_id,
        heading=lines[0][4:].strip(),
        block=block,
        decided_at=fields["Decided At"],
        supersedes=tuple(supersedes),
    )


def _parse_canonical(path: Path) -> list[Decision]:
    data = path.read_bytes()
    if not _is_v2(data):
        raise LedgerError("canonical decisions.md is not ledger v2")
    decisions = [_parse_decision(block) for _, _, block in _parse_blocks(data)]
    ids = [decision.id for decision in decisions]
    if len(ids) != len(set(ids)):
        raise LedgerError("canonical decisions.md contains duplicate IDs")
    return decisions


def _legacy_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        decision
        for legacy_import in manifest["legacy_imports"]
        for decision in legacy_import["decisions"]
    ]


def _known_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = {record["id"]: record for record in manifest["archives"]}
    records.update({record["id"]: record for record in _legacy_records(manifest)})
    return records


def _derive_statuses(
    decisions: list[Decision], manifest: dict[str, Any]
) -> tuple[set[str], set[str]]:
    known = _known_records(manifest)
    decision_by_id = {decision.id: decision for decision in decisions}
    if len(decision_by_id) != len(decisions):
        raise LedgerError("duplicate canonical decision IDs")
    overlap = set(decision_by_id).intersection(known)
    if overlap:
        raise LedgerError(f"canonical/archive ID overlap: {sorted(overlap)[0]}")

    targets: set[str] = set()
    graph: dict[str, tuple[str, ...]] = {}
    for decision in decisions:
        graph[decision.id] = decision.supersedes
        for target in decision.supersedes:
            if target in targets:
                raise LedgerError(f"multiple successors claim {target}")
            if target in known and known[target].get("status") == "superseded":
                raise LedgerError(f"cannot supersede already superseded {target}")
            if target not in decision_by_id and target not in known:
                raise LedgerError(f"unknown supersession target {target}")
            targets.add(target)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise LedgerError("supersession cycle")
        if node in visited:
            return
        visiting.add(node)
        for target in graph[node]:
            if target in graph:
                visit(target)
        visiting.remove(node)
        visited.add(node)

    for decision in decisions:
        visit(decision.id)
    return set(decision_by_id).difference(targets), targets


def _render_canonical(decisions: list[Decision], manifest: dict[str, Any]) -> bytes:
    legacy_note = ""
    if manifest["legacy_imports"]:
        latest = manifest["legacy_imports"][-1]
        legacy_note = (
            "\n## Legacy Compatibility\n\n"
            f"Legacy import `{latest['source_sha256']}` is losslessly indexed in "
            f"`{latest['archive_path']}`; use decision-ledger retrieval by legacy ID.\n"
        )
    blocks = b"\n".join(decision.block.rstrip(b"\n") for decision in decisions)
    suffix = b"\n" if blocks else b""
    return CANONICAL_HEADER.encode("utf-8") + b"\n## Active Decisions\n\n" + blocks + suffix + legacy_note.encode("utf-8")


def _archive_path(team_root: Path, decision: Decision) -> Path:
    return team_root / "decisions" / "archive" / f"{decision.id}-{_sha256(decision.block)[:16]}.md"


def _archive_decisions(
    team_root: Path, manifest: dict[str, Any], archived: list[Decision], superseded_by: dict[str, str]
) -> None:
    existing = {record["id"] for record in manifest["archives"]}
    for decision in archived:
        path = _archive_path(team_root, decision)
        digest = _sha256(decision.block)
        if path.exists():
            if _sha256(path.read_bytes()) != digest:
                raise LedgerError(f"archive hash mismatch for {decision.id}")
        else:
            _atomic_write(path, decision.block)
            if _sha256(path.read_bytes()) != digest:
                raise LedgerError(f"archive verification failed for {decision.id}")
        if decision.id not in existing:
            manifest["archives"].append(
                {
                    "id": decision.id,
                    "heading": decision.heading,
                    "status": "superseded",
                    "superseded_by": superseded_by[decision.id],
                    "archive_path": path.relative_to(team_root).as_posix(),
                    "sha256": digest,
                }
            )
    _write_json(team_root / "decisions" / "manifest.json", manifest)


def _compact(
    decisions: list[Decision], manifest: dict[str, Any]
) -> tuple[list[Decision], list[Decision], dict[str, str], bool]:
    active_ids, superseded_ids = _derive_statuses(decisions, manifest)
    active = [decision for decision in decisions if decision.id in active_ids]
    rendered = _render_canonical(decisions, manifest)
    if len(rendered) <= HARD_CAP_BYTES:
        return decisions, [], {}, False

    decision_by_id = {decision.id: decision for decision in decisions}
    successor = {
        target: decision.id
        for decision in decisions
        for target in decision.supersedes
        if target in superseded_ids
    }
    candidates = sorted(
        (decision_by_id[decision_id] for decision_id in superseded_ids),
        key=lambda decision: (decision.decided_at, decision.id),
    )
    archived: list[Decision] = []
    remaining = list(decisions)
    for candidate in candidates:
        remaining = [decision for decision in remaining if decision.id != candidate.id]
        archived.append(candidate)
        if len(_render_canonical(remaining, manifest)) <= TARGET_BYTES:
            break
    return remaining, archived, {decision.id: successor[decision.id] for decision in archived}, (
        len(_render_canonical(remaining, manifest)) > HARD_CAP_BYTES
    )


def _quarantine(
    team_root: Path, manifest: dict[str, Any], inbox_path: Path, reason: str
) -> None:
    raw = inbox_path.read_bytes()
    digest = _sha256(raw)
    path = team_root / "decisions" / "quarantine" / f"{digest}.md"
    if not path.exists():
        _atomic_write(path, raw)
    if path.read_bytes() != raw:
        raise LedgerError(f"quarantine verification failed for {inbox_path.name}")
    manifest["quarantine"].append(
        {
            "inbox_file": inbox_path.name,
            "path": path.relative_to(team_root).as_posix(),
            "sha256": digest,
            "reason": reason,
        }
    )
    _write_json(team_root / "decisions" / "manifest.json", manifest)
    inbox_path.unlink()


def _migrate_legacy(team_root: Path) -> None:
    source = team_root / "decisions.md"
    raw = source.read_bytes()
    digest = _sha256(raw)
    archive = team_root / "decisions" / "archive" / f"legacy-{digest}.md"
    _atomic_write(archive, raw)
    if archive.read_bytes() != raw:
        raise LedgerError("legacy archive verification failed")

    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for ordinal, (start, end, block) in enumerate(_parse_blocks(raw), start=1):
        record_id = f"L-{_sha256(block)[:16]}-{ordinal}"
        while record_id in ids:
            ordinal += 1
            record_id = f"L-{_sha256(block)[:16]}-{ordinal}"
        ids.add(record_id)
        heading = block.splitlines()[0][4:].decode("utf-8", errors="replace").strip()
        records.append(
            {
                "id": record_id,
                "heading": heading,
                "status": "legacy-unclassified",
                "byte_start": start,
                "byte_end": end,
                "sha256": _sha256(block),
            }
        )
    manifest = {
        "version": 2,
        "archives": [],
        "legacy_imports": [
            {
                "source_sha256": digest,
                "archive_path": archive.relative_to(team_root).as_posix(),
                "decisions": records,
            }
        ],
        "quarantine": [],
    }
    _write_json(team_root / "decisions" / "manifest.json", manifest)
    _atomic_write(source, _render_canonical([], manifest))


def reconcile(team_root: Path) -> ReconcileResult:
    """Migrate once, validate inbox entries, compact superseded history, and report overflow."""

    team_root = team_root.resolve()
    source = team_root / "decisions.md"
    if not source.exists():
        raise LedgerError(f"missing {source}")
    result = ReconcileResult()
    if not _is_v2(source.read_bytes()):
        _migrate_legacy(team_root)
        result.migrated = True

    manifest = _load_manifest(team_root)
    decisions = _parse_canonical(source)
    _derive_statuses(decisions, manifest)
    inbox = team_root / "decisions" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)

    candidates: list[tuple[Decision, Path]] = []
    for path in sorted(inbox.glob("*.md")):
        try:
            candidates.append((_parse_decision(path.read_bytes()), path))
        except LedgerError as error:
            _quarantine(team_root, manifest, path, str(error))
            result.quarantined.append(path.name)
    candidates.sort(key=lambda item: (item[0].decided_at, item[0].id, _sha256(item[0].block)))

    accepted_paths: list[Path] = []
    for candidate, path in candidates:
        try:
            prospective = [*decisions, candidate]
            _derive_statuses(prospective, manifest)
            compacted, _, _, blocked = _compact(prospective, manifest)
            if blocked:
                result.blocked_overflow = True
                result.blocked_inbox.append(path.name)
                continue
            decisions = prospective
            accepted_paths.append(path)
            result.accepted_inbox.append(path.name)
        except LedgerError as error:
            _quarantine(team_root, manifest, path, str(error))
            result.quarantined.append(path.name)

    compacted, archived, successor, blocked = _compact(decisions, manifest)
    result.blocked_overflow = result.blocked_overflow or blocked
    if archived:
        _archive_decisions(team_root, manifest, archived, successor)
        result.archived_ids.extend(decision.id for decision in archived)
        decisions = compacted
    if not result.blocked_overflow:
        _atomic_write(source, _render_canonical(decisions, manifest))
        for path in accepted_paths:
            path.unlink(missing_ok=True)
    return result


def retrieve(team_root: Path, decision_id: str) -> bytes:
    """Return a canonical or archived decision only after SHA-256 verification."""

    team_root = team_root.resolve()
    for decision in _parse_canonical(team_root / "decisions.md"):
        if decision.id == decision_id:
            return decision.block
    manifest = _load_manifest(team_root)
    for record in manifest["archives"]:
        if record["id"] == decision_id:
            path = team_root / record["archive_path"]
            content = path.read_bytes()
            if _sha256(content) != record["sha256"]:
                raise LedgerError(f"archive hash mismatch for {decision_id}")
            return content
    for legacy_import in manifest["legacy_imports"]:
        for record in legacy_import["decisions"]:
            if record["id"] == decision_id:
                content = (team_root / legacy_import["archive_path"]).read_bytes()[
                    record["byte_start"]:record["byte_end"]
                ]
                if _sha256(content) != record["sha256"]:
                    raise LedgerError(f"legacy archive hash mismatch for {decision_id}")
                return content
    raise LedgerError(f"unknown decision ID {decision_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team-root", type=Path, default=Path(".squad"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("reconcile")
    show = subparsers.add_parser("show")
    show.add_argument("decision_id")
    args = parser.parse_args(argv)
    try:
        if args.command == "reconcile":
            result = reconcile(args.team_root)
            print(
                json.dumps(
                    {
                        "status": "BLOCKED_ACTIVE_OVERFLOW"
                        if result.blocked_overflow
                        else "OK",
                        "migrated": result.migrated,
                        "archived_ids": result.archived_ids,
                        "quarantined": result.quarantined,
                        "accepted_inbox": result.accepted_inbox,
                        "blocked_inbox": result.blocked_inbox,
                    },
                    sort_keys=True,
                )
            )
            return 3 if result.blocked_overflow else 0
        sys.stdout.buffer.write(retrieve(args.team_root, args.decision_id))
        return 0
    except LedgerError as error:
        print(f"decision-ledger: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
