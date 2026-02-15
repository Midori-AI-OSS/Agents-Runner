from __future__ import annotations


class MainWindowCapacityMixin:
    def _count_running_agents(self, env_id: str | None = None) -> int:
        count = 0
        env_id = str(env_id or "").strip() or None
        for task in self._tasks.values():
            if env_id and str(getattr(task, "environment_id", "") or "") != env_id:
                continue
            if task.status.lower() in {"pulling", "created", "running", "starting"}:
                count += 1
        return count

    def _max_agents_running_for_env(self, env_id: str | None) -> int:
        env_id = str(env_id or "").strip()
        env = self._environments.get(env_id) if env_id else None
        if env is not None:
            try:
                return int(getattr(env, "max_agents_running", -1))
            except Exception:
                return -1
        try:
            return int(self._settings_data.get("max_agents_running", -1))
        except Exception:
            return -1

    def _can_start_new_agent_for_env(self, env_id: str | None) -> bool:
        max_agents = self._max_agents_running_for_env(env_id)
        if max_agents < 0:
            return True
        return self._count_running_agents(env_id) < max_agents

    def _try_start_queued_tasks(self) -> None:
        queued = [t for t in self._tasks.values() if t.status.lower() == "queued"]
        if not queued:
            return
        queued.sort(key=lambda t: t.created_at_s)
        for task in queued:
            if not self._can_start_new_agent_for_env(
                getattr(task, "environment_id", "")
            ):
                continue
            self._actually_start_task(task)
