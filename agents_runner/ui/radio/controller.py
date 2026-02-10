from __future__ import annotations

import json
import re
import time
from typing import Any

from midori_ai_logger import MidoriAiLogger

from PySide6.QtCore import QObject
from PySide6.QtCore import QTimer
from PySide6.QtCore import QUrl
from PySide6.QtCore import Signal
from PySide6.QtNetwork import QNetworkAccessManager
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtNetwork import QNetworkRequest

try:
    from PySide6.QtMultimedia import QAudioOutput
    from PySide6.QtMultimedia import QMediaPlayer
except Exception:  # pragma: no cover - runtime capability path
    QAudioOutput = None  # type: ignore[assignment]
    QMediaPlayer = None  # type: ignore[assignment]

logger = MidoriAiLogger(channel=None, name=__name__)


class RadioController(QObject):
    """Controller for Midori AI Radio capability, network state, and playback."""

    state_changed = Signal(object)

    BASE_URL = "https://radio.midori-ai.xyz"
    HEALTH_ENDPOINT = "/health"
    CURRENT_ENDPOINT = "/radio/v1/current"
    STREAM_ENDPOINT = "/radio/v1/stream"
    HEALTH_INTERVAL_MS = 30_000
    CURRENT_INTERVAL_MS = 10_000
    QUALITY_VALUES = ("low", "medium", "high")
    LOUDNESS_BOOST_MIN = 0.1
    LOUDNESS_BOOST_MAX = 5.0
    LOUDNESS_BOOST_STEP = 0.05
    LOUDNESS_BOOST_DEFAULT = 2.2
    ERROR_LOG_THROTTLE_S = 30.0
    RECONNECT_DELAYS_MS = (500, 1000, 2000, 3000)
    RECONNECT_SUPPRESS_AFTER_STOP_S = 1.0
    WATCHDOG_INTERVAL_MS = 1000
    WATCHDOG_MIN_RESTART_INTERVAL_S = 0.75

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._qt_available = self.probe_qt_multimedia_available()
        self._service_available = False
        self._service_known = False
        self._enabled = False
        self._quality = "medium"
        self._active_quality = "medium"
        self._pending_quality: str | None = None
        self._volume = 70
        self._loudness_boost_enabled = False
        self._loudness_boost_factor = self.LOUDNESS_BOOST_DEFAULT
        self._effective_volume_percent = self._volume
        self._is_playing = False
        self._status_text = "Radio unavailable."
        self._current_track_title = ""
        self._last_track_title = ""
        self._current_track_id = ""
        self._degraded_from_playback = False
        self._desired_playing = False
        self._start_when_service_ready = False
        self._reconnect_attempts = 0
        self._last_reconnect_reason = ""
        self._reconnect_allow_service_bypass = False
        self._reconnect_force_restart = False
        self._last_restart_ts_s = 0.0
        self._suppress_reconnect_until_s = 0.0
        self._last_error_log_ts: dict[str, float] = {}

        self._audio_output: Any | None = None
        self._player: Any | None = None
        self._network: QNetworkAccessManager | None = None
        self._health_timer: QTimer | None = None
        self._current_timer: QTimer | None = None
        self._reconnect_timer: QTimer | None = None
        self._watchdog_timer: QTimer | None = None

        if not self._qt_available:
            self._status_text = (
                "Radio unavailable: Qt multimedia backend failed to initialize."
            )
            self._emit_state()
            return

        self._network = QNetworkAccessManager(self)
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(self.HEALTH_INTERVAL_MS)
        self._health_timer.timeout.connect(self._poll_health)

        self._current_timer = QTimer(self)
        self._current_timer.setInterval(self.CURRENT_INTERVAL_MS)
        self._current_timer.timeout.connect(self._poll_current)
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)
        self._watchdog_timer = QTimer(self)
        self._watchdog_timer.setInterval(self.WATCHDOG_INTERVAL_MS)
        self._watchdog_timer.timeout.connect(self._watchdog_tick)

        try:
            self._audio_output = QAudioOutput(self)
            self._player = QMediaPlayer(self)
            self._player.setAudioOutput(self._audio_output)
            self._apply_audio_output_volume()
            self._player.playbackStateChanged.connect(self._on_playback_state_changed)
            self._player.errorOccurred.connect(self._on_media_error)
            self._player.mediaStatusChanged.connect(self._on_media_status_changed)
            self._status_text = "Radio ready."
        except Exception as exc:
            self._log_error_throttled("media_init", f"media init failed: {exc}")
            self._qt_available = False
            self._audio_output = None
            self._player = None
            self._status_text = (
                "Radio unavailable: Qt multimedia backend failed to initialize."
            )
            self._emit_state()
            return

        self._health_timer.start()
        self._current_timer.start()
        self._watchdog_timer.start()
        QTimer.singleShot(0, self._poll_health)
        QTimer.singleShot(0, self._poll_current)
        self._emit_state()

    @classmethod
    def normalize_quality(cls, value: object) -> str:
        raw = str(value or "medium").strip().lower()
        if raw not in cls.QUALITY_VALUES:
            return "medium"
        return raw

    @staticmethod
    def clamp_volume(value: object) -> int:
        try:
            parsed = int(str(value).strip())
        except Exception:
            parsed = 70
        return max(0, min(100, parsed))

    @classmethod
    def normalize_loudness_boost_factor(cls, value: object) -> float:
        try:
            parsed = float(str(value).strip())
        except Exception:
            parsed = cls.LOUDNESS_BOOST_DEFAULT
        parsed = max(cls.LOUDNESS_BOOST_MIN, min(cls.LOUDNESS_BOOST_MAX, parsed))
        step_count = int(
            round((parsed - cls.LOUDNESS_BOOST_MIN) / cls.LOUDNESS_BOOST_STEP)
        )
        snapped = cls.LOUDNESS_BOOST_MIN + (step_count * cls.LOUDNESS_BOOST_STEP)
        snapped = max(cls.LOUDNESS_BOOST_MIN, min(cls.LOUDNESS_BOOST_MAX, snapped))
        return round(snapped, 2)

    @classmethod
    def probe_qt_multimedia_available(cls) -> bool:
        if QAudioOutput is None or QMediaPlayer is None:
            return False
        probe_audio: Any | None = None
        probe_player: Any | None = None
        try:
            probe_audio = QAudioOutput()
            probe_player = QMediaPlayer()
            probe_player.setAudioOutput(probe_audio)
            return True
        except Exception as exc:
            logger.rprint(f"radio probe failed: {exc}", mode="warn")
            return False
        finally:
            if probe_player is not None:
                probe_player.deleteLater()
            if probe_audio is not None:
                probe_audio.deleteLater()

    @property
    def qt_available(self) -> bool:
        return self._qt_available

    def state_snapshot(self) -> dict[str, object]:
        return {
            "qt_available": self._qt_available,
            "service_available": self._service_available,
            "service_known": self._service_known,
            "enabled": self._enabled,
            "quality": self._quality,
            "active_quality": self._active_quality,
            "pending_quality": self._pending_quality,
            "volume": self._volume,
            "loudness_boost_enabled": self._loudness_boost_enabled,
            "loudness_boost_factor": self._loudness_boost_factor,
            "effective_volume_percent": self._effective_volume_percent,
            "is_playing": self._is_playing,
            "status_text": self._status_text,
            "current_track": self._current_track_title,
            "last_track": self._last_track_title,
            "degraded_from_playback": self._degraded_from_playback,
            "desired_playing": self._desired_playing,
            "reconnect_attempts": self._reconnect_attempts,
            "last_reconnect_reason": self._last_reconnect_reason,
        }

    def _emit_state(self) -> None:
        self.state_changed.emit(dict(self.state_snapshot()))

    def shutdown(self) -> None:
        self.cancel_start_when_service_ready()
        if self._health_timer is not None:
            self._health_timer.stop()
        if self._current_timer is not None:
            self._current_timer.stop()
        if self._watchdog_timer is not None:
            self._watchdog_timer.stop()
        self._cancel_reconnect(reset_attempts=True)
        try:
            self.stop_playback()
        except Exception:
            pass

    def set_enabled(self, enabled: bool, *, start_when_enabled: bool = False) -> None:
        enabled = bool(enabled)
        changed = enabled != self._enabled
        self._enabled = enabled

        if not enabled:
            self._desired_playing = False
            self.cancel_start_when_service_ready()
            self._cancel_reconnect(reset_attempts=True)
            self.stop_playback()
            self._status_text = "Radio disabled."
            self._emit_state()
            return

        if changed and start_when_enabled:
            self.start_playback()
            return

        if changed:
            self._status_text = "Radio enabled."
            self._emit_state()

    def set_quality(self, quality: str) -> None:
        normalized = self.normalize_quality(quality)
        if normalized == self._quality and not self._pending_quality:
            return
        self._quality = normalized

        if self._is_playing:
            self._pending_quality = normalized
            self._status_text = f"Quality change queued ({normalized}) and will apply on track transition."
            self._emit_state()
            return

        self._active_quality = normalized
        self._pending_quality = None
        self._status_text = f"Quality set to {normalized}."
        self._emit_state()

    def set_volume(self, percent: int) -> None:
        clamped = self.clamp_volume(percent)
        if clamped == self._volume:
            return
        self._volume = clamped
        self._apply_audio_output_volume()
        self._emit_state()

    def set_loudness_boost(self, enabled: bool, factor: float) -> None:
        normalized_enabled = bool(enabled)
        normalized_factor = self.normalize_loudness_boost_factor(factor)
        if (
            normalized_enabled == self._loudness_boost_enabled
            and normalized_factor == self._loudness_boost_factor
        ):
            return
        self._loudness_boost_enabled = normalized_enabled
        self._loudness_boost_factor = normalized_factor
        self._apply_audio_output_volume()
        self._emit_state()

    def _compute_effective_volume_percent(self) -> int:
        if not self._loudness_boost_enabled:
            return self._volume
        return max(0, int(round(float(self._volume) * self._loudness_boost_factor)))

    def _apply_audio_output_volume(self) -> None:
        self._effective_volume_percent = self._compute_effective_volume_percent()
        qt_volume = max(0.0, min(1.0, float(self._effective_volume_percent) / 100.0))
        if self._audio_output is not None:
            self._audio_output.setVolume(qt_volume)

    def request_start_when_service_ready(self) -> None:
        if not self._qt_available:
            return
        self._start_when_service_ready = True
        if self._service_available and self._enabled and not self._is_playing:
            self._start_when_service_ready = False
            self.start_playback()

    def cancel_start_when_service_ready(self) -> None:
        self._start_when_service_ready = False

    def toggle_playback(self) -> None:
        if not self._enabled:
            self._enabled = True
        if self._desired_playing or self._is_playing:
            self.stop_playback()
            return
        self._desired_playing = True
        self.start_playback()

    def start_playback(self) -> bool:
        if not self._qt_available:
            self._desired_playing = False
            self._status_text = "Radio unavailable: Qt multimedia is not available."
            self._emit_state()
            return False
        if not self._enabled:
            self._desired_playing = False
            self._status_text = "Radio is disabled."
            self._emit_state()
            return False
        self._desired_playing = True
        if not self._service_available:
            self.request_start_when_service_ready()
            self._status_text = "Radio service unavailable."
            self._emit_state()
            return False
        if self._player is None:
            self._status_text = "Radio player is not ready."
            self._emit_state()
            return False

        quality_to_use = self._pending_quality or self._quality
        self._active_quality = self.normalize_quality(quality_to_use)
        self._pending_quality = None
        stream_url = self._build_stream_url(self._active_quality)

        try:
            self._cancel_reconnect(reset_attempts=True)
            self._suppress_reconnect_until_s = 0.0
            self._player.setSource(QUrl(stream_url))
            self._player.play()
            self._degraded_from_playback = False
            self._status_text = f"Playing Midori AI Radio ({self._active_quality})."
            self._emit_state()
            return True
        except Exception as exc:
            self._log_error_throttled("start_playback", f"playback start failed: {exc}")
            self._status_text = "Unable to start radio playback."
            self._emit_state()
            return False

    def stop_playback(self) -> None:
        self._desired_playing = False
        self._cancel_reconnect(reset_attempts=True)
        self._suppress_reconnect_until_s = (
            time.monotonic() + self.RECONNECT_SUPPRESS_AFTER_STOP_S
        )
        if self._player is not None:
            try:
                self._player.stop()
            except Exception:
                pass
        self._is_playing = False
        self._degraded_from_playback = False
        if self._enabled:
            self._status_text = "Radio stopped."
        self._emit_state()

    def _build_stream_url(self, quality: str) -> str:
        quality_value = self.normalize_quality(quality)
        return f"{self.BASE_URL}{self.STREAM_ENDPOINT}?q={quality_value}"

    def _poll_health(self) -> None:
        self._request_json(self.HEALTH_ENDPOINT, self._handle_health_response)

    def _poll_current(self) -> None:
        self._request_json(self.CURRENT_ENDPOINT, self._handle_current_response)

    def _request_json(
        self,
        endpoint: str,
        callback: Any,
    ) -> None:
        if not self._qt_available or self._network is None:
            return
        url = QUrl(f"{self.BASE_URL}{endpoint}")
        request = QNetworkRequest(url)
        request.setRawHeader(b"Accept", b"application/json")
        request.setRawHeader(b"User-Agent", b"midori-ai-agents-runner-radio")
        reply = self._network.get(request)

        def _finish() -> None:
            self._on_json_reply(reply, endpoint, callback)

        reply.finished.connect(_finish)

    def _on_json_reply(
        self, reply: QNetworkReply, endpoint: str, callback: Any
    ) -> None:
        payload: dict[str, Any] | None = None
        error_text = ""
        is_error = False

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                is_error = True
                error_text = str(reply.errorString() or "network error")
            else:
                raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("invalid JSON envelope")
                payload = parsed

                if not bool(parsed.get("ok")):
                    is_error = True
                    error = parsed.get("error")
                    if isinstance(error, dict):
                        error_text = str(error.get("message") or "API returned not-ok")
                    if not error_text:
                        error_text = "API returned not-ok"
        except Exception as exc:
            is_error = True
            error_text = str(exc or "invalid response")
        finally:
            reply.deleteLater()

        if is_error:
            self._log_error_throttled(endpoint, f"{endpoint} failed: {error_text}")
            callback(None, error_text)
            return

        callback(payload, "")

    def _handle_health_response(
        self,
        payload: dict[str, Any] | None,
        error_text: str,
    ) -> None:
        if error_text or payload is None:
            self._set_service_available(
                False, reason=error_text or "health unavailable"
            )
            return

        self._set_service_available(True, reason="health ready")

    def _handle_current_response(
        self,
        payload: dict[str, Any] | None,
        error_text: str,
    ) -> None:
        if error_text or payload is None:
            self._set_service_available(
                False, reason=error_text or "current track unavailable"
            )
            self._current_track_title = ""
            self._emit_state()
            return

        data = payload.get("data")
        if not isinstance(data, dict):
            self._set_service_available(False, reason="current payload missing data")
            self._current_track_title = ""
            self._emit_state()
            return

        self._set_service_available(True, reason="current track ok")

        previous_track_id = self._current_track_id
        track_id = str(data.get("track_id") or "").strip()
        title = self._normalize_track_title(
            data.get("title"),
            station_label=data.get("station_label"),
        )
        if track_id:
            self._current_track_id = track_id
        if title:
            self._current_track_title = title
            self._last_track_title = title
        else:
            self._current_track_title = ""

        if previous_track_id and track_id and previous_track_id != track_id:
            if self._pending_quality:
                self._apply_pending_quality(boundary_detected=True)
            elif self._enabled and self._desired_playing:
                self._queue_reconnect(
                    "track boundary detected",
                    allow_without_service=True,
                    force_restart=True,
                    immediate=True,
                )

        self._emit_state()

    def _normalize_track_title(
        self,
        raw_title: object,
        *,
        station_label: object = "",
    ) -> str:
        title = " ".join(str(raw_title or "").split())
        if not title:
            return ""

        known_suffixes = {"midori ai agents runner", "midori ai radio"}
        station = " ".join(str(station_label or "").split()).strip().casefold()
        if station:
            known_suffixes.add(station)

        parts = [
            part.strip() for part in re.split(r"\s+[—–-]\s+", title) if part.strip()
        ]
        if not parts:
            return ""

        while parts and parts[0].casefold() in known_suffixes:
            parts.pop(0)
        while len(parts) >= 2 and parts[-1].casefold() == parts[-2].casefold():
            parts.pop()
        while len(parts) >= 2 and parts[0].casefold() == parts[-1].casefold():
            parts.pop()
        while parts and parts[-1].casefold() in known_suffixes:
            parts.pop()

        if not parts:
            return ""
        return " - ".join(parts)

    def _apply_pending_quality(self, *, boundary_detected: bool) -> None:
        if not self._pending_quality:
            return
        pending = self.normalize_quality(self._pending_quality)
        self._pending_quality = None
        self._active_quality = pending

        if self._is_playing and self._service_available:
            try:
                if self._player is not None:
                    self._player.setSource(QUrl(self._build_stream_url(pending)))
                    self._player.play()
            except Exception as exc:
                self._log_error_throttled(
                    "quality_apply",
                    f"quality apply failed ({pending}): {exc}",
                )
                self._pending_quality = pending
                return

        if boundary_detected:
            self._status_text = f"Quality switched to {pending}."
        else:
            self._status_text = (
                f"Quality queued ({pending}); will apply on next playback start."
            )
        self._emit_state()

    def _set_service_available(self, available: bool, *, reason: str) -> None:
        available = bool(available)
        previous = self._service_available
        self._service_available = available
        self._service_known = True

        if available:
            if not previous:
                self._status_text = "Radio service healthy."
            self._degraded_from_playback = False
            if (
                self._start_when_service_ready
                and self._enabled
                and not self._is_playing
            ):
                self._start_when_service_ready = False
                self.start_playback()
                return
        else:
            if (
                not self._reconnect_allow_service_bypass
                and not self._reconnect_force_restart
            ):
                self._cancel_reconnect(reset_attempts=False)
            if previous and self._is_playing and self._last_track_title:
                self._degraded_from_playback = True
            if self._is_playing:
                self._status_text = (
                    "Radio unavailable. Playback may degrade until service recovery."
                )
            else:
                self._status_text = "Radio service unavailable."
            self._log_error_throttled("service", reason)

        self._emit_state()

    def _on_playback_state_changed(self, state: Any) -> None:
        if QMediaPlayer is None:
            return
        playing_state = QMediaPlayer.PlaybackState.PlayingState
        is_playing_now = bool(state == playing_state)
        if is_playing_now == self._is_playing:
            return
        self._is_playing = is_playing_now
        if is_playing_now:
            self._cancel_reconnect(reset_attempts=True)
            self._degraded_from_playback = False
            self._status_text = f"Playing Midori AI Radio ({self._active_quality})."
            self._emit_state()
            return
        if not is_playing_now and self._pending_quality:
            self._apply_pending_quality(boundary_detected=False)
            if self._is_playing:
                return
        if self._enabled and self._desired_playing:
            self._queue_reconnect(
                "playback state stopped",
                allow_without_service=True,
            )
        self._emit_state()

    def _on_media_error(self, _error: Any, error_string: str) -> None:
        text = str(error_string or "media playback error")
        self._log_error_throttled("media_error", text)
        self._status_text = "Radio playback error. Attempting to recover..."
        self._queue_reconnect(
            "media error",
            allow_without_service=True,
            force_restart=True,
        )
        self._emit_state()

    def _on_media_status_changed(self, status: Any) -> None:
        if QMediaPlayer is None:
            return

        status_name = self._media_status_name(status)
        restart_statuses = {
            "EndOfMedia",
            "InvalidMedia",
            "StalledMedia",
        }
        if status_name in restart_statuses:
            self._queue_reconnect(
                f"media status {status_name}",
                allow_without_service=True,
                force_restart=True,
                immediate=True,
            )
            self._emit_state()

    def _media_status_name(self, status: Any) -> str:
        try:
            return str(status.name)
        except Exception:
            pass
        return str(status)

    def _should_auto_reconnect(
        self,
        *,
        allow_without_service: bool = False,
        force_restart: bool = False,
    ) -> bool:
        if not self._qt_available or self._player is None:
            return False
        if not self._enabled:
            return False
        if not self._desired_playing:
            return False
        if not allow_without_service and not self._service_available:
            return False
        if self._is_playing and not force_restart:
            return False
        if time.monotonic() < self._suppress_reconnect_until_s:
            return False
        return True

    def _queue_reconnect(
        self,
        reason: str,
        *,
        allow_without_service: bool = False,
        force_restart: bool = False,
        immediate: bool = False,
    ) -> None:
        if not self._should_auto_reconnect(
            allow_without_service=allow_without_service,
            force_restart=force_restart,
        ):
            return
        if self._reconnect_timer is not None and self._reconnect_timer.isActive():
            if allow_without_service:
                self._reconnect_allow_service_bypass = True
            if force_restart:
                self._reconnect_force_restart = True
            return

        self._reconnect_allow_service_bypass = bool(allow_without_service)
        self._reconnect_force_restart = bool(force_restart)
        self._reconnect_attempts += 1
        self._last_reconnect_reason = str(reason or "unknown")
        delay_ms = (
            0 if immediate else self._next_reconnect_delay_ms(self._reconnect_attempts)
        )
        self._status_text = (
            f"Radio stream interrupted. Reconnecting ({self._reconnect_attempts})..."
        )

        if self._reconnect_timer is None:
            return
        self._reconnect_timer.start(delay_ms)

    def _next_reconnect_delay_ms(self, attempt: int) -> int:
        attempt_idx = max(0, int(attempt) - 1)
        max_idx = len(self.RECONNECT_DELAYS_MS) - 1
        return int(self.RECONNECT_DELAYS_MS[min(attempt_idx, max_idx)])

    def _attempt_reconnect(self) -> None:
        allow_without_service = bool(self._reconnect_allow_service_bypass)
        force_restart = bool(self._reconnect_force_restart)
        if not self._should_auto_reconnect(
            allow_without_service=allow_without_service,
            force_restart=force_restart,
        ):
            if not self._enabled:
                self._cancel_reconnect(reset_attempts=True)
            return
        if self._player is None:
            return

        quality_to_use = self.normalize_quality(
            self._pending_quality or self._active_quality or self._quality
        )
        self._active_quality = quality_to_use
        self._status_text = f"Reconnecting Midori AI Radio ({quality_to_use})..."
        self._last_restart_ts_s = time.monotonic()

        try:
            if force_restart:
                try:
                    self._player.stop()
                except Exception:
                    pass
                self._is_playing = False
            self._player.setSource(QUrl(self._build_stream_url(quality_to_use)))
            self._player.play()
        except Exception as exc:
            self._log_error_throttled(
                "reconnect",
                f"reconnect failed ({quality_to_use}): {exc}",
            )
            self._queue_reconnect(
                "reconnect exception",
                allow_without_service=allow_without_service,
                force_restart=force_restart,
            )

        self._emit_state()

    def _cancel_reconnect(self, *, reset_attempts: bool) -> None:
        if self._reconnect_timer is not None and self._reconnect_timer.isActive():
            self._reconnect_timer.stop()
        if reset_attempts:
            self._reconnect_attempts = 0
            self._last_reconnect_reason = ""
            self._reconnect_allow_service_bypass = False
            self._reconnect_force_restart = False

    def _watchdog_tick(self) -> None:
        if not self._qt_available or self._player is None:
            return
        if not self._enabled or not self._desired_playing:
            return
        if self._reconnect_timer is not None and self._reconnect_timer.isActive():
            return
        if time.monotonic() < self._suppress_reconnect_until_s:
            return

        now = time.monotonic()
        if now - self._last_restart_ts_s < self.WATCHDOG_MIN_RESTART_INTERVAL_S:
            return

        if not self._is_playing:
            self._queue_reconnect(
                "watchdog detected stalled playback",
                allow_without_service=True,
                force_restart=True,
                immediate=True,
            )
            self._emit_state()
            return

        status_name = self._media_status_name(self._player.mediaStatus())
        if status_name in {"EndOfMedia", "InvalidMedia", "StalledMedia"}:
            self._queue_reconnect(
                f"watchdog media status {status_name}",
                allow_without_service=True,
                force_restart=True,
                immediate=True,
            )
            self._emit_state()

    def _log_error_throttled(self, key: str, message: str) -> None:
        now = time.monotonic()
        last = float(self._last_error_log_ts.get(key, 0.0))
        if now - last < self.ERROR_LOG_THROTTLE_S:
            return
        self._last_error_log_ts[key] = now
        logger.rprint(f"[radio] {message}", mode="warn")
