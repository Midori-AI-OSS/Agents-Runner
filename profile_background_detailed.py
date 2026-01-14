#!/usr/bin/env python3
"""Detailed profiling of Codex background components."""

from __future__ import annotations

import sys
import time
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from agents_runner.ui.graphics import GlassRoot


class DetailedProfileWindow(QWidget):
    """Window for detailed profiling of background components."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Detailed Background Performance Profile")
        self.resize(1200, 800)

        # Create background widget
        self.background = GlassRoot(self)
        self.background.set_agent_theme("codex")

        # Create stats overlay
        self.stats_label = QLabel("Profiling...", self)
        self.stats_label.setStyleSheet(
            "background: rgba(0, 0, 0, 180); color: white; padding: 10px; font-family: monospace; font-size: 11px;"
        )

        layout = QVBoxLayout(self)
        layout.addWidget(self.background)
        layout.addWidget(self.stats_label)

        # Profiling state
        self.codex_bg_times: list[float] = []
        self.band_boundary_times: list[float] = []
        self.calc_split_times: list[float] = []
        self.calc_top_phase_times: list[float] = []
        self.calc_bottom_phase_times: list[float] = []
        self.get_top_color_times: list[float] = []
        self.get_bottom_color_times: list[float] = []
        self.blend_colors_times: list[float] = []
        self.sample_count = 0

        # Hook into methods
        self._original_codex_bg = self.background._paint_codex_background
        self.background._paint_codex_background = self._profiled_codex_bg

        self._original_band_boundary = self.background._paint_band_boundary
        self.background._paint_band_boundary = self._profiled_band_boundary

        self._original_calc_split = self.background._calc_split_ratio
        self.background._calc_split_ratio = self._profiled_calc_split

        self._original_calc_top = self.background._calc_top_phase
        self.background._calc_top_phase = self._profiled_calc_top

        self._original_calc_bottom = self.background._calc_bottom_phase
        self.background._calc_bottom_phase = self._profiled_calc_bottom

        self._original_get_top = self.background._get_top_band_color
        self.background._get_top_band_color = self._profiled_get_top

        self._original_get_bottom = self.background._get_bottom_band_color
        self.background._get_bottom_band_color = self._profiled_get_bottom

        self._original_blend = self.background._blend_colors
        self.background._blend_colors = self._profiled_blend

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

    def _profiled_codex_bg(self, painter: QPainter, rect: Any) -> None:
        """Wrapper around _paint_codex_background."""
        start = time.perf_counter_ns()
        self._original_codex_bg(painter, rect)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.codex_bg_times.append(elapsed_ms)
        self.sample_count += 1

    def _profiled_band_boundary(self, painter: Any, rect: Any, split_ratio: float, top_color: Any, bottom_color: Any) -> None:
        """Wrapper around _paint_band_boundary."""
        start = time.perf_counter_ns()
        self._original_band_boundary(painter, rect, split_ratio, top_color, bottom_color)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.band_boundary_times.append(elapsed_ms)

    def _profiled_calc_split(self) -> float:
        """Wrapper around _calc_split_ratio."""
        start = time.perf_counter_ns()
        result = self._original_calc_split()
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.calc_split_times.append(elapsed_ms)
        return result

    def _profiled_calc_top(self) -> float:
        """Wrapper around _calc_top_phase."""
        start = time.perf_counter_ns()
        result = self._original_calc_top()
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.calc_top_phase_times.append(elapsed_ms)
        return result

    def _profiled_calc_bottom(self) -> float:
        """Wrapper around _calc_bottom_phase."""
        start = time.perf_counter_ns()
        result = self._original_calc_bottom()
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.calc_bottom_phase_times.append(elapsed_ms)
        return result

    def _profiled_get_top(self, phase: float) -> Any:
        """Wrapper around _get_top_band_color."""
        start = time.perf_counter_ns()
        result = self._original_get_top(phase)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.get_top_color_times.append(elapsed_ms)
        return result

    def _profiled_get_bottom(self, phase: float) -> Any:
        """Wrapper around _get_bottom_band_color."""
        start = time.perf_counter_ns()
        result = self._original_get_bottom(phase)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.get_bottom_color_times.append(elapsed_ms)
        return result

    def _profiled_blend(self, color1: Any, color2: Any, t: float) -> Any:
        """Wrapper around _blend_colors."""
        start = time.perf_counter_ns()
        result = self._original_blend(color1, color2, t)
        end = time.perf_counter_ns()
        elapsed_ms = (end - start) / 1_000_000.0
        self.blend_colors_times.append(elapsed_ms)
        return result

    def _avg(self, times: list[float]) -> float:
        """Calculate average."""
        return sum(times) / len(times) if times else 0.0

    def _update_stats_display(self) -> None:
        """Update the stats label with current profiling data."""
        if not self.codex_bg_times:
            return

        stats_text = f"""DETAILED BACKGROUND PERFORMANCE PROFILE
