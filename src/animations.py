from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

from utils import blend_hex_colors, hex_to_rgb, rgb_to_hex


class FeedbackAnimator:
    """Animate color transitions and pulse effects for feedback labels."""

    def __init__(self, *, root, label, font, base_color: str, base_size: int = 20) -> None:
        self.root = root
        self.label = label
        self.font = font
        self.base_color = base_color
        self.base_size = base_size
        self.color_animation_id: Optional[str] = None
        self.pulse_animation_id: Optional[str] = None

    def animate_color(self, start_color: str, end_color: str, steps: int = 12, interval: int = 45) -> None:
        self.cancel_color_animation()

        try:
            start_rgb = hex_to_rgb(start_color)
        except ValueError:
            start_rgb = hex_to_rgb(self.base_color)
        end_rgb = hex_to_rgb(end_color)

        def step_animation(step: int = 0) -> None:
            t = min(1.0, step / steps) if steps else 1.0
            current = tuple(int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * t) for i in range(3))
            self.label.configure(text_color=rgb_to_hex(current))
            if step < steps:
                self.color_animation_id = self.root.after(
                    interval,
                    lambda: step_animation(step + 1),
                )
            else:
                self.color_animation_id = None

        step_animation()

    def pulse(self, amplitude: int = 4, steps: int = 8, interval: int = 35) -> None:
        self.cancel_pulse_animation()

        def pulse(step: int = 0) -> None:
            t = step / steps if steps else 1.0
            size = self.base_size + int(amplitude * math.sin(math.pi * t))
            self.font.configure(size=size)
            if step < steps:
                self.pulse_animation_id = self.root.after(
                    interval,
                    lambda: pulse(step + 1),
                )
            else:
                self.font.configure(size=self.base_size)
                self.pulse_animation_id = None

        pulse()

    def cancel_color_animation(self) -> None:
        if self.color_animation_id is not None:
            self.root.after_cancel(self.color_animation_id)
            self.color_animation_id = None

    def cancel_pulse_animation(self) -> None:
        if self.pulse_animation_id is not None:
            self.root.after_cancel(self.pulse_animation_id)
            self.pulse_animation_id = None
            self.font.configure(size=self.base_size)

    def cancel_all(self) -> None:
        self.cancel_color_animation()
        self.cancel_pulse_animation()
        self.label.configure(text_color=self.base_color)


class BackgroundAnimator:
    """Manages the breathing background gradient."""

    def __init__(
        self,
        *,
        root,
        palette: Sequence[str],
        on_color: Callable[[str], None],
    ) -> None:
        self.root = root
        self.palette = palette
        self.on_color = on_color
        self.theta = 0.0
        self.interval = 60

    def start(self, interval: int = 60) -> None:
        self.interval = interval
        self._tick()

    def _tick(self) -> None:
        self.theta = (self.theta + 0.02) % (2 * math.pi)
        mix = (math.sin(self.theta) + 1) / 2
        color = blend_hex_colors(self.palette[0], self.palette[1], mix)

        self.on_color(color)
        self.root.after(self.interval, self._tick)


class WordAnimator:
    """Handles fade and conceal interactions for the displayed word."""

    def __init__(
        self,
        *,
        root,
        container,
        label,
        adjust_font: Callable[[str], None],
        base_bg: str,
        base_text_color: str,
    ) -> None:
        self.root = root
        self.container = container
        self.label = label
        self.adjust_font = adjust_font
        self.base_bg = base_bg
        self.last_word_bg = base_bg
        self.last_word_color = base_text_color
        self.word_fade_id: Optional[str] = None
        self.hide_word_id: Optional[str] = None

    def remember_word_style(self, *, text_color: str, container_color: str) -> None:
        self.last_word_color = text_color
        self.last_word_bg = container_color

    def fade_to(self, start_color: str, target_color: str, duration: int = 220, steps: int = 8) -> None:
        self.cancel_fade()
        start_rgb = hex_to_rgb(start_color)
        end_rgb = hex_to_rgb(target_color)
        interval = int(duration / steps) if steps else duration

        def fade(step: int = 0) -> None:
            t = min(1.0, step / steps) if steps else 1.0
            blended = tuple(int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * t) for i in range(3))
            hex_color = rgb_to_hex(blended)
            self.container.configure(fg_color=hex_color)
            self.label.configure(fg_color=hex_color)
            self.last_word_bg = hex_color
            if step < steps:
                self.word_fade_id = self.root.after(
                    interval,
                    lambda: fade(step + 1),
                )
            else:
                self.word_fade_id = None

        fade()

    def schedule_conceal(self, delay_ms: int) -> None:
        self.cancel_conceal()
        self.hide_word_id = self.root.after(delay_ms, self._conceal_word)

    def cancel_all(self) -> None:
        self.cancel_conceal()
        self.cancel_fade()

    def cancel_conceal(self) -> None:
        if self.hide_word_id is not None:
            self.root.after_cancel(self.hide_word_id)
            self.hide_word_id = None

    def cancel_fade(self) -> None:
        if self.word_fade_id is not None:
            self.root.after_cancel(self.word_fade_id)
            self.word_fade_id = None

    def _conceal_word(self) -> None:
        self.hide_word_id = None
        self.container.configure(fg_color=self.last_word_bg)
        self.label.configure(text="?", text_color=self.last_word_color, fg_color=self.last_word_bg)
        self.adjust_font("?")
