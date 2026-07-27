"""Deterministic naming for per-PR ephemeral Azure environments (Phase 1).

This module is pure, standard-library-only logic. It performs NO Azure calls,
reads NO credentials, and emits nothing sensitive. Given a repository slug, a
GitHub pull-request number, and the PR head branch, it produces a stable set of
Azure resource names that respect each service's hard character limits.

Naming scheme (from docs/design/pr-ephemeral-environments.md on the design
branch): the ``azd`` environment name is ``pr-{number}-{slug}-{hash8}`` where

* ``number`` is the GitHub PR number,
* ``slug`` is the sanitized slug derived from the stable branch convention
  ``squad/{issue}-{slug}`` (lowercase letters, digits, hyphens; collapsed
  separators; trimmed), and
* ``hash8`` is the first 8 lowercase hex chars of
  ``sha256("{repo}|{prNumber}|{slug}")``.

API CONTRACT for ``hash8``: ``repo`` MUST be the canonical GitHub
``owner/repo`` form (e.g. ``bmoussaud/squad-workshop``). The design doc left
this ambiguous, which is precisely why five different candidate hashes exist for
PR #14; this module pins the ``owner/repo`` form so the output is deterministic.

KNOWN DISCREPANCY: the design doc's worked example claims
``hash8 == "4717e5bb"`` for PR #14, but that value is NOT reproducible from the
doc's own stated rule under ANY plausible ``repo`` reading (verified: owner/repo
-> ``4c32c628``, bare name -> ``fff13584``, full URL -> ``2ccebd61``, host/path
-> ``bc96ea57``, branch-as-repo -> ``c9ca5700``). This module implements the
rule AS SPECIFIED; ``4c32c628`` is the correct output for the canonical
``owner/repo`` input. A human must adjudicate whether the doc gets corrected.
The doc's other two example values (storage 16 chars, container app 23 chars)
are internally consistent shapes -- only the hash substring is wrong.

Every generator fails loudly (``ValueError``) rather than silently emitting a
name that violates an Azure limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass, field

# --- Azure service hard limits -------------------------------------------------
# The values below are the AUTHORITATIVE, doc-cited limits (learn.microsoft.com
# resource-name-rules) unless annotated otherwise.
STORAGE_MAX = 24
STORAGE_MIN = 3
# Container Apps: length 2-32, lowercase alphanumeric and hyphens, must START
# with a letter and END with an alphanumeric character.
CONTAINER_APP_MAX = 32
CONTAINER_APP_MIN = 2
RESOURCE_GROUP_MAX = 90
MANAGED_IDENTITY_MAX = 128
APPLICATION_INSIGHTS_MAX = 260
ACTION_GROUP_MAX = 260
BUDGET_MAX = 63
ACR_MIN = 5
ACR_MAX = 50
# Virtual Network name: length 2-64, alphanumerics, hyphens, underscores and
# periods; must start with an alphanumeric. Our generated names use only
# ``[a-z0-9-]`` and always start with a letter, so they satisfy the rule; we
# assert the length ceiling defensively.
VIRTUAL_NETWORK_MAX = 64
# UNVERIFIED: the Container Apps *managed environment* max length is NOT
# published (the ARM reference gives only the character pattern, no length), and
# ``azd`` publishes no documented length limit on environment names either. We
# do NOT assert an authoritative Azure limit for these; instead we apply the
# same defensive compaction fallback we use elsewhere, using this conservative
# self-imposed ceiling so a pathological name can never silently balloon.
MANAGED_ENVIRONMENT_DEFENSIVE_MAX = 32

# Compact fixed application prefix used inside per-resource names.
APP_PREFIX = "fc"

_BRANCH_RE = re.compile(r"^squad/(?P<issue>[1-9][0-9]*)-(?P<slug>.+)$")
_SLUG_ALLOWED_RE = re.compile(r"[^a-z0-9-]+")
_HYPHEN_RUN_RE = re.compile(r"-{2,}")
_ACR_RE = re.compile(r"^[a-zA-Z0-9]+$")
# Container App: start with a letter, end with an alphanumeric, lowercase
# alphanumeric and hyphens in between.
_CONTAINER_APP_RE = re.compile(r"^[a-z][a-z0-9-]*[a-z0-9]$")
# Any control character (newlines, carriage returns, ANSI ESC, NUL, DEL). These
# are the log-injection primitives: a real newline lets attacker-controlled
# input open a fresh log line that could start a GitHub Actions workflow command
# (``::error``, ``::set-output``) or corrupt a multi-line ``$GITHUB_OUTPUT``
# value. Every string this module PRINTS is passed through ``_sanitize_log``.
_LOG_UNSAFE_RE = re.compile(r"[\x00-\x1f\x7f]")


def _sanitize_log(text: str) -> str:
    """Neutralize any control character so printed text can never inject a new
    log line or a GitHub Actions workflow command.

    Branch names are fully attacker-controlled on fork PRs, so any value that
    could be echoed (including inside an error message) is collapsed to a single
    safe line before it reaches stdout/stderr.
    """
    return _LOG_UNSAFE_RE.sub(" ", text)


def slug_from_branch(branch: str) -> str:
    """Extract and sanitize the meaningful slug from a ``squad/{issue}-{slug}`` branch.

    Raises ``ValueError`` for any branch that does not follow the convention or
    that yields an empty slug after sanitization.
    """
    if not isinstance(branch, str) or not branch.strip():
        raise ValueError("branch must be a non-empty string")
    match = _BRANCH_RE.match(branch.strip())
    if match is None:
        raise ValueError(
            f"branch {branch!r} does not follow the required "
            "'squad/{issue}-{slug}' convention"
        )
    return sanitize_slug(match.group("slug"))


def sanitize_slug(raw: str) -> str:
    """Lowercase, restrict to ``[a-z0-9-]``, collapse and trim hyphens.

    Raises ``ValueError`` if nothing meaningful remains.
    """
    lowered = raw.strip().lower()
    replaced = _SLUG_ALLOWED_RE.sub("-", lowered)
    collapsed = _HYPHEN_RUN_RE.sub("-", replaced)
    slug = collapsed.strip("-")
    if not slug:
        raise ValueError(f"slug {raw!r} is empty after sanitization")
    return slug


def hash8(repo: str, pr_number: int, slug: str) -> str:
    """First 8 lowercase hex chars of ``sha256("{repo}|{prNumber}|{slug}")``.

    The exact hashed input format is ``repo|prNumber|slug`` with a single ASCII
    pipe separator and no surrounding whitespace. ``repo`` MUST be the canonical
    GitHub ``owner/repo`` form (e.g. ``bmoussaud/squad-workshop``); this is a
    documented part of the contract because the design doc's ambiguity about the
    repo form produced five different candidate hashes. Callers must not pass a
    bare repo name, a URL, or a host/path form.
    """
    if not isinstance(repo, str) or not repo:
        raise ValueError("repo must be a non-empty string")
    _validate_pr_number(pr_number)
    if not slug:
        raise ValueError("slug must be a non-empty string")
    payload = f"{repo}|{pr_number}|{slug}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def _validate_pr_number(pr_number: int) -> None:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int):
        raise ValueError("pr_number must be an integer")
    if pr_number <= 0:
        raise ValueError("pr_number must be a positive integer")


def environment_name(pr_number: int, slug: str, digest: str) -> str:
    """The human-readable, stable ``azd`` environment name."""
    _validate_pr_number(pr_number)
    return f"pr-{pr_number}-{slug}-{digest}"


def storage_account_name(pr_number: int, digest: str) -> str:
    """``stfcpr{number}{hash8}`` -- lowercase alnum only, length 3-24.

    Only the numeric PR token is truncated (keeping its leading digits) if the
    account name would otherwise exceed 24 chars; ``hash8`` is always preserved.
    """
    _validate_pr_number(pr_number)
    prefix = f"st{APP_PREFIX}pr"
    fixed = len(prefix) + len(digest)
    budget = STORAGE_MAX - fixed
    if budget < 1:
        raise ValueError(
            "storage account name cannot fit the required hash8 within 24 chars"
        )
    number_token = str(pr_number)[:budget]
    name = f"{prefix}{number_token}{digest}"
    if not (STORAGE_MIN <= len(name) <= STORAGE_MAX):
        raise ValueError(f"generated storage account name {name!r} violates length 3-24")
    if not name.isalnum() or not name.islower():
        raise ValueError(
            f"generated storage account name {name!r} is not lowercase alnum"
        )
    return name


def _slug_words(slug: str) -> list[str]:
    return [word for word in slug.split("-") if word]


def container_app_name(pr_number: int, slug: str, digest: str) -> str:
    """``ca-fc-pr{number}-{slugCompact}-{hash8}`` -- length 2-32.

    ``slugCompact`` is the acronym formed from the first character of each slug
    word, taken left to right only as far as the full name stays within 32
    chars. Long slugs are therefore compacted (never overflowing the limit).

    Enforces the full Container Apps naming rule: length 2-32, lowercase
    alphanumeric and hyphens only, MUST start with a letter and end with an
    alphanumeric character (so no trailing-hyphen or empty-token artifact).
    """
    _validate_pr_number(pr_number)
    prefix = f"ca-{APP_PREFIX}-pr{pr_number}-"
    suffix = f"-{digest}"
    budget = CONTAINER_APP_MAX - len(prefix) - len(suffix)
    if budget < 1:
        raise ValueError(
            "container app name cannot fit any slug token within 32 chars for "
            f"PR #{pr_number}"
        )
    acronym = "".join(word[0] for word in _slug_words(slug))
    if not acronym:
        raise ValueError(f"slug {slug!r} produced an empty acronym")
    slug_compact = acronym[:budget]
    name = f"{prefix}{slug_compact}{suffix}"
    _validate_container_app_name(name)
    return name


def _validate_container_app_name(name: str) -> None:
    """Fail loudly unless ``name`` satisfies every Container Apps naming rule."""
    if not (CONTAINER_APP_MIN <= len(name) <= CONTAINER_APP_MAX):
        raise ValueError(
            f"generated container app name {name!r} violates length "
            f"{CONTAINER_APP_MIN}-{CONTAINER_APP_MAX}"
        )
    if _CONTAINER_APP_RE.match(name) is None:
        raise ValueError(
            f"generated container app name {name!r} must be lowercase "
            "alphanumeric/hyphen, start with a letter and end with an "
            "alphanumeric character"
        )


def _compact_or_full(full: str, limit: int, pr_number: int, digest: str) -> str:
    """Return the full environment name when it fits ``limit``; otherwise fall
    back to the ``pr{number}-{hash8}`` compaction (truncating the PR token only
    if even that overflows, always preserving ``hash8``)."""
    if len(full) <= limit:
        return full
    prefix = "pr"
    suffix = f"-{digest}"
    budget = limit - len(prefix) - len(suffix)
    if budget < 1:
        raise ValueError(
            f"cannot compact name within {limit} chars while preserving hash8"
        )
    number_token = str(pr_number)[:budget]
    return f"{prefix}{number_token}{suffix}"


def is_valid_acr_name(name: str) -> bool:
    """Validate a *referenced* Azure Container Registry name (alnum, length 5-50).

    PR environments never create a registry; they reference the shared ACR, so
    this validates an existing name rather than generating one.
    """
    return (
        isinstance(name, str)
        and ACR_MIN <= len(name) <= ACR_MAX
        and _ACR_RE.match(name) is not None
    )


def virtual_network_name(managed_environment: str) -> str:
    """``vnet-{managed_environment}-private`` -- length 2-64.

    The private app-tier VNet name is anchored to the already-compacted
    ``managed_environment`` token (<= 32 chars) rather than to the raw ``azd``
    environment name. That is deliberate: ``infra/web.bicep`` previously built
    ``vnet-fantasy-cards-{environmentName}-private``, which reaches 65 chars for
    a real PR (``pr-26-relax-ci-ownership-gate-8ba70a79``) and overflows the
    64-char VNet limit. Deriving from the bounded managed-environment token
    keeps the name <= 45 chars for any input, so it can never overflow.
    """
    if not managed_environment:
        raise ValueError("managed_environment must be a non-empty string")
    name = f"vnet-{managed_environment}-private"
    if not (2 <= len(name) <= VIRTUAL_NETWORK_MAX):
        raise ValueError(
            f"generated virtual network name {name!r} violates length "
            f"2-{VIRTUAL_NETWORK_MAX}"
        )
    return name


# --- CLI -> bicepparam env-var contract ---------------------------------------
# The single, authoritative mapping between the log-safe JSON/env keys this
# module emits (see PrEnvironmentNames.printable_fields) and the environment
# variable names that infra/main.bicepparam reads via readEnvironmentVariable.
# Phase 3 work item B (the GitHub Actions workflow) MUST export exactly these
# variable names before ``azd provision`` so the PR-safe names reach Bicep; the
# ``--format envvars`` output emits precisely this mapping to remove
# hand-transcription risk. Only names owned by this module AND consumed by
# main.bicepparam appear here; identity names (PLATFORM_IDENTITY_NAME /
# APPLICATION_IDENTITY_NAME) are intentionally left to work item B because a
# single managed_identity token does not map cleanly onto the two identity
# parameters.
BICEPPARAM_ENV_VARS: dict[str, str] = {
    "environment_name": "AZURE_ENV_NAME",
    "storage_account": "STORAGE_ACCOUNT_NAME",
    "container_app": "CONTAINER_APP_NAME",
    "managed_environment": "CONTAINER_APPS_ENVIRONMENT_NAME",
    "virtual_network": "VIRTUAL_NETWORK_NAME",
    "application_insights": "APPLICATION_INSIGHTS_NAME",
}


@dataclass(frozen=True)
class PrEnvironmentNames:
    """The full set of deterministic names for one per-PR environment."""

    # ``repo`` is part of the in-process identity record but is kept out of the
    # dataclass repr and out of every printable projection: it is not a
    # generated Azure name and must never be echoed into CI logs or PR comments.
    repo: str = field(repr=False)
    pr_number: int
    slug: str
    hash8: str
    environment_name: str
    resource_group: str
    storage_account: str
    container_app: str
    managed_environment: str
    virtual_network: str
    managed_identity: str
    application_insights: str
    action_group: str
    budget: str

    def as_dict(self) -> dict[str, object]:
        """Full record for in-process callers (includes ``repo``).

        This is NOT the log/CI surface -- use :meth:`printable_fields` for
        anything that gets printed. Callers that build resource tags read
        ``repo`` directly from this record; they must never print it verbatim.
        """
        return asdict(self)

    def printable_fields(self) -> dict[str, str]:
        """The log-safe projection emitted by the CLI (no ``repo``).

        Only generated Azure names appear here, every one of which is
        constrained to ``[a-z0-9-]`` (plus fixed prefixes), so no value can carry
        a newline, ANSI escape, or workflow-command marker.
        """
        return {
            "environment_name": self.environment_name,
            "slug": self.slug,
            "hash8": self.hash8,
            "resource_group": self.resource_group,
            "storage_account": self.storage_account,
            "container_app": self.container_app,
            "managed_environment": self.managed_environment,
            "virtual_network": self.virtual_network,
            "managed_identity": self.managed_identity,
            "application_insights": self.application_insights,
            "action_group": self.action_group,
            "budget": self.budget,
        }


def compute_names(repo: str, pr_number: int, branch: str) -> PrEnvironmentNames:
    """Compute every per-PR Azure name from ``repo``, ``pr_number`` and ``branch``.

    Raises ``ValueError`` on any invalid input or if a name cannot be generated
    within its Azure limit.
    """
    _validate_pr_number(pr_number)
    slug = slug_from_branch(branch)
    digest = hash8(repo, pr_number, slug)
    env = environment_name(pr_number, slug, digest)
    managed_environment = _compact_or_full(
        env, MANAGED_ENVIRONMENT_DEFENSIVE_MAX, pr_number, digest
    )
    return PrEnvironmentNames(
        repo=repo,
        pr_number=pr_number,
        slug=slug,
        hash8=digest,
        environment_name=env,
        resource_group=_compact_or_full(env, RESOURCE_GROUP_MAX, pr_number, digest),
        storage_account=storage_account_name(pr_number, digest),
        container_app=container_app_name(pr_number, slug, digest),
        managed_environment=managed_environment,
        virtual_network=virtual_network_name(managed_environment),
        managed_identity=_compact_or_full(
            env, MANAGED_IDENTITY_MAX, pr_number, digest
        ),
        application_insights=_compact_or_full(
            env, APPLICATION_INSIGHTS_MAX, pr_number, digest
        ),
        action_group=_compact_or_full(env, ACTION_GROUP_MAX, pr_number, digest),
        budget=_compact_or_full(env, BUDGET_MAX, pr_number, digest),
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pr_environment_names",
        description=(
            "Compute deterministic per-PR Azure environment names for CI. "
            "Emits key=value (GITHUB_OUTPUT-friendly) or JSON."
        ),
    )
    parser.add_argument("--repo", required=True, help="owner/name repository slug")
    parser.add_argument("--pr-number", required=True, type=int, help="GitHub PR number")
    parser.add_argument(
        "--branch",
        required=True,
        help="PR head branch (must follow squad/{issue}-{slug})",
    )
    parser.add_argument(
        "--format",
        choices=("env", "json", "envvars"),
        default="env",
        help=(
            "output format: env (name=value using this module's keys), json, or "
            "envvars (BICEPPARAM_ENV_VAR=value lines matching "
            "infra/main.bicepparam, ready to append to $GITHUB_ENV)"
        ),
    )
    return parser.parse_args(argv)


def _render_env(names: PrEnvironmentNames) -> str:
    return "\n".join(
        f"{key}={value}" for key, value in names.printable_fields().items()
    )


def _render_envvars(names: PrEnvironmentNames) -> str:
    """Emit ``BICEPPARAM_ENV_VAR=value`` lines for the Bicep name contract.

    The variable names are exactly those ``infra/main.bicepparam`` reads, so the
    workflow can append this block straight to ``$GITHUB_ENV`` without
    re-typing any name.
    """
    fields = names.printable_fields()
    return "\n".join(
        f"{env_var}={fields[key]}" for key, env_var in BICEPPARAM_ENV_VARS.items()
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        names = compute_names(args.repo, args.pr_number, args.branch)
    except ValueError as error:
        # The branch is attacker-controlled input; sanitize before printing so a
        # crafted branch name cannot inject a log line or workflow command.
        print(f"pr_environment_names: {_sanitize_log(str(error))}", file=sys.stderr)
        return 1
    if args.format == "json":
        print(json.dumps(names.printable_fields(), sort_keys=True))
    elif args.format == "envvars":
        print(_render_envvars(names))
    else:
        print(_render_env(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
