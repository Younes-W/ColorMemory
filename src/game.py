from __future__ import annotations

import os
import random
from contextlib import suppress
from typing import Sequence

from config import COLOR_MAP, HIGHSCORE_PATH
from utils import darker_color


class ColorMemoryEngine:
    """Encapsulates sequence handling and highscore persistence."""

    def __init__(
        self,
        *,
        color_map: dict[str, str] | None = None,
        highscore_path: str = HIGHSCORE_PATH,
        timer_factor: float = 3.0,
        allowed_words: Sequence[str] | None = None,
    ) -> None:
        self.color_map = color_map or COLOR_MAP
        self.highscore_path = highscore_path
        self.timer_factor = timer_factor
        if allowed_words is None:
            allowed_words = list(self.color_map.keys())
        self.active_words = [word for word in allowed_words if word in self.color_map]
        self.sequence: list[str] = []
        self.round: int = 0

        self._ensure_highscore_file()
        self.highscore: int = self._load_highscore()

    # ------------------------------------------------------------------#
    # Game lifecycle
    # ------------------------------------------------------------------#

    def reset(self) -> None:
        self.sequence.clear()
        self.round = 0

    def prepare_next_round(self) -> dict[str, str | float]:
        """Advance the internal state and return display attributes."""
        self.round += 1
        pool = self.active_words or list(self.color_map.keys())
        word = random.choice(pool)
        self.sequence.append(word)

        available_colors = [
            code for name, code in self.color_map.items() if name != word and name in pool
        ]
        if not available_colors:
            available_colors = list(self.color_map.values())
        text_color = random.choice(available_colors)
        background_color = darker_color(text_color)
        time_budget = float(self.round * self.timer_factor)

        return {
            "word": word,
            "text_color": text_color,
            "background_color": background_color,
            "time_budget": time_budget,
        }

    def evaluate_guess(self, guessed_words: Sequence[str]) -> bool:
        expected = [word.casefold() for word in self.sequence]
        guess_norm = [word.casefold() for word in guessed_words]
        return guess_norm == expected

    def register_failure(self) -> tuple[int, bool, str]:
        score = max(0, self.round - 1)
        new_highscore = score > self.highscore
        if new_highscore:
            self.highscore = score
            self._save_highscore(score)
        solution = " → ".join(self.sequence)
        return score, new_highscore, solution

    def register_success(self) -> None:
        if self.round > self.highscore:
            self.highscore = self.round

    # ------------------------------------------------------------------#
    # Highscore persistence
    # ------------------------------------------------------------------#

    def reset_highscore(self) -> None:
        self.highscore = 0
        self._save_highscore(self.highscore)

    def _ensure_highscore_file(self) -> None:
        if not os.path.exists(self.highscore_path):
            with suppress(OSError):
                with open(self.highscore_path, "w", encoding="utf-8") as file:
                    file.write("0")

    def _load_highscore(self) -> int:
        try:
            with open(self.highscore_path, "r", encoding="utf-8") as file:
                raw = file.read().strip()
                if not raw:
                    return 0
                try:
                    return max(0, int(raw))
                except ValueError:
                    with suppress(Exception):
                        import json

                        data = json.loads(raw)
                        if isinstance(data, dict):
                            return max(0, int(data.get("score", 0)))
                        if isinstance(data, int):
                            return max(0, data)
                    return 0
        except OSError:
            return 0

    def _save_highscore(self, score: int) -> None:
        try:
            with open(self.highscore_path, "w", encoding="utf-8") as file:
                file.write(str(int(score)))
        except OSError:
            pass
