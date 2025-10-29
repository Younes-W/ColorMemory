from __future__ import annotations

import importlib
import os
import platform
import shutil
import subprocess
import threading
import time
from contextlib import suppress
from typing import Callable, Optional

playsound_func: Optional[Callable[[str], None]] = None
with suppress(Exception):  # pragma: no cover - optional dependency
    module = importlib.import_module("playsound")
    playsound_func = getattr(module, "playsound")


class MusicController:
    """Manages background music playback for the game."""

    def __init__(
        self,
        *,
        music_file: str,
        notify: Callable[[str, str], None],
        invoke_later: Optional[Callable[[Callable[[], None]], None]] = None,
    ) -> None:
        self.music_file = music_file
        self.notify = notify
        self.invoke_later = invoke_later or (lambda func: func())
        self.music_thread: Optional[threading.Thread] = None
        self.music_stop_event = threading.Event()
        self.music_mode: Optional[str] = None
        self.music_process: Optional[subprocess.Popen] = None

    def start(self) -> None:
        if self.music_thread and self.music_thread.is_alive():
            return
        if not os.path.exists(self.music_file):
            self.notify("Keine Musikdatei gefunden.", "#c67b1e")
            return

        system = platform.system()
        can_use_afplay = system == "Darwin" and shutil.which("afplay") is not None

        self.music_stop_event.clear()

        if can_use_afplay:
            self.music_mode = "afplay"
            self.music_thread = threading.Thread(
                target=self._music_loop,
                args=("afplay",),
                daemon=True,
            )
            self.music_thread.start()
            return

        if playsound_func is not None:
            self.music_mode = "playsound"
            self.music_thread = threading.Thread(
                target=self._music_loop,
                args=("playsound",),
                daemon=True,
            )
            self.music_thread.start()
            return

        self.notify("Musik nicht verfügbar.", "#c67b1e")

    def stop(self, *, with_feedback: bool = True) -> None:
        self.music_stop_event.set()
        if self.music_mode == "afplay" and self.music_process is not None:
            try:
                self.music_process.terminate()
            except Exception:
                pass
        self.music_mode = None
        if with_feedback:
            self.notify("", "#4b58c2")

    def cleanup(self) -> None:
        self.stop(with_feedback=False)
        if self.music_thread and self.music_thread.is_alive():
            self.music_thread.join(timeout=0.2)

    # ------------------------------------------------------------------#
    # Internal helpers
    # ------------------------------------------------------------------#

    def _music_loop(self, mode: str) -> None:
        error_message: Optional[str] = None

        if mode == "playsound":
            while not self.music_stop_event.is_set():
                try:
                    playsound_func(self.music_file)  # type: ignore[arg-type]
                except FileNotFoundError:
                    error_message = "Keine Musikdatei gefunden."
                    break
                except Exception:
                    error_message = "Musikwiedergabe fehlgeschlagen."
                    break

        elif mode == "afplay":
            while not self.music_stop_event.is_set():
                try:
                    self.music_process = subprocess.Popen(
                        ["afplay", "-v", "0.3", self.music_file],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except FileNotFoundError:
                    error_message = "afplay nicht gefunden."
                    break
                except Exception:
                    error_message = "Musikwiedergabe fehlgeschlagen."
                    break

                while not self.music_stop_event.is_set():
                    if self.music_process.poll() is not None:
                        break
                    time.sleep(0.1)

                if self.music_stop_event.is_set() and self.music_process.poll() is None:
                    try:
                        self.music_process.terminate()
                    except Exception:
                        pass
                    break

            self.music_process = None

        self.invoke_later(lambda: self._finalize_music_loop(error_message))

    def _finalize_music_loop(self, error_message: Optional[str]) -> None:
        self.music_thread = None
        self.music_process = None
        self.music_mode = None
        if error_message:
            self.notify(error_message, "#c67b1e")
        elif not self.music_stop_event.is_set():
            self.notify("Musik beendet.", "#4b58c2")


def play_feedback_sound(sound: str, *, bell: Optional[Callable[[], None]] = None) -> None:
    system = platform.system()

    if system == "Windows":

        def _windows() -> None:
            try:
                import winsound

                alias = winsound.MB_ICONASTERISK if sound == "success" else winsound.MB_ICONHAND
                winsound.MessageBeep(alias)
            except Exception:
                try:
                    import winsound

                    frequency = 880 if sound == "success" else 440
                    winsound.Beep(frequency, 150)
                except Exception:
                    pass

        threading.Thread(target=_windows, daemon=True).start()
    elif system == "Darwin":

        def _macos() -> None:
            sound_name = "Glass.aiff" if sound == "success" else "Basso.aiff"
            path = os.path.join("/System/Library/Sounds", sound_name)
            try:
                subprocess.run(["afplay", path], check=False)
            except FileNotFoundError:
                pass

        threading.Thread(target=_macos, daemon=True).start()
    else:
        if bell is not None:
            try:
                bell()
            except Exception:
                pass
        else:
            try:
                import sys

                sys.stdout.write("\a")
                sys.stdout.flush()
            except Exception:
                pass
