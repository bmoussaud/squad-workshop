"""Count active PR environments against the set of open pull requests.

The Azure query is only a candidate filter. This helper owns the fail-closed
cross-check against GitHub's open PR list so closed/merged PR leaks do not
silently consume the app-tier concurrency cap.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any


_RG_NAME_RE = re.compile(r"^[A-Za-z0-9_.()\-]{1,90}$")


@dataclass(frozen=True)
class ActiveEnvironmentCount:
    active_count: int
    active_names: tuple[str, ...]
    orphan_count: int
    orphan_names: tuple[str, ...]


def _parse_pr_numbers(raw: str) -> frozenset[int]:
    numbers: set[int] = set()
    for token in raw.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        if not stripped.isascii() or not stripped.isdigit():
            raise ValueError(f"malformed PR number in list: {stripped!r}")
        numbers.add(int(stripped))
    return frozenset(numbers)


def _parse_current_pr(raw: str) -> int:
    stripped = raw.strip()
    if not stripped.isascii() or not stripped.isdigit():
        raise ValueError("current PR number is malformed")
    return int(stripped)


def _safe_name(raw: object) -> str:
    if not isinstance(raw, str) or not _RG_NAME_RE.fullmatch(raw):
        raise ValueError("resource group name is missing or malformed")
    return raw


def _pr_number_from_tags(tags: object) -> int:
    if not isinstance(tags, dict):
        raise ValueError("candidate group tags are missing or malformed")
    raw = tags.get("pr-number")
    if not isinstance(raw, str):
        raise ValueError("candidate group pr-number tag is missing or malformed")
    stripped = raw.strip()
    if not stripped.isascii() or not stripped.isdigit():
        raise ValueError("candidate group pr-number tag is malformed")
    return int(stripped)


def count_active_open_environments(
    groups: list[dict[str, Any]],
    *,
    open_pr_numbers: frozenset[int],
    current_pr_number: int,
) -> ActiveEnvironmentCount:
    active: list[str] = []
    orphans: list[str] = []

    for group in groups:
        name = _safe_name(group.get("name"))
        pr_number = _pr_number_from_tags(group.get("tags"))
        if pr_number == current_pr_number:
            continue
        if pr_number in open_pr_numbers:
            active.append(name)
        else:
            orphans.append(name)

    return ActiveEnvironmentCount(
        active_count=len(active),
        active_names=tuple(active),
        orphan_count=len(orphans),
        orphan_names=tuple(orphans),
    )


def _load_groups(raw: str) -> list[dict[str, Any]]:
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("groups JSON must be an array")
    if not all(isinstance(group, dict) for group in payload):
        raise ValueError("groups JSON must contain only objects")
    return payload


def _read_groups_json(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return source


def _emit(result: ActiveEnvironmentCount, output_format: str) -> None:
    payload = {
        "active_count": result.active_count,
        "active_names": ",".join(result.active_names),
        "orphan_count": result.orphan_count,
        "orphan_names": ",".join(result.orphan_names),
    }
    if output_format == "json":
        print(json.dumps(payload, sort_keys=True))
    else:
        print("\n".join(f"{key}={value}" for key, value in payload.items()))


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr_env_active_count",
        description=(
            "Count candidate PR environment resource groups that belong to open "
            "pull requests, excluding the current PR. Malformed inputs fail closed."
        ),
    )
    parser.add_argument(
        "--groups-json",
        required=True,
        help="Azure resource-group JSON array, or '-' to read from stdin",
    )
    parser.add_argument(
        "--open-pr-numbers",
        required=True,
        help="comma-separated open pull request numbers from GitHub",
    )
    parser.add_argument(
        "--current-pr-number",
        required=True,
        help="current PR number to exclude from the count",
    )
    parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="env",
        help="output format",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        groups = _load_groups(_read_groups_json(args.groups_json))
        open_pr_numbers = _parse_pr_numbers(args.open_pr_numbers)
        current_pr_number = _parse_current_pr(args.current_pr_number)
        result = count_active_open_environments(
            groups,
            open_pr_numbers=open_pr_numbers,
            current_pr_number=current_pr_number,
        )
    except (json.JSONDecodeError, ValueError) as error:
        print(f"error={error}", file=sys.stderr)
        return 2
    _emit(result, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
