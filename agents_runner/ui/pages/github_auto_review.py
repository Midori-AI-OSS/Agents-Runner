from __future__ import annotations

from collections.abc import Callable
import threading
import time
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import cast

from agents_runner.environments import Environment
from agents_runner.gh.automation_policy import resolve_effective_auto_reactions_enabled
from agents_runner.gh.automation_policy import resolve_effective_auto_review_enabled
from agents_runner.gh.automation_policy import resolve_effective_inactive_filter_enabled
from agents_runner.gh.automation_policy import resolve_effective_inactive_max_age_days
from agents_runner.gh.polling_state import PollingStateStore
from agents_runner.gh.work_items import GitHubComment
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import add_issue_comment_reaction
from agents_runner.gh.work_items import add_issue_reaction
from agents_runner.gh.work_items import add_pull_request_review_comment_reaction
from agents_runner.gh.work_items import add_pull_request_review_reaction
from agents_runner.gh.work_items import has_issue_reaction
from agents_runner.gh.work_items import has_pull_request_review_reaction
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_pull_request_review_comments
from agents_runner.gh.work_items import list_pull_request_reviews
from agents_runner.prompts.github_prompting import has_agentsnova_mention
from agents_runner.ui.pages.github_trust import effective_trusted_users
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)
_THREAD_SCAN_LIMIT = 300