────────────────────────────────────────────────
Samples: {self.sample_count}

Paint Methods:
  _paint_codex_background:  {self._avg(self.codex_bg_times):.3f}ms
  _paint_band_boundary:     {self._avg(self.band_boundary_times):.3f}ms

Phase Calculations:
  _calc_split_ratio:        {self._avg(self.calc_split_times):.3f}ms
  _calc_top_phase:          {self._avg(self.calc_top_phase_times):.3f}ms
  _calc_bottom_phase:       {self._avg(self.calc_bottom_phase_times):.3f}ms

Color Methods:
  _get_top_band_color:      {self._avg(self.get_top_color_times):.3f}ms
  _get_bottom_band_color:   {self._avg(self.get_bottom_color_times):.3f}ms
  _blend_colors (avg):      {self._avg(self.blend_colors_times):.3f}ms
  _blend_colors (calls):    {len(self.blend_colors_times)}
"""
        self.stats_label.setText(stats_text)

    def _finish_profiling(self) -> None:
        """Print final report and close."""
        print("\n" + "=" * 70)
        print("DETAILED BACKGROUND PERFORMANCE PROFILE - FINAL REPORT")
        print("=" * 70)

        if not self.codex_bg_times:
            print("ERROR: No profiling data collected")
            QApplication.quit()
            return

        print(f"\nSample Count: {self.sample_count}")
        
        print(f"\nPaint Methods:")
        print(f"  _paint_codex_background:  {self._avg(self.codex_bg_times):.4f}ms avg")
        print(f"  _paint_band_boundary:     {self._avg(self.band_boundary_times):.4f}ms avg")

        print(f"\nPhase Calculations (per call):")
        print(f"  _calc_split_ratio:        {self._avg(self.calc_split_times):.4f}ms ({len(self.calc_split_times)} calls)")
        print(f"  _calc_top_phase:          {self._avg(self.calc_top_phase_times):.4f}ms ({len(self.calc_top_phase_times)} calls)")
        print(f"  _calc_bottom_phase:       {self._avg(self.calc_bottom_phase_times):.4f}ms ({len(self.calc_bottom_phase_times)} calls)")

        print(f"\nColor Methods (per call):")
        print(f"  _get_top_band_color:      {self._avg(self.get_top_color_times):.4f}ms ({len(self.get_top_color_times)} calls)")
        print(f"  _get_bottom_band_color:   {self._avg(self.get_bottom_color_times):.4f}ms ({len(self.get_bottom_color_times)} calls)")
        print(f"  _blend_colors:            {self._avg(self.blend_colors_times):.4f}ms ({len(self.blend_colors_times)} calls)")

        # Calculate time distribution
        total_codex_bg = self._avg(self.codex_bg_times)
        total_band = self._avg(self.band_boundary_times)
        
        print(f"\nTime Distribution:")
        print(f"  Total _paint_codex_background: {total_codex_bg:.4f}ms")
        print(f"    - Band boundary painting:    {total_band:.4f}ms ({total_band/total_codex_bg*100:.1f}%)")
        print(f"    - Other (fills, calcs):      {total_codex_bg - total_band:.4f}ms ({(total_codex_bg - total_band)/total_codex_bg*100:.1f}%)")

        # Optimization opportunities
        print(f"\nOptimization Opportunities:")
        blend_calls_per_paint = len(self.blend_colors_times) / self.sample_count if self.sample_count > 0 else 0
        print(f"  - _blend_colors called {blend_calls_per_paint:.1f}x per paint")
        print(f"    Total time in _blend_colors: {self._avg(self.blend_colors_times) * blend_calls_per_paint:.4f}ms")
        
        if total_band / total_codex_bg > 0.5:
            print(f"  - Band boundary painting is {total_band/total_codex_bg*100:.0f}% of paint time")
            print(f"    Consider caching gradient if boundary unchanged")
        
        print(f"\nCaching Potential:")
        # Check how often phase calculations are duplicated
        calc_total = (self._avg(self.calc_split_times) + 
                     self._avg(self.calc_top_phase_times) + 
                     self._avg(self.calc_bottom_phase_times))
        color_total = (self._avg(self.get_top_color_times) + 
                      self._avg(self.get_bottom_color_times))
        
        print(f"  Phase calculations:  {calc_total:.4f}ms per paint")
        print(f"  Color generation:    {color_total:.4f}ms per paint")
        print(f"  QLinearGradient:     ~{total_band - color_total:.4f}ms per paint")

        print("\n" + "=" * 70)

        QApplication.quit()


def main() -> int:
    """Run the detailed profiling window."""
    app = QApplication(sys.argv)
    window = DetailedProfileWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
