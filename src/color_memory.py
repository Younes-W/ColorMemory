import importlib
import math
import os
import platform
import random
import re
import shutil
import subprocess
import threading
import time
import sys
from contextlib import suppress
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

playsound_func: Optional[Callable[[str], None]] = None
with suppress(Exception):  # pragma: no cover - optional dependency
    module = importlib.import_module("playsound")
    playsound_func = getattr(module, "playsound")


def resource_path(*relative_parts: str, create_parent: bool = False) -> str:
    """Return absolute path to a project resource, supporting PyInstaller bundles."""
    if not relative_parts:
        raise ValueError("resource_path expects at least one relative path component.")

    relative_path = os.path.join(*relative_parts)
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    candidate = os.path.join(base_path, relative_path)

    if os.path.exists(candidate):
        if create_parent:
            os.makedirs(os.path.dirname(candidate), exist_ok=True)
        return candidate

    base_dir_name = os.path.basename(base_path.rstrip(os.sep))
    if base_dir_name == "src":
        project_root = os.path.dirname(base_path)
        fallback = os.path.join(project_root, relative_path)
        if os.path.exists(fallback) or create_parent:
            if create_parent:
                os.makedirs(os.path.dirname(fallback), exist_ok=True)
            return fallback

    if create_parent:
        os.makedirs(os.path.dirname(candidate), exist_ok=True)
    return candidate


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i : i + 2], 16) for i in range(0, 6, 2))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def blend_hex_colors(start: str, end: str, t: float) -> str:
    sr, sg, sb = hex_to_rgb(start)
    er, eg, eb = hex_to_rgb(end)
    r = int(sr + (er - sr) * t)
    g = int(sg + (eg - sg) * t)
    b = int(sb + (eb - sb) * t)
    return rgb_to_hex((r, g, b))


NEUTRAL_BG = "#f6f4ff"
NEUTRAL_BG_ALT = "#ece8ff"
HEADER_BG = "#ffffff"
ACCENT_BLUE = "#6258f5"
TIME_COLOR = "#f76a3e"
FEEDBACK_BASE = "#4b4a6a"
ENTRY_BG = "#ffffff"
ENTRY_TEXT = "#1f1f1f"
TEXT_PRIMARY = "#1f1f1f"
TEXT_MUTED = "#6a7090"
CARD_BG = "#f3efff"
START_DELAY_MS = 800
LOGO_PATH = resource_path("assets", "logo.png")
MUSIC_PATH = resource_path("assets", "music.wav")
HIGHSCORE_PATH = resource_path("data", "highscore.txt", create_parent=True)


COLOR_MAP = {
    "Rot": "#ff9aa0",
    "Blau": "#8bbcff",
    "Grün": "#8be2c0",
    "Gelb": "#ffe7a3",
    "Orange": "#ffc39c",
    "Lila": "#cab3ff",
    "Pink": "#ffb0dc",
    "Braun": "#cba786",
    "Schwarz": "#5a5f73",
    "Weiß": "#e6e9f6",
    "Grau": "#a2b3d4",
}


