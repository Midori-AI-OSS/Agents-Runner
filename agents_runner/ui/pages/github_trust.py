from __future__ import annotations

from typing import Iterable

from agents_runner.environments import Environment
from agents_runner.environments import WORKSPACE_CLONED
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.gh.work_items import get_authenticated_github_login
from agents_runner.gh.work_items import list_org_members


TRUST_MODE_INHERIT = "inherit"
TRUST_MODE_ADDITIVE = "additive"
TRUST_MODE_REPLACE = "replace"


def normalize_github_username(value: object) -> str:
    username = str(value or "").strip().lstrip("@").lower()
    return username


def normalize_github_usernames(values: Iterable[object]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        username = normalize_github_username(raw)
        if not username or username in seen:
            continue
        cleaned.append(username)
        seen.add(username)
    return cleaned


def normalize_trusted_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    if mode in {TRUST_MODE_ADDITIVE, TRUST_MODE_REPLACE}:
        return mode
    return TRUST_MODE_INHERIT


def effective_trusted_users(
    *,
    global_usernames: Iterable[object],
    env: Environment | None,
) -> set[str]:
    global_set = set(normalize_github_usernames(global_usernames))
    if env is None:
        return global_set

    env_list = normalize_github_usernames(
        getattr(env, "agentsnova_trusted_users_env", []) or []
    )
    env_set = set(env_list)
    mode = normalize_trusted_mode(getattr(env, "agentsnova_trusted_mode", "inherit"))
    if mode == TRUST_MODE_REPLACE:
        return env_set
    if mode == TRUST_MODE_ADDITIVE:
        return global_set | env_set
    return global_set


def collect_seed_usernames_for_environment(env: Environment | None) -> list[str]:
    seeded: list[str] = []

    current_login = normalize_github_username(get_authenticated_github_login())
    if current_login:
        seeded.append(current_login)

    if env is None:
        return normalize_github_usernames(seeded)

    context = resolve_environment_github_repo(env)
    if context is None:
        return normalize_github_usernames(seeded)

    owner = normalize_github_username(context.repo_owner)
    if owner:
        seeded.append(owner)
        seeded.extend(list_org_members(owner, limit=100))
    return normalize_github_usernames(seeded)


def collect_seed_usernames_for_cloned_environments(
    environments: Iterable[Environment],
) -> list[str]:
    seeded: list[str] = []

    current_login = normalize_github_username(get_authenticated_github_login())
    if current_login:
        seeded.append(current_login)

    owners: list[str] = []
    for env in environments:
        if (
            str(getattr(env, "workspace_type", "") or "").strip().lower()
            != WORKSPACE_CLONED
        ):
            continue
        context = resolve_environment_github_repo(env)
        if context is None:
            continue
        owner = normalize_github_username(context.repo_owner)
        if owner:
            owners.append(owner)

    for owner in normalize_github_usernames(owners):
        seeded.append(owner)
        seeded.extend(list_org_members(owner, limit=100))
    return normalize_github_usernames(seeded)
