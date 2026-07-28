"""Detect whether a PR needs the gated Foundry exception path.

The preflight gate already knows how to fail closed when ``requires_foundry`` is
true. This module supplies that boolean from PR metadata only: changed paths and
labels. It performs no GitHub or Azure calls.

Path matching is intentionally narrow because the workflow uses this answer to
set ``DEPLOY_FOUNDRY``. A false positive can create scarce billable Foundry
capacity and saturate the one-environment cap; a false negative falls back to the
documented cheap default of deploying the app against the shared Foundry.

Matched paths:

* ``infra/foundry.bicep``: owns Foundry account/project/model deployment,
  per-PR/shared switching, outputs, and Foundry role assignment wiring.
* ``infra/modules/shared-foundry-rbac.bicep``: owns shared Foundry invocation
  RBAC for PR app identities.
* label ``requires:foundry``: explicit maintainer/author opt-in for ambiguous
  changes that truly need a per-PR Foundry account/project/model deployment.
* Foundry switch-integrity inspection: when ``infra/main.bicep`` or
  ``infra/main.bicepparam`` changed, inspect the checked-out file content and
  require Foundry only when the ``deployFoundry`` switch no longer flows from
  ``DEPLOY_FOUNDRY``. This is content-aware because those root files are shared
  by ordinary app-tier, tagging, budget, and observability work.

Deliberately excluded examples:

* ``infra/web.bicep``: consumes the Foundry endpoint/deployment as app settings,
  but mostly owns app-tier hosting, storage, networking, and scaling. Matching
  the whole file would gate routine app-tier infrastructure PRs.
* ``infra/main.bicep`` and ``infra/main.bicepparam``: root/shared parameter files
  touched by ordinary app-tier, tagging, budget, observability, and naming work.
  Path-only evidence here is too ambiguous; use ``requires:foundry`` when a diff
  in these files actually changes Foundry region/model/SKU/capacity behavior.
* ``src/fantasy_cards/adapters.py`` and its tests: these own provider request,
  response, and safety contracts, but they can be validated against the shared
  Foundry with the independent ``validate:live-foundry`` hook. Use
  ``requires:foundry`` only when such a change specifically needs isolated new
  Foundry provisioning rather than shared-Foundry validation.
* ``src/fantasy_cards/config.py`` and ``src/fantasy_cards/web.py``: they wire and
  present provider-backed generation, but broad changes there are usually app
  configuration/UI/API behavior. Use the explicit ``requires:foundry`` label when
  such a change truly alters the Foundry safety/provider contract.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


MALFORMED_INPUT_EXIT_CODE = 3

REQUIRES_FOUNDRY_LABEL = "requires:foundry"
LIVE_VALIDATION_LABEL = "validate:live-foundry"

MAIN_BICEP_PATH = "infra/main.bicep"
MAIN_BICEPPARAM_PATH = "infra/main.bicepparam"


@dataclass(frozen=True)
class FoundryPathPattern:
    pattern: str
    category: str
    rationale: str

    def matches(self, path: str) -> bool:
        return path == self.pattern


@dataclass(frozen=True)
class FoundryScope:
    requires_foundry: bool
    live_validation_requested: bool
    reasons: dict[str, dict[str, object]]


FOUNDRY_PATH_PATTERNS: tuple[FoundryPathPattern, ...] = (
    FoundryPathPattern(
        "infra/foundry.bicep",
        "foundry_provisioning",
        "Foundry account/project/model deployment and Foundry RBAC wiring",
    ),
    FoundryPathPattern(
        "infra/modules/shared-foundry-rbac.bicep",
        "foundry_rbac",
        "Shared Foundry invocation RBAC for PR application identities",
    ),
)

_DEPLOY_FOUNDRY_ENV_RE = re.compile(
    r"""
    ^\s*
    param\s+deployFoundry\s*=\s*
    bool\s*\(\s*
    readEnvironmentVariable\s*\(\s*
    (?P<quote>['"])DEPLOY_FOUNDRY(?P=quote)\s*,\s*
    (?P<default_quote>['"])(?:true|false)(?P=default_quote)\s*
    \)\s*
    \)\s*
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
_MAIN_BICEP_PARAM_RE = re.compile(r"\bparam\s+deployFoundry\s+bool\b")
_MAIN_BICEP_MODULE_WIRING_RE = re.compile(r"\bdeployFoundry\s*:\s*deployFoundry\b")


def _sanitize_log(value: str) -> str:
    return "".join(
        character if character >= " " and character != "\x7f" else "?"
        for character in value
    )


def _normalize_pr_path(raw: str) -> str:
    normalized = raw.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _strip_line_comment(line: str) -> str:
    in_single = False
    in_double = False
    index = 0
    while index < len(line) - 1:
        character = line[index]
        if character == "'" and not in_double:
            in_single = not in_single
        elif character == '"' and not in_single:
            in_double = not in_double
        elif character == "/" and line[index + 1] == "/" and not in_single and not in_double:
            return line[:index]
        index += 1
    return line


def _strip_bicep_comments(text: str) -> str:
    return "\n".join(_strip_line_comment(line) for line in text.splitlines())


def _deploy_foundry_assignment(text: str) -> str | None:
    for line in _strip_bicep_comments(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("param deployFoundry"):
            return stripped
    return None


def _switch_reason(path: str, check: str, observed: str, rationale: str) -> dict[str, str]:
    return {
        "path": path,
        "category": "foundry_switch_integrity",
        "check": check,
        "observed": _sanitize_log(observed),
        "rationale": rationale,
    }


def _inspect_main_bicepparam(text: str) -> list[dict[str, str]]:
    assignment = _deploy_foundry_assignment(text)
    if assignment is None:
        return [
            _switch_reason(
                MAIN_BICEPPARAM_PATH,
                "deployFoundry_parameter_present",
                "<missing>",
                "deployFoundry must remain an explicit DEPLOY_FOUNDRY-driven switch",
            )
        ]
    if _DEPLOY_FOUNDRY_ENV_RE.fullmatch(assignment):
        return []
    return [
        _switch_reason(
            MAIN_BICEPPARAM_PATH,
            "deployFoundry_sources_DEPLOY_FOUNDRY",
            assignment,
            "deployFoundry must be bool(readEnvironmentVariable('DEPLOY_FOUNDRY', ...))",
        )
    ]


def _inspect_main_bicep(text: str) -> list[dict[str, str]]:
    commentless = _strip_bicep_comments(text)
    reasons: list[dict[str, str]] = []
    if _MAIN_BICEP_PARAM_RE.search(commentless) is None:
        reasons.append(
            _switch_reason(
                MAIN_BICEP_PATH,
                "deployFoundry_parameter_declared",
                "<missing>",
                "main.bicep must expose a deployFoundry bool parameter",
            )
        )
    if _MAIN_BICEP_MODULE_WIRING_RE.search(commentless) is None:
        reasons.append(
            _switch_reason(
                MAIN_BICEP_PATH,
                "deployFoundry_module_wiring",
                "<missing>",
                "the Foundry module must receive deployFoundry from the root switch",
            )
        )
    return reasons


def _inspect_foundry_switches(
    normalized_paths: list[str],
    *,
    repo_root: Path,
) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    changed = set(normalized_paths)
    inspections: tuple[tuple[str, Callable[[str], list[dict[str, str]]]], ...] = (
        (MAIN_BICEPPARAM_PATH, _inspect_main_bicepparam),
        (MAIN_BICEP_PATH, _inspect_main_bicep),
    )
    for relative_path, inspector in inspections:
        if relative_path not in changed:
            continue
        full_path = repo_root / Path(*relative_path.split("/"))
        text = full_path.read_text(encoding="utf-8")
        reasons.extend(inspector(text))
    return reasons


def evaluate(
    changed_paths: list[str],
    labels: list[str],
    *,
    repo_root: Path | None = None,
) -> FoundryScope:
    normalized_paths = [
        path for path in (_normalize_pr_path(raw) for raw in changed_paths) if path
    ]
    label_set = set(labels)

    matched_paths: list[dict[str, str]] = []
    for path in normalized_paths:
        for pattern in FOUNDRY_PATH_PATTERNS:
            if pattern.matches(path):
                matched_paths.append(
                    {
                        "path": path,
                        "pattern": pattern.pattern,
                        "category": pattern.category,
                        "rationale": pattern.rationale,
                    }
                )
                break

    requires_labels = (
        [REQUIRES_FOUNDRY_LABEL] if REQUIRES_FOUNDRY_LABEL in label_set else []
    )
    live_labels = [LIVE_VALIDATION_LABEL] if LIVE_VALIDATION_LABEL in label_set else []
    switch_integrity = _inspect_foundry_switches(
        normalized_paths,
        repo_root=Path.cwd() if repo_root is None else repo_root,
    )

    requires_foundry = bool(matched_paths or requires_labels or switch_integrity)
    live_validation_requested = bool(live_labels)

    return FoundryScope(
        requires_foundry=requires_foundry,
        live_validation_requested=live_validation_requested,
        reasons={
            "requires_foundry": {
                "paths": matched_paths,
                "labels": requires_labels,
                "switch_integrity": switch_integrity,
            },
            "live_validation_requested": {
                "labels": live_labels,
            },
        },
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr_foundry_scope",
        description=(
            "Detect whether PR metadata requires the Foundry exception gate and/or "
            "requests labelled live Foundry validation. Exits 3 on malformed input."
        ),
    )
    parser.add_argument(
        "--changed-paths-file",
        required=True,
        help="newline-delimited PR changed paths, one path per line",
    )
    parser.add_argument(
        "--labels-file",
        required=True,
        help="JSON array of GitHub label name strings",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help=(
            "repository root to inspect for content-aware Foundry switch checks "
            "(defaults to the current working directory)"
        ),
    )
    parser.add_argument(
        "--format",
        choices=("github", "json"),
        required=True,
        help="github emits GITHUB_OUTPUT key=value lines; json emits audit payload",
    )
    return parser.parse_args(argv)


def _read_changed_paths(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines()


def _read_labels(path: str) -> list[str]:
    raw = Path(path).read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or any(not isinstance(label, str) for label in parsed):
        raise ValueError("--labels-file must be a JSON array of label name strings")
    return parsed


def _fail_malformed(message: str, output_format: str) -> int:
    safe = _sanitize_log(message)
    if output_format == "json":
        print(json.dumps({"error": safe}, sort_keys=True))
    else:
        print(f"error={safe}")
    return MALFORMED_INPUT_EXIT_CODE


def _emit(scope: FoundryScope, output_format: str) -> None:
    if output_format == "json":
        print(
            json.dumps(
                {
                    "requires_foundry": scope.requires_foundry,
                    "live_validation_requested": scope.live_validation_requested,
                    "reasons": scope.reasons,
                },
                sort_keys=True,
            )
        )
        return

    print(f"requires_foundry={str(scope.requires_foundry).lower()}")
    print(f"live_validation_requested={str(scope.live_validation_requested).lower()}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    try:
        changed_paths = _read_changed_paths(args.changed_paths_file)
        labels = _read_labels(args.labels_file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        return _fail_malformed(f"malformed input: {error}", args.format)

    try:
        scope = evaluate(changed_paths, labels, repo_root=Path(args.repo_root))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        return _fail_malformed(f"malformed switch-integrity input: {error}", args.format)
    _emit(scope, args.format)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
