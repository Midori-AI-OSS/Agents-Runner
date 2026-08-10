from __future__ import annotations

import threading
import time

from dataclasses import dataclass
from dataclasses import replace
from datetime import datetime
from datetime import timezone

from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal

from agents_runner.environments import Environment
from agents_runner.environments import GitHubRepoContext
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.gh.work_items import GitHubComment
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import add_issue_comment_reaction
from agents_runner.gh.work_items import add_issue_reaction
from agents_runner.gh.work_items import add_pull_request_review_comment_reaction
from agents_runner.gh.work_items import add_pull_request_review_reaction
from agents_runner.gh.work_items import has_issue_reaction
from agents_runner.gh.work_items import has_pull_request_review_reaction
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_open_issues
from agents_runner.gh.work_items import list_open_pull_requests
from agents_runner.gh.rate_limiter import Priority
from agents_runner.gh.rate_limiter import push_priority
from agents_runner.gh.work_items import list_pull_request_review_comments
from agents_runner.gh.work_items import list_pull_request_reviews
from agents_runner.gh.automation_policy import (
    resolve_effective_auto_reactions_enabled,
    resolve_effective_auto_review_enabled,
)
from agents_runner.prompts import load_prompt
from agents_runner.prompts.github_prompting import build_default_request_line
from agents_runner.prompts.github_prompting import build_primary_request
from agents_runner.prompts.github_prompting import has_agentsnova_mention
from agents_runner.ui.pages.github_trust import effective_trusted_users
from midori_ai_logger import MidoriAiLogger

logger = MidoriAiLogger(channel=None, name=__name__)


@dataclass(frozen=True)
class GitHubWorkCacheEntry:
    item_type: str
    env_id: str
    items: list[GitHubWorkItem]
    repo_context: GitHubRepoContext | None
    error: str
    fetched_at: float
    expires_at: float
    refreshing: bool = False


