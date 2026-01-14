#!/usr/bin/env python3
"""Profile the Codex background animation performance."""

from __future__ import annotations

import sys
import time
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from agents_runner.ui.graphics import GlassRoot


class ProfileWindow(QWidget):
    """Window for profiling the background animation."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Background Performance Profile")
        self.resize(1200, 800)

        # Create background widget
        self.background = GlassRoot(self)
        self.background.set_agent_theme("codex")

        # Create stats overlay
        self.stats_label = QLabel("Profiling...", self)
        self.stats_label.setStyleSheet(
            "background: rgba(0, 0, 0, 180); color: white; padding: 10px; font-family: monospace;"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.background)
        layout.addWidget(self.stats_label)

        # Profiling state
        self.paint_times: list[float] = []
        self.update_times: list[float] = []
        self.sample_count = 0
        self.max_samples = 200  # 20 seconds at 10 FPS

        # Hook into paint event
        self._original_paint = self.background.paintEvent
        self.background.paintEvent = self._profiled_paint_event

        # Hook into update callback
        self._original_update = self.background._update_background_animation
        self.background._update_background_animation = self._profiled_update

        # Update stats display
        self.stats_timer = QTimer(self)
        self.stats_timer.setInterval(500)
        self.stats_timer.timeout.connect(self._update_stats_display)
        self.stats_timer.start()

        # Auto-close after profiling
        self.profile_timer = QTimer(self)
        self.profile_timer.setSingleShot(True)
        self.profile_timer.setInterval(22000)  # 22 seconds
        self.profile_timer.timeout.connect(self._finish_profiling)
        self.profile_timer.start()

    def _profiled_paint_event(self, event: Any) -> None:
        """Wrapper around paintEvent to measure time."""
        start = time.perf_counter_ns()
        self._original_paint(event)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0  # Convert ns to ms
        self.paint_times.append(elapsed_ms)

    def _profiled_update(self) -> None:
        """Wrapper around _update_background_animation to measure time."""
        start = time.perf_counter_ns()
        self._original_update()
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0  # Convert ns to ms
        self.update_times.append(elapsed_ms)
        self.sample_count += 1

    def _update_stats_display(self) -> None:
        """Update the stats label with current profiling data."""
        if not self.paint_times or not self.update_times:
            return

        # Calculate paint stats
        paint_avg = sum(self.paint_times) / len(self.paint_times)
        paint_max = max(self.paint_times)
        paint_min = min(self.paint_times)

        # Calculate update stats
        update_avg = sum(self.update_times) / len(self.update_times)
        update_max = max(self.update_times)

        # Calculate recent samples (last 20)
        recent_paint = self.paint_times[-20:] if len(self.paint_times) >= 20 else self.paint_times
        recent_avg = sum(recent_paint) / len(recent_paint)

        stats_text = f"""BACKGROUND PERFORMANCE PROFILE
─────────────────────────────────────
Samples: {self.sample_count} / {self.max_samples}

Paint Event:
  Average: {paint_avg:.2f}ms
  Recent:  {recent_avg:.2f}ms
  Min:     {paint_min:.2f}ms
  Max:     {paint_max:.2f}ms

Update Animation:
  Average: {update_avg:.2f}ms
  Max:     {update_max:.2f}ms

Target: < 5ms paint, < 3% CPU
"""
        self.stats_label.setText(stats_text)

    def _finish_profiling(self) -> None:
        """Print final report and close."""
        print("\n" + "=" * 60)
        print("BACKGROUND PERFORMANCE PROFILE - FINAL REPORT")
        print("=" * 60)

        if not self.paint_times or not self.update_times:
            print("ERROR: No profiling data collected")
            QApplication.quit()
            return

        # Paint event stats
        paint_avg = sum(self.paint_times) / len(self.paint_times)
        paint_max = max(self.paint_times)
        paint_min = min(self.paint_times)
        paint_median = sorted(self.paint_times)[len(self.paint_times) // 2]

        # Update animation stats
        update_avg = sum(self.update_times) / len(self.update_times)
        update_max = max(self.update_times)
        update_min = min(self.update_times)

        print(f"\nSample Count: {len(self.paint_times)} paint events, {len(self.update_times)} updates")
        print(f"\nPaint Event Performance:")
        print(f"  Average:  {paint_avg:.3f}ms")
        print(f"  Median:   {paint_median:.3f}ms")
        print(f"  Min:      {paint_min:.3f}ms")
        print(f"  Max:      {paint_max:.3f}ms")

        print(f"\nUpdate Animation Performance:")
        print(f"  Average:  {update_avg:.3f}ms")
        print(f"  Min:      {update_min:.3f}ms")
        print(f"  Max:      {update_max:.3f}ms")

        # Check against targets
        print(f"\nPerformance Targets:")
        paint_ok = "✓" if paint_avg < 5.0 else "✗"
        print(f"  {paint_ok} Paint < 5ms:  {paint_avg:.2f}ms (target: < 5.0ms)")

        # Calculate theoretical CPU usage
        # Timer runs at 100ms (10 Hz), so theoretical max is:
        # (paint_time + update_time) * 10 updates/sec = % of 1 second
        cycle_time = paint_avg + update_avg
        theoretical_cpu = (cycle_time / 100.0) * 100.0  # As percentage
        cpu_ok = "✓" if theoretical_cpu < 3.0 else "✗"
        print(f"  {cpu_ok} CPU < 3%:     ~{theoretical_cpu:.2f}% (target: < 3.0%)")

        # Performance breakdown
        print(f"\nPerformance Breakdown:")
        total_time = paint_avg + update_avg
        paint_pct = (paint_avg / total_time * 100) if total_time > 0 else 0
        update_pct = (update_avg / total_time * 100) if total_time > 0 else 0
        print(f"  Paint:     {paint_pct:.1f}% ({paint_avg:.3f}ms)")
        print(f"  Update:    {update_pct:.1f}% ({update_avg:.3f}ms)")
        print(f"  Total:     {total_time:.3f}ms per cycle")

        # Recommendations
        print(f"\nRecommendations:")
        if paint_avg >= 5.0:
            print("  ! Paint time exceeds target - consider optimizations:")
            print("    - Cache QColor objects")
            print("    - Cache QLinearGradient objects")
            print("    - Reduce gradient complexity")
        if theoretical_cpu >= 3.0:
            print("  ! CPU usage may be high - consider:")
            print("    - Increase timer interval (100ms → 150ms)")
            print("    - Skip repaints when phase change < threshold")
        if paint_avg < 5.0 and theoretical_cpu < 3.0:
            print("  ✓ Performance is within acceptable targets")

        print("\n" + "=" * 60)

        QApplication.quit()


def main() -> int:
    """Run the profiling window."""
    app = QApplication(sys.argv)
    window = ProfileWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