def parse_iso_timestamp_s(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return float(parsed.timestamp())
    except Exception:
        return None


def mention_item_key(*, repo_owner: str, repo_name: str, item_type: str, number: int) -> str:
    try:
        normalized_number = max(0, int(number))
    except Exception:
        normalized_number = 0
    return (
        f"{str(repo_owner or '').strip().lower()}/{str(repo_name or '').strip().lower()}:"
        f"{str(item_type or '').strip().lower()}:{normalized_number}"
    )


class AutoReviewCollector:
    def __init__(
        self,
        *,
        store: PollingStateStore | None,
        settings_provider: Callable[[], dict[str, object]],
        environments_provider: Callable[[], dict[str, Environment]],
    ) -> None:
        self.store = store
        self.settings_provider = settings_provider
        self.environments_provider = environments_provider
        self._lock = threading.Lock()
        self.seen_mentions: set[str] = set()
        self.emit_keys: set[str] = set()
        self.warned_keys: set[str] = set()
        self.eyes_blocked: dict[str, float] = {}
        self.pending_by_item: dict[str, set[str]] = {}

    def _warn_once(self, *, key: str, message: str) -> None:
        with self._lock:
            if key in self.warned_keys:
                return
            self.warned_keys.add(key)
        logger.rprint(message, mode="warn")

    def seed_from_store(self, *, now_epoch: float) -> None:
        if self.store is None:
            return
        try:
            self.store.release_stale_reservations(now_epoch=now_epoch, ttl_s=86400.0)
        except Exception as exc:
            self._warn_once(key="store_seed_release", message=f"[github-auto-review] polling state seed failed: {exc}")
        try:
            mentions = self.store.list_processed_mentions()
            with self._lock:
                self.seen_mentions.update(row.mention_key for row in mentions)
                self.emit_keys.update(row.emit_key for row in mentions)
        except Exception as exc:
            self._warn_once(key="store_seed_mentions", message=f"[github-auto-review] polling state seed failed: {exc}")
        try:
            anchors = self.store.list_pending_anchors()
            with self._lock:
                for anchor in anchors:
                    self.eyes_blocked[anchor.mention_key] = anchor.blocked_since_epoch
                    item_key = mention_item_key(
                        repo_owner=anchor.repo.split("/", 1)[0],
                        repo_name=anchor.repo.split("/", 1)[1] if "/" in anchor.repo else "",
                        item_type=anchor.item_type,
                        number=anchor.number,
                    )
                    self.pending_by_item.setdefault(item_key, set()).add(anchor.mention_key)
        except Exception as exc:
            self._warn_once(key="store_seed_anchors", message=f"[github-auto-review] polling state seed failed: {exc}")

    def _drop_pending_index(self, mention_key: str) -> None:
        for item_key, mentions in list(self.pending_by_item.items()):
            mentions.discard(mention_key)
            if not mentions:
                self.pending_by_item.pop(item_key, None)

    def emit_decision(
        self,
        *,
        emit_key: str,
        mention_key: str,
        repo_slug: str,
        item_type: str,
        number: int,
        item_key: str,
        is_item_active: Callable[[str], bool],
        now_epoch: float,
    ) -> bool:
        with self._lock:
            was_blocked = mention_key in self.eyes_blocked
            if mention_key in self.seen_mentions:
                if was_blocked:
                    self.eyes_blocked.pop(mention_key, None)
                    self._drop_pending_index(mention_key)
                    if is_item_active(item_key):
                        return False
                    self.seen_mentions.discard(mention_key)
                    self.emit_keys.discard(emit_key)
                else:
                    return False
            elif was_blocked:
                self.eyes_blocked.pop(mention_key, None)
                self._drop_pending_index(mention_key)
                if is_item_active(item_key):
                    return False
            if emit_key in self.emit_keys:
                return False
            self.seen_mentions.add(mention_key)
            self.emit_keys.add(emit_key)
            removed_pending = was_blocked
        if removed_pending and self.store is not None:
            try:
                self.store.remove_pending_anchor(mention_key)
            except Exception as exc:
                self._warn_once(
                    key="store_remove_anchor", message=f"[github-auto-review] polling state update failed: {exc}"
                )
        if self.store is not None:
            try:
                reserved = self.store.reserve_mention(
                    emit_key=emit_key,
                    mention_key=mention_key,
                    repo=repo_slug,
                    item_type=item_type,
                    number=number,
                    now_epoch=now_epoch,
                )
            except Exception as exc:
                self._warn_once(key="store_reserve", message=f"[github-auto-review] polling state update failed: {exc}")
                return True
            if not reserved:
                return False
        return True

    def collect(
        self,
        *,
        env: Environment | None,
        repo_owner: str,
        repo_name: str,
        items: list[GitHubWorkItem],
    ) -> list[dict[str, object]]:
        settings = self.settings_provider()
        repo_slug = f"{repo_owner}/{repo_name}"
        now_epoch = time.time()
        filter_enabled = resolve_effective_inactive_filter_enabled(settings=settings, env=env)
        max_age_s = resolve_effective_inactive_max_age_days(settings=settings, env=env) * 86400
        for item in items:
            updated_at = str(getattr(item, "updated_at", "") or "")
            created_at = str(getattr(item, "created_at", "") or "")
            if self.store is not None:
                try:
                    self.store.record_observation(
                        repo=repo_slug,
                        item_type=item.item_type,
                        number=item.number,
                        activity_iso=updated_at or created_at,
                        now_epoch=now_epoch,
                    )
                except Exception as exc:
                    self._warn_once(
                        key="store_observation",
                        message=f"[github-auto-review] polling state observation failed: {exc}",
                    )
        if not resolve_effective_auto_review_enabled(settings=settings, env=env):
            return []
        trusted_users = effective_trusted_users(
            global_usernames=cast(Any, settings.get("agentsnova_trusted_users_global", [])), env=env
        )
        if not trusted_users:
            return []
        auto_reactions_enabled = resolve_effective_auto_reactions_enabled(settings=settings, env=env)
        with self._lock:
            queued_snapshot = set(self.seen_mentions) - set(self.eyes_blocked)

        results: list[dict[str, object]] = []
        for item in items:
            item_key = mention_item_key(
                repo_owner=repo_owner, repo_name=repo_name, item_type=item.item_type, number=item.number
            )
            updated_at = str(getattr(item, "updated_at", "") or "")
            created_at = str(getattr(item, "created_at", "") or "")
            activity_epoch = parse_iso_timestamp_s(updated_at)
            if activity_epoch is None:
                activity_epoch = parse_iso_timestamp_s(created_at)
            with self._lock:
                has_pending = bool(self.pending_by_item.get(item_key))
            if (
                filter_enabled
                and activity_epoch is not None
                and now_epoch - activity_epoch > max_age_s
                and not has_pending
            ):
                continue

            pr_head_ref = str(getattr(item, "head_ref", "") or "")
            pr_base_ref = str(getattr(item, "base_ref", "") or "")
            pr_head_repo_owner = str(getattr(item, "head_repo_owner", "") or "")
            pr_head_repo_name = str(getattr(item, "head_repo_name", "") or "")
            pr_is_cross_repo = bool(getattr(item, "is_cross_repo", False))
            comments = list_issue_comments(
                repo_owner, repo_name, issue_number=item.number, limit=_THREAD_SCAN_LIMIT, newest_first=True
            )
            candidates: list[dict[str, object]] = []

            def add_comment_candidate(comment: GitHubComment, *, source: str) -> None:
                author = str(comment.author or "").strip().lower()
                if not author or author not in trusted_users or not has_agentsnova_mention(comment.body):
                    return
                created = str(comment.created_at or "")
                candidates.append(
                    {
                        "source": source,
                        "mention_key": f"{source}:{comment.comment_id}",
                        "mention_text": str(comment.body or ""),
                        "mention_author": str(comment.author or ""),
                        "mention_created_at": created,
                        "mention_url": str(comment.url or ""),
                        "created_at_s": parse_iso_timestamp_s(created) or 0.0,
                        "sort_id": comment.comment_id,
                        "comment": comment,
                        "anchor_id": comment.comment_id,
                    }
                )

            for comment in comments:
                add_comment_candidate(comment, source="issue_comment")
            if item.item_type == "pr":
                for comment in list_pull_request_review_comments(
                    repo_owner, repo_name, pull_number=item.number, limit=_THREAD_SCAN_LIMIT, newest_first=True
                ):
                    add_comment_candidate(comment, source="review_comment")
                for review in list_pull_request_reviews(
                    repo_owner, repo_name, pull_number=item.number, limit=_THREAD_SCAN_LIMIT, newest_first=True
                ):
                    author = str(review.author or "").strip().lower()
                    if not author or author not in trusted_users or not has_agentsnova_mention(review.body):
                        continue
                    created = str(review.submitted_at or "")
                    candidates.append(
                        {
                            "source": "review_body",
                            "mention_key": f"review_body:{review.review_id}",
                            "mention_text": str(review.body or ""),
                            "mention_author": str(review.author or ""),
                            "mention_created_at": created,
                            "mention_url": str(review.url or ""),
                            "created_at_s": parse_iso_timestamp_s(created) or 0.0,
                            "sort_id": review.review_id,
                            "anchor_id": review.review_id,
                        }
                    )
            body_text = str(getattr(item, "body", "") or "")
            title_text = str(getattr(item, "title", "") or "")
            body_has_mention = has_agentsnova_mention(body_text)
            title_has_mention = has_agentsnova_mention(title_text)
            author = str(getattr(item, "author", "") or "").strip().lower()
            if (body_has_mention or title_has_mention) and author in trusted_users:
                mention_created_at = updated_at or created_at
                source = "pr_body" if item.item_type == "pr" else "issue_body"
                candidates.append(
                    {
                        "source": source,
                        "mention_key": f"{source}:{item_key}",
                        "mention_text": body_text if body_has_mention else title_text,
                        "mention_author": str(getattr(item, "author", "") or ""),
                        "mention_created_at": mention_created_at,
                        "mention_url": str(item.url or ""),
                        "created_at_s": parse_iso_timestamp_s(mention_created_at) or 0.0,
                        "sort_id": item.number,
                        "anchor_id": item.number,
                    }
                )
            ordered = sorted(
                candidates,
                key=lambda candidate: (
                    float(cast(Any, candidate.get("created_at_s", 0.0) or 0.0)),
                    int(cast(Any, candidate.get("sort_id", 0) or 0)),
                ),
                reverse=True,
            )
            for candidate in ordered:
                mention_key = str(candidate.get("mention_key") or "").strip()
                if not mention_key or mention_key in queued_snapshot:
                    continue
                source = str(candidate.get("source") or "").strip().lower()
                try:
                    eyes = self._anchor_has_any_eyes(
                        repo_owner, repo_name, item.number, source, candidate.get("anchor_id"), candidate.get("comment")
                    )
                except Exception as exc:
                    self._warn_once(
                        key="auto_review_read_eyes_failed",
                        message=f"[github-auto-review] skipped auto-start scans: failed to read eyes reaction anchors. first_error={exc}",
                    )
                    continue
                if eyes:
                    with self._lock:
                        self.eyes_blocked[mention_key] = time.time()
                        self.pending_by_item.setdefault(item_key, set()).add(mention_key)
                    if self.store is not None:
                        try:
                            self.store.set_pending_anchor(
                                mention_key=mention_key,
                                repo=repo_slug,
                                item_type=item.item_type,
                                number=item.number,
                                now_epoch=time.time(),
                            )
                        except Exception as exc:
                            self._warn_once(
                                key="store_set_anchor",
                                message=f"[github-auto-review] polling state update failed: {exc}",
                            )
                    continue
                if auto_reactions_enabled:
                    try:
                        self._add_anchor_eyes_reaction(
                            repo_owner, repo_name, item.number, source, candidate.get("anchor_id")
                        )
                    except Exception as exc:
                        self._warn_once(
                            key="auto_review_add_eyes_failed",
                            message=f"[github-auto-review] failed to add eyes reactions during auto-start scans. first_error={exc}",
                        )
                results.append(
                    {
                        "item_type": item.item_type,
                        "number": item.number,
                        "url": item.url,
                        "title": item.title,
                        "pr_head_ref": pr_head_ref,
                        "pr_base_ref": pr_base_ref,
                        "pr_head_repo_owner": pr_head_repo_owner,
                        "pr_head_repo_name": pr_head_repo_name,
                        "pr_is_cross_repo": pr_is_cross_repo,
                        "mention_key": mention_key,
                        "trigger_source": source,
                        "mention_text": candidate.get("mention_text", ""),
                        "mention_author": candidate.get("mention_author", ""),
                        "mention_created_at": candidate.get("mention_created_at", ""),
                        "mention_url": candidate.get("mention_url", ""),
                        "item_key": item_key,
                    }
                )
                queued_snapshot.add(mention_key)
                if len(results) >= 3:
                    return results
                break
        return results

    @staticmethod
    def _safe_positive_int(value: object) -> int:
        try:
            parsed = int(cast(Any, value or 0))
        except Exception:
            return 0
        return parsed if parsed > 0 else 0

    def _anchor_has_any_eyes(
        self,
        repo_owner: str,
        repo_name: str,
        item_number: int,
        source: str,
        anchor_id: object,
        candidate_comment: object | None,
    ) -> bool:
        if source in {"issue_comment", "review_comment"}:
            if not isinstance(candidate_comment, GitHubComment):
                raise ValueError("missing comment candidate")
            return candidate_comment.reactions.eyes > 0
        if source == "review_body":
            review_id = self._safe_positive_int(anchor_id)
            if review_id <= 0:
                raise ValueError("invalid review anchor id")
            return has_pull_request_review_reaction(
                repo_owner, repo_name, pull_number=item_number, review_id=review_id, reaction="eyes"
            )
        if source in {"pr_body", "issue_body"}:
            return has_issue_reaction(repo_owner, repo_name, issue_number=item_number, reaction="eyes")
        raise ValueError(f"unsupported mention source: {source}")

    def _add_anchor_eyes_reaction(
        self, repo_owner: str, repo_name: str, item_number: int, source: str, anchor_id: object
    ) -> None:
        anchor = self._safe_positive_int(anchor_id)
        if anchor <= 0:
            raise ValueError("invalid reaction anchor id")
        if source == "issue_comment":
            add_issue_comment_reaction(repo_owner, repo_name, comment_id=anchor, reaction="eyes")
        elif source == "review_comment":
            add_pull_request_review_comment_reaction(repo_owner, repo_name, comment_id=anchor, reaction="eyes")
        elif source == "review_body":
            add_pull_request_review_reaction(
                repo_owner, repo_name, pull_number=item_number, review_id=anchor, reaction="eyes"
            )
        elif source in {"pr_body", "issue_body"}:
            add_issue_reaction(repo_owner, repo_name, issue_number=item_number, reaction="eyes")
        else:
            raise ValueError(f"unsupported mention source: {source}")