class GitHubWorkCoordinator(QObject):
    cache_updated = Signal(str, str)
    auto_review_requested = Signal(str, object)
    task_completed = Signal(str)

    _fetch_completed = Signal(str, str, object, object, str, object)
    _cycle_finished = Signal()

    _CACHE_TTL_S = 45.0
    _AUTO_REVIEW_THREAD_SCAN_LIMIT = 300
    _COALESCE_TIMEOUT_S = 30.0

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, object] = {}
        self._settings_initialized = False
        self._environments: dict[str, Environment] = {}
        self._cache: dict[tuple[str, str], GitHubWorkCacheEntry] = {}
        self._inflight_keys: set[tuple[str, str]] = set()
        self._inflight_events: dict[tuple[str, str], threading.Event] = {}

        self._auto_review_seen_mentions: set[str] = set()
        self._auto_review_emit_keys: set[str] = set()
        self._auto_review_warned_keys: set[str] = set()

        self._eyes_blocked_anchors: dict[str, float] = {}
        self._active_task_by_item: dict[str, float] = {}

        self._state_lock = threading.Lock()
        self._poll_cycle_running = False

        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(False)
        self._poll_timer.timeout.connect(self._on_poll_timer_tick)

        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.timeout.connect(self._on_startup_timer_tick)
        self._startup_poll_started = False

        self._fetch_completed.connect(self._on_fetch_completed)
        self._cycle_finished.connect(self._on_cycle_finished)

    def set_settings_data(self, settings_data: dict[str, object]) -> None:
        previous_global_polling_enabled = self.is_global_polling_enabled() if self._settings_initialized else None
        self._settings = dict(settings_data or {})
        self._poll_timer.setInterval(self._poll_interval_s() * 1000)
        runtime_enable_requested = bool(
            self._settings_initialized and previous_global_polling_enabled is False and self.is_global_polling_enabled()
        )
        self._reconfigure_polling_timers(start_immediately=runtime_enable_requested)
        self._settings_initialized = True

    def set_environments(self, environments: dict[str, Environment]) -> None:
        self._environments = dict(environments or {})
        self._reconfigure_polling_timers()

    def get_cache_entry(self, *, item_type: str, env_id: str) -> GitHubWorkCacheEntry | None:
        key = self._cache_key(item_type=item_type, env_id=env_id)
        with self._state_lock:
            entry = self._cache.get(key)
        return entry

    def request_refresh(
        self,
        *,
        item_type: str,
        env_id: str,
        force: bool,
    ) -> None:
        normalized_env = str(env_id or "").strip()
        if not normalized_env:
            return
        normalized_type = self._normalize_item_type(item_type)
        key = self._cache_key(item_type=normalized_type, env_id=normalized_env)
        entry = self.get_cache_entry(item_type=normalized_type, env_id=normalized_env)
        now = time.time()
        if not force and entry is not None and entry.expires_at > now:
            return
        if entry is not None and entry.refreshing:
            return
        if not self._begin_fetch(key=key):
            return
        fetch_priority = Priority.HIGH if force else Priority.LOW
        threading.Thread(
            target=self._fetch_key_worker,
            args=(normalized_type, normalized_env, fetch_priority),
            daemon=True,
        ).start()

    def request_refresh_if_stale(self, *, item_type: str, env_id: str) -> None:
        normalized_env = str(env_id or "").strip()
        if not normalized_env:
            return
        normalized_type = self._normalize_item_type(item_type)
        entry = self.get_cache_entry(item_type=normalized_type, env_id=normalized_env)
        if entry is None:
            self.request_refresh(
                item_type=normalized_type,
                env_id=normalized_env,
                force=True,
            )
            return
        if entry.refreshing:
            return
        if entry.expires_at <= time.time():
            self.request_refresh(
                item_type=normalized_type,
                env_id=normalized_env,
                force=True,
            )

    def notify_task_completed(self, *, item_key: str) -> None:
        normalized = str(item_key or "").strip()
        if not normalized:
            return
        with self._state_lock:
            self._active_task_by_item.pop(normalized, None)

    def is_global_polling_enabled(self) -> bool:
        return bool(self._settings.get("github_polling_enabled") or False)

    def is_polling_effective_for_env(self, env_id: str) -> bool:
        if not self.is_global_polling_enabled():
            return False
        env = self._environments.get(str(env_id or "").strip())
        if env is None:
            return False
        return resolve_environment_github_repo(env) is not None

    def _reconfigure_polling_timers(self, *, start_immediately: bool = False) -> None:
        if not self.is_global_polling_enabled():
            self._poll_timer.stop()
            self._startup_timer.stop()
            self._startup_poll_started = False
            return

        self._poll_timer.setInterval(self._poll_interval_s() * 1000)
        if self._startup_poll_started:
            if not self._poll_timer.isActive():
                self._poll_timer.start()
            return

        if start_immediately:
            self._startup_timer.stop()
            self._startup_poll_started = True
            self._start_poll_cycle()
            if not self._poll_timer.isActive():
                self._poll_timer.start()
            return

        delay_s = self._startup_delay_s()
        if delay_s <= 0:
            self._startup_poll_started = True
            self._start_poll_cycle()
            if not self._poll_timer.isActive():
                self._poll_timer.start()
            return

        if not self._startup_timer.isActive():
            self._startup_timer.start(delay_s * 1000)

    def _on_startup_timer_tick(self) -> None:
        if not self.is_global_polling_enabled():
            return
        self._startup_poll_started = True
        self._start_poll_cycle()
        if not self._poll_timer.isActive():
            self._poll_timer.start()

    def _on_poll_timer_tick(self) -> None:
        self._start_poll_cycle()

    def _start_poll_cycle(self) -> None:
        if not self.is_global_polling_enabled():
            return

        def _clear_cycle_running_flag() -> None:
            with self._state_lock:
                self._poll_cycle_running = False

        with self._state_lock:
            if self._poll_cycle_running:
                return
            self._poll_cycle_running = True

        try:
            env_ids = self._eligible_poll_environment_ids()
        except Exception:
            _clear_cycle_running_flag()
            return

        if not env_ids:
            _clear_cycle_running_flag()
            return

        try:
            threading.Thread(
                target=self._run_poll_cycle,
                args=(env_ids,),
                daemon=True,
            ).start()
        except Exception:
            _clear_cycle_running_flag()

    def _run_poll_cycle(self, env_ids: list[str]) -> None:
        try:
            semaphore = threading.Semaphore(2)
            workers: list[threading.Thread] = []

            for index, env_id in enumerate(env_ids):
                pr_key = self._cache_key(item_type="pr", env_id=env_id)
                issue_key = self._cache_key(item_type="issue", env_id=env_id)

                pr_inflight = self._is_key_inflight(pr_key)
                issue_inflight = self._is_key_inflight(issue_key)

                if pr_inflight or issue_inflight:
                    if pr_inflight and not self._wait_for_inflight(pr_key, timeout_s=self._COALESCE_TIMEOUT_S):
                        logger.rprint(
                            f"[github-poll] coalesce timeout for pr key env={env_id}, skipping this cycle",
                            mode="warn",
                        )
                    if issue_inflight and not self._wait_for_inflight(issue_key, timeout_s=self._COALESCE_TIMEOUT_S):
                        logger.rprint(
                            f"[github-poll] coalesce timeout for issue key env={env_id}, skipping this cycle",
                            mode="warn",
                        )
                    continue

                semaphore.acquire()
                worker = threading.Thread(
                    target=self._poll_environment_bundle_worker,
                    args=(env_id, semaphore),
                    daemon=True,
                )
                worker.start()
                workers.append(worker)
                if index < len(env_ids) - 1:
                    time.sleep(2.0)

            for worker in workers:
                worker.join()
        finally:
            self._cycle_finished.emit()

    def _poll_environment_bundle_worker(
        self,
        env_id: str,
        semaphore: threading.Semaphore,
    ) -> None:
        try:
            self._fetch_key_sync(item_type="pr", env_id=env_id)
            self._fetch_key_sync(item_type="issue", env_id=env_id)
        finally:
            semaphore.release()

    def _fetch_key_sync(self, *, item_type: str, env_id: str, priority: Priority = Priority.LOW) -> None:
        normalized_type = self._normalize_item_type(item_type)
        normalized_env = str(env_id or "").strip()
        if not normalized_env:
            return
        key = self._cache_key(item_type=normalized_type, env_id=normalized_env)
        if not self._begin_fetch(key=key):
            return
        self._fetch_key_worker(normalized_type, normalized_env, priority=priority)

    def _fetch_key_worker(self, item_type: str, env_id: str, priority: Priority = Priority.LOW) -> None:
        with push_priority(priority):
            repo_context: GitHubRepoContext | None = None
            items: list[GitHubWorkItem] = []
            auto_reviews: list[dict[str, object]] = []
            error = ""

            try:
                env = self._environments.get(env_id)
                repo_context = resolve_environment_github_repo(env)
                if repo_context is None:
                    key = self._cache_key(item_type=item_type, env_id=env_id)
                    if self._should_preserve_stale_cache_on_missing_repo(key=key, env=env):
                        error = "transient repo detection unavailable"
                    self._fetch_completed.emit(
                        item_type,
                        env_id,
                        items,
                        None,
                        error,
                        auto_reviews,
                    )
                    return

                if item_type == "pr":
                    items = list_open_pull_requests(
                        repo_context.repo_owner,
                        repo_context.repo_name,
                        limit=30,
                    )
                else:
                    items = list_open_issues(
                        repo_context.repo_owner,
                        repo_context.repo_name,
                        limit=30,
                    )

                if resolve_effective_auto_review_enabled(
                    settings=self._settings,
                    env=env,
                ):
                    auto_reviews = self._collect_auto_reviews(
                        env_id=env_id,
                        repo_owner=repo_context.repo_owner,
                        repo_name=repo_context.repo_name,
                        items=items,
                    )
            except Exception as exc:
                error = str(exc)

            self._fetch_completed.emit(
                item_type,
                env_id,
                items,
                repo_context,
                error,
                auto_reviews,
            )

    def _begin_fetch(self, *, key: tuple[str, str]) -> bool:
        with self._state_lock:
            if key in self._inflight_keys:
                return False
            self._inflight_keys.add(key)
            event = self._inflight_events.get(key)
            if event is not None:
                event.clear()
            else:
                self._inflight_events[key] = threading.Event()

            current = self._cache.get(key)
            if current is None:
                self._cache[key] = GitHubWorkCacheEntry(
                    item_type=key[0],
                    env_id=key[1],
                    items=[],
                    repo_context=None,
                    error="",
                    fetched_at=0.0,
                    expires_at=0.0,
                    refreshing=True,
                )
            else:
                self._cache[key] = replace(current, refreshing=True)
        return True

    def _is_key_inflight(self, key: tuple[str, str]) -> bool:
        with self._state_lock:
            return key in self._inflight_keys

    def _wait_for_inflight(self, key: tuple[str, str], timeout_s: float = 30.0) -> bool:
        with self._state_lock:
            if key not in self._inflight_keys:
                return True
            event = self._inflight_events.get(key)
            if event is None:
                event = threading.Event()
                self._inflight_events[key] = event
        return event.wait(timeout=timeout_s)

    def _on_fetch_completed(
        self,
        item_type: str,
        env_id: str,
        items: object,
        repo_context: object,
        error: str,
        auto_reviews: object,
    ) -> None:
        key = self._cache_key(item_type=item_type, env_id=env_id)
        parsed_items = [item for item in (items if isinstance(items, list) else []) if isinstance(item, GitHubWorkItem)]  # pyright: ignore[reportUnknownVariableType]
        parsed_context = repo_context if isinstance(repo_context, GitHubRepoContext) else None
        parsed_reviews = auto_reviews if isinstance(auto_reviews, list) else []  # pyright: ignore[reportUnknownVariableType]

        now_s = time.time()

        with self._state_lock:
            previous = self._cache.get(key)
            self._inflight_keys.discard(key)
            event = self._inflight_events.pop(key, None)
            if event is not None:
                event.set()

            if parsed_context is None and not error:
                new_entry = GitHubWorkCacheEntry(
                    item_type=item_type,
                    env_id=env_id,
                    items=[],
                    repo_context=None,
                    error="",
                    fetched_at=now_s,
                    expires_at=now_s + self._CACHE_TTL_S,
                    refreshing=False,
                )
            elif error:
                fallback_items = list(previous.items) if previous is not None and previous.items else list(parsed_items)
                fallback_context = (
                    parsed_context
                    if parsed_context is not None
                    else (previous.repo_context if previous is not None else None)
                )
                new_entry = GitHubWorkCacheEntry(
                    item_type=item_type,
                    env_id=env_id,
                    items=fallback_items,
                    repo_context=fallback_context,
                    error=str(error or "").strip(),
                    fetched_at=now_s,
                    expires_at=now_s + self._CACHE_TTL_S,
                    refreshing=False,
                )
            else:
                new_entry = GitHubWorkCacheEntry(
                    item_type=item_type,
                    env_id=env_id,
                    items=list(parsed_items),
                    repo_context=parsed_context,
                    error="",
                    fetched_at=now_s,
                    expires_at=now_s + self._CACHE_TTL_S,
                    refreshing=False,
                )

            self._cache[key] = new_entry

        self.cache_updated.emit(item_type, env_id)
        self._emit_auto_reviews(
            env_id=env_id,
            repo_context=parsed_context,
            reviews=parsed_reviews,
        )

    def _should_preserve_stale_cache_on_missing_repo(self, *, key: tuple[str, str], env: Environment | None) -> bool:
        if env is None:
            return False
        workspace_type = str(getattr(env, "workspace_type", "") or "").strip().lower()
        if workspace_type != "mounted":
            return False
        with self._state_lock:
            previous = self._cache.get(key)
        if previous is None:
            return False
        return bool(previous.items) or previous.repo_context is not None

    def _emit_auto_reviews(
        self,
        *,
        env_id: str,
        repo_context: GitHubRepoContext | None,
        reviews: list[dict[str, object]],
    ) -> None:
        if repo_context is None:
            return

        repo_owner = str(repo_context.repo_owner or "")
        repo_name = str(repo_context.repo_name or "")

        for review in reviews:
            item_type = self._normalize_item_type(review.get("item_type"))
            try:
                number = int(review.get("number") or 0)
            except Exception:
                number = 0
            if number <= 0:
                continue

            trigger_source = str(review.get("trigger_source") or "").strip().lower()
            mention_key = str(review.get("mention_key") or "").strip()
            if not mention_key:
                continue

            item_key = str(review.get("item_key") or "").strip()
            if not item_key:
                item_key = self._mention_item_key(
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                    item_type=item_type,
                    number=number,
                )

            emit_key = (
                f"{repo_owner.strip().lower()}/{repo_name.strip().lower()}:"
                f"{item_type}:{number}:{trigger_source}:{mention_key}"
            )

            with self._state_lock:
                was_blocked = mention_key in self._eyes_blocked_anchors
                if mention_key in self._auto_review_seen_mentions:
                    if was_blocked:
                        self._eyes_blocked_anchors.pop(mention_key, None)
                        if item_key in self._active_task_by_item:
                            continue
                        self._auto_review_seen_mentions.discard(mention_key)
                        self._auto_review_emit_keys.discard(emit_key)
                    else:
                        continue
                elif was_blocked:
                    self._eyes_blocked_anchors.pop(mention_key, None)
                    if item_key in self._active_task_by_item:
                        continue
                if emit_key in self._auto_review_emit_keys:
                    continue

                self._auto_review_seen_mentions.add(mention_key)
                self._auto_review_emit_keys.add(emit_key)

            mention_text = str(review.get("mention_text") or "")
            mention_url = str(review.get("mention_url") or "")
            mention_author = str(review.get("mention_author") or "")
            mention_created_at = str(review.get("mention_created_at") or "")
            pr_head_ref = str(review.get("pr_head_ref") or "")
            pr_base_ref = str(review.get("pr_base_ref") or "")
            pr_head_repo_owner = str(review.get("pr_head_repo_owner") or "")
            pr_head_repo_name = str(review.get("pr_head_repo_name") or "")
            pr_is_cross_repo = bool(review.get("pr_is_cross_repo") or False)

            prompt = self._build_task_prompt(
                item_type=item_type,
                repo_owner=repo_owner,
                repo_name=repo_name,
                number=number,
                url=str(review.get("url") or "").strip(),
                title=str(review.get("title") or "").strip(),
                mention_text=mention_text,
            )
            if not prompt:
                continue
            payload = {
                "prompt": prompt,
                "repo_owner": repo_owner,
                "repo_name": repo_name,
                "item_type": item_type,
                "number": number,
                "trigger_source": trigger_source,
                "mention_source": trigger_source,
                "mention_text": mention_text,
                "mention_url": mention_url,
                "mention_author": mention_author,
                "mention_created_at": mention_created_at,
                "mention_key": mention_key,
                "pr_head_ref": pr_head_ref,
                "pr_base_ref": pr_base_ref,
                "pr_head_repo_owner": pr_head_repo_owner,
                "pr_head_repo_name": pr_head_repo_name,
                "pr_is_cross_repo": pr_is_cross_repo,
            }
            self.auto_review_requested.emit(env_id, payload)
            with self._state_lock:
                self._active_task_by_item[item_key] = time.time()

    def _collect_auto_reviews(
        self,
        *,
        env_id: str,
        repo_owner: str,
        repo_name: str,
        items: list[GitHubWorkItem],
    ) -> list[dict[str, object]]:
        env = self._environments.get(env_id)
        if not resolve_effective_auto_review_enabled(
            settings=self._settings,
            env=env,
        ):
            return []
        trusted_users = effective_trusted_users(
            global_usernames=self._settings.get("agentsnova_trusted_users_global", []),
            env=env,
        )
        if not trusted_users:
            return []
        auto_reactions_enabled = resolve_effective_auto_reactions_enabled(
            settings=self._settings,
            env=env,
        )

        with self._state_lock:
            queued_snapshot = set(self._auto_review_seen_mentions) - set(self._eyes_blocked_anchors)

        results: list[dict[str, object]] = []
        for item in items:
            pr_head_ref = str(getattr(item, "head_ref", "") or "")
            pr_base_ref = str(getattr(item, "base_ref", "") or "")
            pr_head_repo_owner = str(getattr(item, "head_repo_owner", "") or "")
            pr_head_repo_name = str(getattr(item, "head_repo_name", "") or "")
            pr_is_cross_repo = bool(getattr(item, "is_cross_repo", False))
            item_key = self._mention_item_key(
                repo_owner=repo_owner,
                repo_name=repo_name,
                item_type=item.item_type,
                number=item.number,
            )
            comments = list_issue_comments(
                repo_owner,
                repo_name,
                issue_number=item.number,
                limit=self._AUTO_REVIEW_THREAD_SCAN_LIMIT,
                newest_first=True,
            )
            candidates: list[dict[str, object]] = []

            def _add_comment_candidate(
                comment: GitHubComment,
                *,
                source: str,
            ) -> None:
                if not self._is_trusted_comment_author(comment, trusted_users):
                    return
                if not has_agentsnova_mention(comment.body):
                    return
                mention_created_at = str(comment.created_at or "")
                mention_created_at_s = self._parse_iso_timestamp_s(mention_created_at)
                mention_key = f"{source}:{comment.comment_id}"
                candidates.append(
                    {
                        "source": source,
                        "mention_key": mention_key,
                        "mention_text": str(comment.body or ""),
                        "mention_author": str(comment.author or ""),
                        "mention_created_at": mention_created_at,
                        "mention_url": str(comment.url or ""),
                        "created_at_s": mention_created_at_s or 0.0,
                        "sort_id": comment.comment_id,
                        "comment": comment,
                        "anchor_id": comment.comment_id,
                    }
                )

            for comment in comments:
                _add_comment_candidate(
                    comment,
                    source="issue_comment",
                )

            if item.item_type == "pr":
                review_comments = list_pull_request_review_comments(
                    repo_owner,
                    repo_name,
                    pull_number=item.number,
                    limit=self._AUTO_REVIEW_THREAD_SCAN_LIMIT,
                    newest_first=True,
                )
                for comment in review_comments:
                    _add_comment_candidate(
                        comment,
                        source="review_comment",
                    )

                review_bodies = list_pull_request_reviews(
                    repo_owner,
                    repo_name,
                    pull_number=item.number,
                    limit=self._AUTO_REVIEW_THREAD_SCAN_LIMIT,
                    newest_first=True,
                )
                for review in review_bodies:
                    author = str(review.author or "").strip().lower()
                    if not author or author not in trusted_users:
                        continue
                    if not has_agentsnova_mention(review.body):
                        continue
                    mention_created_at = str(review.submitted_at or "")
                    mention_created_at_s = self._parse_iso_timestamp_s(mention_created_at)
                    mention_key = f"review_body:{review.review_id}"
                    candidates.append(
                        {
                            "source": "review_body",
                            "mention_key": mention_key,
                            "mention_text": str(review.body or ""),
                            "mention_author": str(review.author or ""),
                            "mention_created_at": mention_created_at,
                            "mention_url": str(review.url or ""),
                            "created_at_s": mention_created_at_s or 0.0,
                            "sort_id": review.review_id,
                            "anchor_id": review.review_id,
                        }
                    )

            body_text = str(getattr(item, "body", "") or "")
            title_text = str(getattr(item, "title", "") or "")
            body_has_mention = has_agentsnova_mention(body_text)
            title_has_mention = has_agentsnova_mention(title_text)
            if body_has_mention or title_has_mention:
                if self._is_trusted_item_author(item=item, trusted_users=trusted_users):
                    mention_text = body_text if body_has_mention else title_text
                    updated_at = str(getattr(item, "updated_at", "") or "")
                    created_at = str(getattr(item, "created_at", "") or "")
                    mention_created_at = updated_at or created_at
                    mention_created_at_s = self._parse_iso_timestamp_s(mention_created_at)
                    source = "pr_body" if item.item_type == "pr" else "issue_body"
                    mention_key = f"{source}:{item_key}"
                    mention_author = str(getattr(item, "author", "") or "")
                    candidates.append(
                        {
                            "source": source,
                            "mention_key": mention_key,
                            "mention_text": str(mention_text or ""),
                            "mention_author": mention_author,
                            "mention_created_at": mention_created_at,
                            "mention_url": str(item.url or ""),
                            "created_at_s": mention_created_at_s or 0.0,
                            "sort_id": item.number,
                            "anchor_id": item.number,
                        }
                    )

            if not candidates:
                continue

            ordered_candidates = sorted(
                candidates,
                key=lambda candidate: (
                    float(candidate.get("created_at_s", 0.0) or 0.0),
                    int(candidate.get("sort_id", 0) or 0),
                ),
                reverse=True,
            )

            for candidate in ordered_candidates:
                mention_key = str(candidate.get("mention_key") or "").strip()
                if not mention_key:
                    continue
                if mention_key in queued_snapshot:
                    continue

                source = str(candidate.get("source") or "").strip().lower()
                try:
                    anchor_has_eyes = self._anchor_has_any_eyes(
                        repo_owner=repo_owner,
                        repo_name=repo_name,
                        item_number=item.number,
                        source=source,
                        anchor_id=candidate.get("anchor_id"),
                        candidate_comment=candidate.get("comment"),
                    )
                except Exception as exc:
                    self._log_auto_review_warning_once(
                        key="auto_review_read_eyes_failed",
                        message=(
                            "[github-auto-review] skipped auto-start scans: failed to "
                            "read eyes reaction anchors. "
                            f"first_error={exc}"
                        ),
                    )
                    continue
                if anchor_has_eyes:
                    with self._state_lock:
                        self._eyes_blocked_anchors[mention_key] = time.time()
                    continue

                if auto_reactions_enabled:
                    try:
                        self._add_anchor_eyes_reaction(
                            repo_owner=repo_owner,
                            repo_name=repo_name,
                            item_number=item.number,
                            source=source,
                            anchor_id=candidate.get("anchor_id"),
                        )
                    except Exception as exc:
                        self._log_auto_review_warning_once(
                            key="auto_review_add_eyes_failed",
                            message=(
                                "[github-auto-review] failed to add eyes reactions "
                                "during auto-start scans. "
                                f"first_error={exc}"
                            ),
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
            parsed = int(value or 0)
        except Exception:
            return 0
        return parsed if parsed > 0 else 0

    def _log_auto_review_warning_once(self, *, key: str, message: str) -> None:
        message_text = str(message or "").strip()
        if not key or not message_text:
            return
        should_log = False
        with self._state_lock:
            if key not in self._auto_review_warned_keys:
                self._auto_review_warned_keys.add(key)
                should_log = True
        if should_log:
            logger.rprint(message_text, mode="warn")

    def _anchor_has_any_eyes(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        item_number: int,
        source: str,
        anchor_id: object,
        candidate_comment: object | None = None,
    ) -> bool:
        if source == "issue_comment":
            if not isinstance(candidate_comment, GitHubComment):
                raise ValueError("missing issue comment candidate")
            return candidate_comment.reactions.eyes > 0
        if source == "review_comment":
            if not isinstance(candidate_comment, GitHubComment):
                raise ValueError("missing review comment candidate")
            return candidate_comment.reactions.eyes > 0
        if source == "review_body":
            review_id = self._safe_positive_int(anchor_id)
            if review_id <= 0:
                raise ValueError("invalid review anchor id")
            return has_pull_request_review_reaction(
                repo_owner,
                repo_name,
                pull_number=item_number,
                review_id=review_id,
                reaction="eyes",
            )
        if source in {"pr_body", "issue_body"}:
            return has_issue_reaction(
                repo_owner,
                repo_name,
                issue_number=item_number,
                reaction="eyes",
            )
        raise ValueError(f"unsupported mention source: {source}")

    def _add_anchor_eyes_reaction(
        self,
        *,
        repo_owner: str,
        repo_name: str,
        item_number: int,
        source: str,
        anchor_id: object,
    ) -> None:
        if source == "issue_comment":
            comment_id = self._safe_positive_int(anchor_id)
            if comment_id <= 0:
                raise ValueError("invalid issue comment anchor id")
            add_issue_comment_reaction(
                repo_owner,
                repo_name,
                comment_id=comment_id,
                reaction="eyes",
            )
            return
        if source == "review_comment":
            comment_id = self._safe_positive_int(anchor_id)
            if comment_id <= 0:
                raise ValueError("invalid review comment anchor id")
            add_pull_request_review_comment_reaction(
                repo_owner,
                repo_name,
                comment_id=comment_id,
                reaction="eyes",
            )
            return
        if source == "review_body":
            review_id = self._safe_positive_int(anchor_id)
            if review_id <= 0:
                raise ValueError("invalid review anchor id")
            add_pull_request_review_reaction(
                repo_owner,
                repo_name,
                pull_number=item_number,
                review_id=review_id,
                reaction="eyes",
            )
            return
        if source in {"pr_body", "issue_body"}:
            add_issue_reaction(
                repo_owner,
                repo_name,
                issue_number=item_number,
                reaction="eyes",
            )
            return
        raise ValueError(f"unsupported mention source: {source}")

    @staticmethod
    def _parse_iso_timestamp_s(value: object) -> float | None:
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

    @staticmethod
    def _is_trusted_comment_author(
        comment: GitHubComment,
        trusted_users: set[str],
    ) -> bool:
        author = str(comment.author or "").strip().lower()
        return bool(author and author in trusted_users)

    @staticmethod
    def _is_trusted_item_author(
        *,
        item: GitHubWorkItem,
        trusted_users: set[str],
    ) -> bool:
        author = str(getattr(item, "author", "") or "").strip().lower()
        return bool(author and author in trusted_users)

    @staticmethod
    def _normalize_item_type(value: object) -> str:
        normalized = str(value or "").strip().lower()
        return "pr" if normalized == "pr" else "issue"

    @staticmethod
    def _cache_key(*, item_type: str, env_id: str) -> tuple[str, str]:
        return (str(item_type or "").strip().lower(), str(env_id or "").strip())

    @staticmethod
    def _mention_item_key(
        *,
        repo_owner: str,
        repo_name: str,
        item_type: str,
        number: int,
    ) -> str:
        try:
            normalized_number = max(0, int(number))
        except Exception:
            normalized_number = 0
        return (
            f"{str(repo_owner or '').strip().lower()}/"
            f"{str(repo_name or '').strip().lower()}:"
            f"{str(item_type or '').strip().lower()}:{normalized_number}"
        )

    @staticmethod
    def _build_task_prompt(
        *,
        item_type: str,
        repo_owner: str,
        repo_name: str,
        number: int,
        url: str,
        title: str,
        mention_text: str,
    ) -> str:
        normalized_item_type = str(item_type or "").strip().lower()
        default_request = build_default_request_line(
            item_type=normalized_item_type,
            repo_owner=repo_owner,
            repo_name=repo_name,
            number=number,
        )
        primary_request = build_primary_request(
            mention_text=mention_text,
            fallback=default_request,
        )

        if normalized_item_type == "pr":
            return load_prompt(
                "pr_review_template",
                REPO_OWNER=repo_owner,
                REPO_NAME=repo_name,
                PR_NUMBER=number,
                PR_URL=url,
                PR_TITLE=title,
                PRIMARY_REQUEST=primary_request,
            ).strip()

        return load_prompt(
            "issue_fix_template",
            REPO_OWNER=repo_owner,
            REPO_NAME=repo_name,
            ISSUE_NUMBER=number,
            ISSUE_URL=url,
            ISSUE_TITLE=title,
            PRIMARY_REQUEST=primary_request,
        ).strip()

    def _eligible_poll_environment_ids(self) -> list[str]:
        ordered = sorted(
            self._environments.values(),
            key=lambda env: (str(env.name or env.env_id).lower(), str(env.env_id)),
        )
        env_ids: list[str] = []
        for env in ordered:
            env_id = str(env.env_id or "").strip()
            if not env_id:
                continue
            if not self.is_polling_effective_for_env(env_id):
                continue
            env_ids.append(env_id)
        return env_ids

    def _poll_interval_s(self) -> int:
        try:
            interval = int(self._settings.get("github_poll_interval_s", 30))
        except Exception:
            interval = 30
        return max(5, interval)

    def _startup_delay_s(self) -> int:
        try:
            delay = int(self._settings.get("github_poll_startup_delay_s", 35))
        except Exception:
            delay = 35
        return max(0, delay)

    def _on_cycle_finished(self) -> None:
        with self._state_lock:
            self._poll_cycle_running = False
