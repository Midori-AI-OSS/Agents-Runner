from __future__ import annotations

import threading
import time

from dataclasses import dataclass
from dataclasses import replace

from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal

from agents_runner.environments import Environment
from agents_runner.environments import GitHubRepoContext
from agents_runner.environments import resolve_environment_github_repo
from agents_runner.gh.work_items import GitHubComment
from agents_runner.gh.work_items import GitHubWorkItem
from agents_runner.gh.work_items import add_issue_comment_reaction
from agents_runner.gh.work_items import list_issue_comments
from agents_runner.gh.work_items import list_open_issues
from agents_runner.gh.work_items import list_open_pull_requests
from agents_runner.prompts import load_prompt
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
    auto_review_requested = Signal(str, str)

    _fetch_completed = Signal(str, str, object, object, str, object)
    _cycle_finished = Signal()

    _CACHE_TTL_S = 45.0

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings: dict[str, object] = {}
        self._environments: dict[str, Environment] = {}
        self._cache: dict[tuple[str, str], GitHubWorkCacheEntry] = {}
        self._inflight_keys: set[tuple[str, str]] = set()

        self._auto_review_seen_comment_ids: set[int] = set()
        self._auto_review_seen_item_mentions: set[str] = set()
        self._auto_review_emit_keys: set[str] = set()

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
        self._settings = dict(settings_data or {})
        self._poll_timer.setInterval(self._poll_interval_s() * 1000)
        self._reconfigure_polling_timers()

    def set_environments(self, environments: dict[str, Environment]) -> None:
        self._environments = dict(environments or {})
        self._reconfigure_polling_timers()

    def get_cache_entry(
        self, *, item_type: str, env_id: str
    ) -> GitHubWorkCacheEntry | None:
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
        threading.Thread(
            target=self._fetch_key_worker,
            args=(normalized_type, normalized_env),
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

    def is_global_polling_enabled(self) -> bool:
        return bool(self._settings.get("github_polling_enabled") or False)

    def is_polling_effective_for_env(self, env_id: str) -> bool:
        if not self.is_global_polling_enabled():
            return False
        env = self._environments.get(str(env_id or "").strip())
        if env is None:
            return False
        if not bool(getattr(env, "github_polling_enabled", False)):
            return False
        return resolve_environment_github_repo(env) is not None

    def _reconfigure_polling_timers(self) -> None:
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

        with self._state_lock:
            if self._poll_cycle_running:
                return
            self._poll_cycle_running = True

        env_ids = self._eligible_poll_environment_ids()
        if not env_ids:
            with self._state_lock:
                self._poll_cycle_running = False
            return

        threading.Thread(
            target=self._run_poll_cycle,
            args=(env_ids,),
            daemon=True,
        ).start()

    def _run_poll_cycle(self, env_ids: list[str]) -> None:
        try:
            semaphore = threading.Semaphore(2)
            workers: list[threading.Thread] = []

            for index, env_id in enumerate(env_ids):
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

    def _fetch_key_sync(self, *, item_type: str, env_id: str) -> None:
        normalized_type = self._normalize_item_type(item_type)
        normalized_env = str(env_id or "").strip()
        if not normalized_env:
            return
        key = self._cache_key(item_type=normalized_type, env_id=normalized_env)
        if not self._begin_fetch(key=key):
            return
        self._fetch_key_worker(normalized_type, normalized_env)

    def _fetch_key_worker(self, item_type: str, env_id: str) -> None:
        repo_context: GitHubRepoContext | None = None
        items: list[GitHubWorkItem] = []
        auto_reviews: list[dict[str, object]] = []
        error = ""

        try:
            env = self._environments.get(env_id)
            repo_context = resolve_environment_github_repo(env)
            if repo_context is None:
                self._fetch_completed.emit(
                    item_type,
                    env_id,
                    items,
                    None,
                    "",
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

            if bool(self._settings.get("agentsnova_auto_review_enabled", True)):
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
        parsed_items = [
            item
            for item in (items if isinstance(items, list) else [])
            if isinstance(item, GitHubWorkItem)
        ]
        parsed_context = (
            repo_context if isinstance(repo_context, GitHubRepoContext) else None
        )
        parsed_reviews = auto_reviews if isinstance(auto_reviews, list) else []

        now_s = time.time()

        with self._state_lock:
            previous = self._cache.get(key)
            self._inflight_keys.discard(key)

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
                fallback_items = (
                    list(previous.items)
                    if previous is not None and previous.items
                    else list(parsed_items)
                )
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
            try:
                mention_comment_id = int(review.get("mention_comment_id") or 0)
            except Exception:
                mention_comment_id = 0

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
                f"{item_type}:{number}:{trigger_source}:{max(0, mention_comment_id)}"
            )

            with self._state_lock:
                if mention_comment_id > 0 and (
                    mention_comment_id in self._auto_review_seen_comment_ids
                ):
                    continue
                if trigger_source == "body_mention" and (
                    item_key in self._auto_review_seen_item_mentions
                ):
                    continue
                if emit_key in self._auto_review_emit_keys:
                    continue

                if mention_comment_id > 0:
                    self._auto_review_seen_comment_ids.add(mention_comment_id)
                if trigger_source == "body_mention":
                    self._auto_review_seen_item_mentions.add(item_key)
                self._auto_review_emit_keys.add(emit_key)

            prompt = self._build_task_prompt(
                item_type=item_type,
                repo_owner=repo_owner,
                repo_name=repo_name,
                number=number,
                url=str(review.get("url") or "").strip(),
                title=str(review.get("title") or "").strip(),
                trigger_source=trigger_source,
                mention_comment_id=mention_comment_id,
            )
            if not prompt:
                continue
            self.auto_review_requested.emit(env_id, prompt)

    def _collect_auto_reviews(
        self,
        *,
        env_id: str,
        repo_owner: str,
        repo_name: str,
        items: list[GitHubWorkItem],
    ) -> list[dict[str, object]]:
        env = self._environments.get(env_id)
        trusted_users = effective_trusted_users(
            global_usernames=self._settings.get("agentsnova_trusted_users_global", []),
            env=env,
        )
        if not trusted_users:
            return []

        with self._state_lock:
            queued_snapshot = set(self._auto_review_seen_comment_ids)
            queued_item_snapshot = set(self._auto_review_seen_item_mentions)

        results: list[dict[str, object]] = []
        for item in items:
            item_key = self._mention_item_key(
                repo_owner=repo_owner,
                repo_name=repo_name,
                item_type=item.item_type,
                number=item.number,
            )
            queued_for_item = False

            comments = list_issue_comments(
                repo_owner,
                repo_name,
                issue_number=item.number,
                limit=100,
            )
            ordered_comments = list(comments)
            ordered_comments.reverse()

            for comment in ordered_comments:
                if not self._is_trusted_comment_author(comment, trusted_users):
                    continue
                body = str(comment.body or "")
                if "@agentsnova" not in body.lower():
                    continue
                if comment.comment_id in queued_snapshot:
                    continue
                if not self._can_apply_reaction(item=item, comment=comment):
                    continue

                marker = "eyes" if item.item_type == "pr" else "rocket"
                try:
                    add_issue_comment_reaction(
                        repo_owner,
                        repo_name,
                        comment_id=comment.comment_id,
                        reaction=marker,
                    )
                except Exception:
                    continue

                results.append(
                    {
                        "item_type": item.item_type,
                        "number": item.number,
                        "url": item.url,
                        "title": item.title,
                        "mention_comment_id": comment.comment_id,
                        "trigger_source": "comment_mention",
                        "item_key": item_key,
                    }
                )
                queued_for_item = True
                if len(results) >= 3:
                    return results
                break

            if queued_for_item:
                continue

            if item_key in queued_item_snapshot:
                continue

            if self._item_has_agentsnova_mention(item) and self._is_trusted_item_author(
                item=item,
                trusted_users=trusted_users,
            ):
                results.append(
                    {
                        "item_type": item.item_type,
                        "number": item.number,
                        "url": item.url,
                        "title": item.title,
                        "mention_comment_id": 0,
                        "trigger_source": "body_mention",
                        "item_key": item_key,
                    }
                )
                queued_item_snapshot.add(item_key)
                if len(results) >= 3:
                    return results

        return results

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
    def _can_apply_reaction(*, item: GitHubWorkItem, comment: GitHubComment) -> bool:
        reactions = comment.reactions
        if reactions.thumbs_up > 0 or reactions.thumbs_down > 0:
            return False
        if item.item_type == "pr":
            return reactions.eyes <= 0
        return reactions.rocket <= 0 and reactions.hooray <= 0

    @staticmethod
    def _item_has_agentsnova_mention(item: GitHubWorkItem) -> bool:
        body = str(getattr(item, "body", "") or "").strip().lower()
        title = str(getattr(item, "title", "") or "").strip().lower()
        return "@agentsnova" in body or "@agentsnova" in title

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
        trigger_source: str,
        mention_comment_id: int,
    ) -> str:
        normalized_item_type = str(item_type or "").strip().lower()
        try:
            parsed_mention_comment_id = int(mention_comment_id)
        except Exception:
            parsed_mention_comment_id = 0
        mention_id = (
            str(parsed_mention_comment_id) if parsed_mention_comment_id > 0 else ""
        )
        source = str(trigger_source or "").strip().lower() or "manual"

        if normalized_item_type == "pr":
            return load_prompt(
                "pr_review_template",
                REPO_OWNER=repo_owner,
                REPO_NAME=repo_name,
                PR_NUMBER=number,
                PR_URL=url,
                PR_TITLE=title,
                MENTION_COMMENT_ID=mention_id,
                TRIGGER_SOURCE=source,
            ).strip()

        return load_prompt(
            "issue_fix_template",
            REPO_OWNER=repo_owner,
            REPO_NAME=repo_name,
            ISSUE_NUMBER=number,
            ISSUE_URL=url,
            ISSUE_TITLE=title,
            MENTION_COMMENT_ID=mention_id,
            TRIGGER_SOURCE=source,
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