class ColorMemoryGame:
    """Modernised Color Memory UI powered by CustomTkinter (logic unchanged)."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("Color Memory")
        self.root.geometry("880x680")
        self.root.minsize(760, 620)
        self.root.configure(fg_color=NEUTRAL_BG)

        # Gameplay state
        self.sequence: list[str] = []
        self.round: int = 0
        self.remaining_time: float = 0.0
        self.timer_id: str | None = None
        self.game_active: bool = False
        self.feedback_color_animation_id: str | None = None
        self.feedback_pulse_animation_id: str | None = None
        self.word_fade_id: str | None = None
        self.hide_word_id: str | None = None

        # Highscore persistence
        self.highscore_path = HIGHSCORE_PATH
        if not os.path.exists(self.highscore_path):
            with suppress(OSError):
                with open(self.highscore_path, "w", encoding="utf-8") as file:
                    file.write("0")
        self.highscore: int = self._load_highscore()

        # Background animation palette
        self.bg_palette = (NEUTRAL_BG, NEUTRAL_BG_ALT)
        self.bg_anim_theta = 0.0

        # Music control
        self.music_thread: threading.Thread | None = None
        self.music_stop_event = threading.Event()
        self.music_file = MUSIC_PATH
        self.music_mode: Optional[str] = None
        self.music_process: Optional[subprocess.Popen] = None

        # Timer toggle variable
        self.timer_enabled = ctk.BooleanVar(value=True)

        self.logo_source: Optional[Image.Image] = None
        self.logo_icon_photo: Optional[ImageTk.PhotoImage] = None
        self.logo_image: Optional[ctk.CTkImage] = None
        self.logo_display_size: Optional[tuple[int, int]] = None

        try:
            self.logo_source = Image.open(LOGO_PATH)
        except (FileNotFoundError, OSError):
            self.logo_source = None

        if self.logo_source is not None:
            original_width, original_height = self.logo_source.size
            icon_bitmap = self.logo_source.copy()
            icon_bitmap.thumbnail((240, 240), Image.LANCZOS)
            self.logo_icon_photo = ImageTk.PhotoImage(icon_bitmap)
            self.root.iconphoto(True, self.logo_icon_photo)

            # Determine a display size while respecting aspect ratio
            target_width = 360
            target_height = 180
            scale = target_width / original_width if original_width else 1.0
            scaled_height = int(original_height * scale)
            if scaled_height > target_height and original_height:
                scale = target_height / original_height
            display_width = max(260, int(original_width * scale))
            display_height = max(140, int(original_height * scale))
            self.logo_display_size = (display_width, display_height)

        self._build_ui()
        self._update_score_label(0)
        self._animate_background()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Create the complete customtkinter interface."""

        # -- Header ---------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=20, pady=(16, 12))

        title_shell = ctk.CTkFrame(
            self.header_frame,
            fg_color="#ffffff",
            corner_radius=20,
            border_width=1,
            border_color="#d7dafc",
        )
        title_shell.pack(fill="x", padx=6, pady=0)

        inner_header = ctk.CTkFrame(title_shell, fg_color="#f6f4ff", corner_radius=16)
        inner_header.pack(fill="x", padx=12, pady=10)

        title_container = ctk.CTkFrame(inner_header, fg_color="transparent")
        title_container.pack(fill="x", padx=6, pady=(4, 8))

        if self.logo_source is not None:
            if self.logo_display_size is None:
                self.logo_display_size = (360, 180)
            self.logo_image = ctk.CTkImage(
                light_image=self.logo_source,
                size=self.logo_display_size,
            )
            self.logo_label = ctk.CTkLabel(title_container, image=self.logo_image, text="")
            self.logo_label.pack(pady=(6, 10))
        else:
            text_holder = ctk.CTkFrame(title_container, fg_color="transparent")
            text_holder.pack(expand=True, fill="x")

            # Subtle drop-shadow effect for the fallback title text
            self.title_shadow = ctk.CTkLabel(
                text_holder,
                text="🎨 Color Memory",
                font=ctk.CTkFont("Helvetica", 32, "bold"),
                text_color="#e4e8ff",
            )
            self.title_shadow.place(relx=0.5, rely=0.5, anchor="center", x=2, y=4)

            self.title_label = ctk.CTkLabel(
                text_holder,
                text="🎨 Color Memory",
                font=ctk.CTkFont("Helvetica", 32, "bold"),
                text_color=ACCENT_BLUE,
            )
            self.title_label.place(relx=0.5, rely=0.5, anchor="center")

        stats_frame = ctk.CTkFrame(inner_header, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=(0, 2))

        self.score_label = ctk.CTkLabel(
            stats_frame,
            text="",
            font=ctk.CTkFont("Helvetica", 18, "bold"),
            text_color="#373d63",
        )
        self.score_label.pack(side="left")

        self.time_label = ctk.CTkLabel(
            stats_frame,
            text="Zeit: 0.0s",
            font=ctk.CTkFont("Helvetica", 18, "bold"),
            text_color="#d95830",
        )
        self.time_label.pack(side="right")

        # -- Body -----------------------------------------------------------
        self.body_frame = ctk.CTkFrame(self.root, fg_color=NEUTRAL_BG, corner_radius=18)
        self.body_frame.pack(fill="both", expand=True, padx=20, pady=(0, 18))

        word_shell = ctk.CTkFrame(
            self.body_frame,
            fg_color="#ffffff",
            corner_radius=18,
            border_width=1,
            border_color="#d7dafc",
        )
        word_shell.pack(fill="both", expand=True, pady=(10, 20))

        self.word_container = ctk.CTkFrame(word_shell, fg_color="#f6f4ff", corner_radius=14)
        self.word_container.pack(fill="both", expand=True, padx=12, pady=12)
        self.word_container.pack_propagate(False)

        self.word_label = ctk.CTkLabel(
            self.word_container,
            text="Drücke Start",
            font=ctk.CTkFont("Helvetica", 62, "bold"),
            text_color=TEXT_PRIMARY,
        )
        self.word_label.pack(expand=True)

        # -- Controls -------------------------------------------------------
        self.controls_frame = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.controls_frame.pack(fill="x", pady=(0, 18))

        self.start_button = ctk.CTkButton(
            self.controls_frame,
            text="Start",
            command=self.start_game,
            fg_color="#72d0c2",
            hover_color="#63c6b7",
            text_color=TEXT_PRIMARY,
            corner_radius=18,
            height=44,
            width=120,
            font=ctk.CTkFont("Helvetica", 16, "bold"),
        )
        self.start_button.pack(side="left")

        self.stop_button = ctk.CTkButton(
            self.controls_frame,
            text="Stopp",
            command=self.stop_game,
            fg_color="#f17b86",
            hover_color="#e96a76",
            text_color=TEXT_PRIMARY,
            corner_radius=18,
            height=44,
            width=120,
            font=ctk.CTkFont("Helvetica", 16, "bold"),
        )
        self.stop_button.pack(side="left", padx=(16, 0))

        self.timer_toggle = ctk.CTkCheckBox(
            self.controls_frame,
            text="Timer aktiv",
            variable=self.timer_enabled,
            command=self._toggle_timer,
            font=ctk.CTkFont("Helvetica", 14, "bold"),
            fg_color="#b8bff9",
            hover_color="#a7aff3",
            border_color="#5d68dc",
            text_color=ACCENT_BLUE,
            corner_radius=14,
            width=24,
            height=24,
        )
        self.timer_toggle.pack(side="left", padx=(24, 0))
        self.timer_toggle.select()

        self.reset_button = ctk.CTkButton(
            self.controls_frame,
            text="Highscore Reset",
            command=self.reset_highscore,
            fg_color="#f4c371",
            hover_color="#ecb65b",
            text_color=TEXT_PRIMARY,
            corner_radius=18,
            height=44,
            width=160,
            font=ctk.CTkFont("Helvetica", 16, "bold"),
        )
        self.reset_button.pack(side="left", padx=(24, 0))

        # -- Entry ----------------------------------------------------------
        self.entry_frame = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.entry_frame.pack(fill="x")

        self.entry_hint_label = ctk.CTkLabel(
            self.entry_frame,
            text='Sequenz eingeben (z. B. "Blau, Grün"):',
            font=ctk.CTkFont("Helvetica", 15),
            text_color=TEXT_MUTED,
        )
        self.entry_hint_label.pack(anchor="w", pady=(4, 6))

        self.input_var = ctk.StringVar()
        self.entry = ctk.CTkEntry(
            self.entry_frame,
            textvariable=self.input_var,
            font=ctk.CTkFont("Helvetica", 20),
            fg_color=ENTRY_BG,
            text_color=ENTRY_TEXT,
            border_color="#c5cdea",
            border_width=2,
            corner_radius=14,
            height=44,
        )
        self.entry.pack(fill="x")
        self.entry.configure(state="disabled")
        self.entry.bind("<Return>", lambda _event: self.submit_guess())

        self.submit_button = ctk.CTkButton(
            self.entry_frame,
            text="Überprüfen",
            command=self.submit_guess,
            fg_color="#8ea1ff",
            hover_color="#7b90ff",
            text_color="#1f2233",
            text_color_disabled="#555977",
            corner_radius=18,
            height=44,
            width=140,
            font=ctk.CTkFont("Helvetica", 16, "bold"),
        )
        self.submit_button.pack(pady=(14, 4))
        self.submit_button.configure(state="disabled")

        self.feedback_font = ctk.CTkFont("Helvetica", 20, "bold")
        self.feedback_label = ctk.CTkLabel(
            self.body_frame,
            text="",
            font=self.feedback_font,
            text_color=FEEDBACK_BASE,
        )
        self.feedback_label.pack(pady=(6, 4))

        self.authors_label = ctk.CTkLabel(
            self.body_frame,
            text="© 2025 – Younes Wimmer · Parnia Esfahani · John Grosch",
            font=ctk.CTkFont("Helvetica", 16, "bold"),
            text_color="#6b7adb",
        )
        self.authors_label.pack(pady=(18, 0))

    # ------------------------------------------------------------------#
    # Gameplay flow (logic preserved – only UI calls adjusted)
    # ------------------------------------------------------------------#

    def start_game(self) -> None:
        if self.game_active:
            return
        self._initialize_game_state()
        self.root.after(START_DELAY_MS, self.next_round)

    def stop_game(self) -> None:
        if not self.game_active:
            self._show_feedback("Kein Spiel läuft.", "#d48b1f")
            return
        self._show_feedback("Spiel gestoppt.", "#c34d5e")
        self._handle_stop()

    def _initialize_game_state(self) -> None:
        self.cancel_timer()
        self._cancel_feedback_animations()
        self._cancel_word_fade()
        self._cancel_word_hide()
        self.sequence = []
        self.round = 0
        self.game_active = True

        self.start_button.configure(state="disabled")
        self.entry.configure(state="normal")
        self.submit_button.configure(state="normal")
        self.input_var.set("")

        self._show_feedback("Merke dir das Wort!", "#5164d8")
        self.word_container.configure(fg_color=CARD_BG)
        self.word_label.configure(text="Bereit?", text_color=TEXT_PRIMARY, fg_color=CARD_BG)
        self._adjust_word_font(text="Bereit?")

        self._update_score_label(0)
        self._update_time_label(0.0 if self.timer_enabled.get() else None)
        self.entry.focus_set()

    def next_round(self) -> None:
        if not self.game_active:
            return

        self.round += 1
        self._update_score_label()

        word = random.choice(list(COLOR_MAP.keys()))
        self.sequence.append(word)

        text_color = random.choice([code for code in COLOR_MAP.values() if code != COLOR_MAP[word]])
        bg_color = self._darker_color(text_color)

        self._cancel_word_hide()
        self.word_container.configure(fg_color=CARD_BG)
        self.word_label.configure(text=word, text_color=text_color, fg_color=CARD_BG)
        self.word_label._last_word_color = text_color  # store for conceal stage
        self.word_container._last_word_bg = self.word_container.cget("fg_color")
        self._adjust_word_font(text=word)
        self._fade_word_container(bg_color)

        # Hide the word after a short interval to force memorisation
        self.hide_word_id = self.root.after(1200, self._conceal_word)

        self.input_var.set("")
        self.entry.focus_set()
        self._clear_feedback()

        self.remaining_time = float(self.round * 3)
        self.cancel_timer()
        if self.timer_enabled.get():
            self.update_timer()
        else:
            self._update_time_label(None)
        self._start_music()

    def submit_guess(self) -> None:
        if not self.game_active:
            return

        guess = self.input_var.get().strip()
        if not guess:
            self._show_feedback("Bitte gib die Sequenz ein.", "#d48b1f")
            return

        parts = [segment.strip() for segment in re.split(r"[,;\s]+", guess) if segment.strip()]
        guessed_words = [word.casefold() for word in parts]
        expected_words = [word.casefold() for word in self.sequence]

        self.cancel_timer()

        if guessed_words == expected_words:
            self._play_sound("success")
            self._show_feedback("Richtig!", "#2f8c68")
            self.root.after(600, self.next_round)
        else:
            self._handle_failure()

    def update_timer(self) -> None:
        if not self.game_active or not self.timer_enabled.get():
            return

        self._update_time_label(self.remaining_time)

        if self.remaining_time <= 0:
            self._handle_failure()
            return

        self.remaining_time = round(self.remaining_time - 0.1, 1)
        self.timer_id = self.root.after(100, self.update_timer)

    def _handle_failure(self) -> None:
        score = max(0, self.round - 1)
        self._play_sound("failure")
        new_highscore = score > self.highscore
        message = f"Falsch! Runde {score} geschafft."
        if new_highscore:
            self.highscore = score
            self._save_highscore(score)
            message += " Neuer Highscore!"
        self._show_feedback(message, "#c34d5e")
        self._music_cleanup()
        self._update_score_label(score)
        solution_text = "Lösung: " + " → ".join(self.sequence)
        self._handle_stop(
            label_text="Game Over",
            label_color="#c34d5e",
            cleanup_music=False,
            reset_progress=False,
            solution=solution_text,
        )

    def _handle_stop(
        self,
        label_text: str = "Gestoppt",
        label_color: str = "#c34d5e",
        *,
        cleanup_music: bool = True,
        reset_progress: bool = True,
        solution: str | None = None,
    ) -> None:
        if cleanup_music:
            self._music_cleanup()
        self._cancel_word_hide()
        self.cancel_timer()
        self.game_active = False
        if reset_progress:
            self.sequence = []
            self.round = 0
        self.entry.configure(state="disabled")
        self.submit_button.configure(state="disabled")
        self.start_button.configure(state="normal")
        self.remaining_time = 0.0
        self._update_time_label(self.remaining_time if self.timer_enabled.get() else None)
        self.word_label.configure(text=label_text, text_color=label_color, fg_color=CARD_BG)
        self.word_container.configure(fg_color=CARD_BG)
        if solution:
            self.word_label.configure(text=solution, text_color=TEXT_PRIMARY, fg_color=CARD_BG)
            self._adjust_word_font(text=solution)
        if reset_progress:
            self._update_score_label(0)

    def cancel_timer(self) -> None:
        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

    def _update_score_label(self, current: int | None = None) -> None:
        if current is None:
            current = self.round
        self.score_label.configure(text=f"Runde: {current} · Best: {self.highscore}")

    def _update_time_label(self, seconds: float | None) -> None:
        if seconds is None:
            self.time_label.configure(text="Zeit: ∞", text_color=TIME_COLOR)
            return
        display = max(0.0, seconds)
        self.time_label.configure(text=f"Zeit: {display:0.1f}s", text_color=TIME_COLOR)

    def _toggle_timer(self) -> None:
        enabled = self.timer_enabled.get()
        if enabled:
            self._show_feedback("Timer aktiviert.", "#4352c5")
        else:
            self._show_feedback("Timer deaktiviert.", "#c67b1e")

        if not self.game_active:
            self._update_time_label(0.0 if enabled else None)
            return
        self.cancel_timer()
        if enabled:
            if self.remaining_time <= 0:
                self.remaining_time = float(self.round * 2)
            self.update_timer()
        else:
            self._update_time_label(None)

    # ------------------------------------------------------------------#
    # Music handling (unchanged behaviour, modernised feedback)
    # ------------------------------------------------------------------#

    def _start_music(self) -> None:
        if self.music_thread and self.music_thread.is_alive():
            return
        if not os.path.exists(self.music_file):
            self._show_feedback("Keine Musikdatei gefunden.", "#c67b1e")
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

        self._show_feedback("Musik nicht verfügbar.", "#c67b1e")

    def _stop_music(self, with_feedback: bool = True) -> None:
        self.music_stop_event.set()
        if self.music_mode == "afplay" and self.music_process is not None:
            try:
                self.music_process.terminate()
            except Exception:
                pass
        self.music_mode = None
        if with_feedback:
            self._show_feedback("Musik gestoppt.", "#4b58c2")

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

        self.root.after(0, lambda: self._finalize_music_loop(error_message))

    def _finalize_music_loop(self, error_message: Optional[str]) -> None:
        self.music_thread = None
        self.music_process = None
        self.music_mode = None
        if error_message:
            self._show_feedback(error_message, "#c67b1e")
        elif not self.music_stop_event.is_set():
            self._show_feedback("Musik beendet.", "#4b58c2")

    # ------------------------------------------------------------------#
    # Feedback & animation helpers
    # ------------------------------------------------------------------#

    def _show_feedback(self, message: str, target_color: str) -> None:
        self.feedback_label.configure(text=message)
        self._animate_feedback_color(self.feedback_label.cget("text_color"), target_color)
        self._pulse_feedback()

    def _clear_feedback(self) -> None:
        self._cancel_feedback_animations()
        self.feedback_label.configure(text="", text_color=FEEDBACK_BASE)

    def _animate_feedback_color(
        self,
        start_color: str,
        end_color: str,
        steps: int = 12,
        interval: int = 45,
    ) -> None:
        self._cancel_feedback_color_animation()

        try:
            start_rgb = hex_to_rgb(start_color)
        except ValueError:
            start_rgb = hex_to_rgb(FEEDBACK_BASE)
        end_rgb = hex_to_rgb(end_color)

        def step_animation(step: int = 0) -> None:
            t = min(1.0, step / steps)
            current = tuple(
                int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * t) for i in range(3)
            )
            self.feedback_label.configure(text_color=rgb_to_hex(current))
            if step < steps:
                self.feedback_color_animation_id = self.root.after(
                    interval,
                    lambda: step_animation(step + 1),
                )
            else:
                self.feedback_color_animation_id = None

        step_animation()

    def _pulse_feedback(self, amplitude: int = 4, steps: int = 8, interval: int = 35) -> None:
        self._cancel_feedback_pulse_animation()
        base_size = 20

        def pulse(step: int = 0) -> None:
            t = step / steps
            size = base_size + int(amplitude * math.sin(math.pi * t))
            self.feedback_font.configure(size=size)
            if step < steps:
                self.feedback_pulse_animation_id = self.root.after(
                    interval,
                    lambda: pulse(step + 1),
                )
            else:
                self.feedback_font.configure(size=base_size)
                self.feedback_pulse_animation_id = None

        pulse()

    def _cancel_feedback_color_animation(self) -> None:
        if self.feedback_color_animation_id is not None:
            self.root.after_cancel(self.feedback_color_animation_id)
            self.feedback_color_animation_id = None

    def _cancel_feedback_pulse_animation(self) -> None:
        if self.feedback_pulse_animation_id is not None:
            self.root.after_cancel(self.feedback_pulse_animation_id)
            self.feedback_pulse_animation_id = None
            self.feedback_font.configure(size=20)

    def _cancel_feedback_animations(self) -> None:
        self._cancel_feedback_color_animation()
        self._cancel_feedback_pulse_animation()

    def _cancel_word_hide(self) -> None:
        if self.hide_word_id is not None:
            self.root.after_cancel(self.hide_word_id)
            self.hide_word_id = None

    def _conceal_word(self) -> None:
        self.hide_word_id = None
        if not self.game_active:
            return
        last_color = getattr(self.word_label, "_last_word_color", TEXT_PRIMARY)
        last_bg = getattr(self.word_container, "_last_word_bg", CARD_BG)
        self.word_container.configure(fg_color=last_bg)
        self.word_label.configure(text="?", text_color=last_color, fg_color=last_bg)
        self._adjust_word_font(text="?")

    def _adjust_word_font(self, text: str | None = None) -> None:
        if text is None:
            current = self.word_label.cget("text")
            text = current if isinstance(current, str) else ""
        length = len(text)
        base_size = 62
        if length <= 6:
            size = base_size
        else:
            size = max(16, int(base_size - (length - 6) * 2.0))
        self.word_label.configure(font=ctk.CTkFont("Helvetica", size, "bold"), wraplength=540)

    def _fade_word_container(self, target_color: str, duration: int = 220, steps: int = 8) -> None:
        self._cancel_word_fade()
        start_rgb = hex_to_rgb(CARD_BG)
        end_rgb = hex_to_rgb(target_color)

        def fade(step: int = 0) -> None:
            t = min(1.0, step / steps)
            blended = tuple(
                int(start_rgb[i] + (end_rgb[i] - start_rgb[i]) * t) for i in range(3)
            )
            hex_color = rgb_to_hex(blended)
            self.word_container.configure(fg_color=hex_color)
            self.word_label.configure(fg_color=hex_color)
            self.word_container._last_word_bg = hex_color
            if step < steps:
                self.word_fade_id = self.root.after(
                    int(duration / steps),
                    lambda: fade(step + 1),
                )
            else:
                self.word_fade_id = None

        fade()

    def _cancel_word_fade(self) -> None:
        if self.word_fade_id is not None:
            self.root.after_cancel(self.word_fade_id)
            self.word_fade_id = None

    def _animate_background(self, interval: int = 60) -> None:
        self.bg_anim_theta = (self.bg_anim_theta + 0.02) % (2 * math.pi)
        mix = (math.sin(self.bg_anim_theta) + 1) / 2
        color = blend_hex_colors(self.bg_palette[0], self.bg_palette[1], mix)

        self.root.configure(fg_color=color)
        self.body_frame.configure(fg_color=color)
        self.controls_frame.configure(fg_color=color)
        self.entry_frame.configure(fg_color=color)
        self.feedback_label.configure(fg_color=color)
        self.entry_hint_label.configure(fg_color=color)
        self.authors_label.configure(fg_color=color)
        self.entry.configure(fg_color=ENTRY_BG, text_color=ENTRY_TEXT)
        self.root.after(interval, self._animate_background)

    # ------------------------------------------------------------------#
    # Persistence & utilities
    # ------------------------------------------------------------------#

    def _play_sound(self, sound: str) -> None:
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
            try:
                self.root.bell()
            except Exception:
                pass

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
        self._update_score_label()

    def reset_highscore(self) -> None:
        self.highscore = 0
        self._save_highscore(self.highscore)
        self._show_feedback("Highscore zurückgesetzt.", "#c67b1e")

    @staticmethod
    def _darker_color(hex_color: str, factor: float = 0.6) -> str:
        hex_color = hex_color.lstrip("#")
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
        except ValueError:
            return "#181f3a"

        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _music_cleanup(self) -> None:
        self._stop_music(with_feedback=False)
        if self.music_thread and self.music_thread.is_alive():
            self.music_thread.join(timeout=0.2)

    def _on_close(self) -> None:
        self._music_cleanup()
        self.root.destroy()


def main() -> None:
    root = ctk.CTk()
    ColorMemoryGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
