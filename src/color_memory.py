import os
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from animations import BackgroundAnimator, FeedbackAnimator, WordAnimator
from audio import MusicController, play_feedback_sound
from config import (
    ACCENT_BLUE,
    ACTIVE_COLORS,
    CARD_BG,
    FEEDBACK_BASE,
    LOGO_PATH,
    MUSIC_PATH,
    NEUTRAL_BG,
    NEUTRAL_BG_ALT,
    START_DELAY_MS,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TIME_COLOR,
)
from game import ColorMemoryEngine
from utils import darker_color, hex_to_rgb

os.environ.setdefault("TK_SILENCE_DEPRECATION", "1")
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class ColorMemoryGame:
    """Modernised Color Memory UI powered by CustomTkinter with modular helpers."""

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.title("Color Memory")
        self.root.geometry("880x680")
        self.root.minsize(760, 620)
        self.root.configure(fg_color=NEUTRAL_BG)

        self.engine = ColorMemoryEngine(allowed_words=ACTIVE_COLORS)
        self.timer_enabled = ctk.BooleanVar(value=True)
        self.remaining_time: float = 0.0
        self.timer_id: Optional[str] = None
        self.game_active: bool = False
        self.player_sequence: list[str] = []
        self.color_buttons: dict[str, ctk.CTkButton] = {}
        self.enable_buttons_id: Optional[str] = None

        self.feedback_animator: Optional[FeedbackAnimator] = None
        self.background_animator: Optional[BackgroundAnimator] = None
        self.word_animator: Optional[WordAnimator] = None
        self.music_controller: Optional[MusicController] = None

        self.bg_palette = (NEUTRAL_BG, NEUTRAL_BG_ALT)

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
        self.music_controller = MusicController(
            root=self.root,
            music_file=MUSIC_PATH,
            notify=self._show_feedback,
        )
        self._update_score_label(0)
        if self.background_animator:
            self.background_animator.start()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Create the complete customtkinter interface."""

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

        self.selection_frame = ctk.CTkFrame(self.body_frame, fg_color="transparent")
        self.selection_frame.pack(fill="x")

        self.selection_hint_label = ctk.CTkLabel(
            self.selection_frame,
            text="Sequenz durch Tippen auf Farbfelder wiederholen:",
            font=ctk.CTkFont("Helvetica", 15),
            text_color=TEXT_MUTED,
        )
        self.selection_hint_label.pack(anchor="w", pady=(4, 10))

        self.buttons_container = ctk.CTkFrame(self.selection_frame, fg_color="transparent")
        self.buttons_container.pack()

        button_font = ctk.CTkFont("Helvetica", 16, "bold")
        for index, color_name in enumerate(self.engine.active_words):
            hex_code = CARD_BG
            if color_name in self.engine.color_map:
                hex_code = self.engine.color_map[color_name]
            hover = darker_color(hex_code, 0.85)
            text_color = self._ideal_text_color(hex_code)
            button = ctk.CTkButton(
                self.buttons_container,
                text=color_name,
                command=lambda name=color_name: self._on_color_selected(name),
                fg_color=hex_code,
                hover_color=hover,
                text_color=text_color,
                corner_radius=18,
                height=48,
                width=130,
                font=button_font,
                border_width=0,
            )
            button.grid(row=index // 3, column=index % 3, padx=10, pady=8, sticky="ew")
            self.color_buttons[color_name] = button

        for column in range(3):
            self.buttons_container.grid_columnconfigure(column, weight=1)

        self.selection_status_label = ctk.CTkLabel(
            self.selection_frame,
            text="Auswahl: —",
            font=ctk.CTkFont("Helvetica", 14, "bold"),
            text_color=TEXT_MUTED,
        )
        self.selection_status_label.pack(pady=(10, 4))

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

        # Instantiate helpers now that widgets exist
        self.feedback_animator = FeedbackAnimator(
            root=self.root,
            label=self.feedback_label,
            font=self.feedback_font,
            base_color=FEEDBACK_BASE,
            base_size=self.feedback_font.cget("size"),
        )
        self.word_animator = WordAnimator(
            root=self.root,
            container=self.word_container,
            label=self.word_label,
            adjust_font=self._adjust_word_font,
            base_bg=CARD_BG,
            base_text_color=TEXT_PRIMARY,
        )
        self.background_animator = BackgroundAnimator(
            root=self.root,
            palette=self.bg_palette,
            on_color=self._apply_background_color,
        )
        self._set_color_buttons_state("disabled")

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
        if self.feedback_animator:
            self.feedback_animator.cancel_all()
        if self.word_animator:
            self.word_animator.cancel_all()
        self.engine.reset()
        self.remaining_time = 0.0
        self.game_active = True
        self.player_sequence = []
        self.selection_status_label.configure(text="Auswahl: —", text_color=TEXT_MUTED)

        self.start_button.configure(state="disabled")
        self._set_color_buttons_state("disabled")

        self._show_feedback("Merke dir das Wort!", "#5164d8")
        self.word_container.configure(fg_color=CARD_BG)
        self.word_label.configure(text="Bereit?", text_color=TEXT_PRIMARY, fg_color=CARD_BG)
        self._adjust_word_font(text="Bereit?")

        self._update_score_label(0)
        self._update_time_label(0.0 if self.timer_enabled.get() else None)

    def next_round(self) -> None:
        if not self.game_active:
            return

        round_data = self.engine.prepare_next_round()
        word = str(round_data["word"])
        text_color = str(round_data["text_color"])
        background_color = str(round_data["background_color"])
        self.remaining_time = float(round_data["time_budget"])
        self.player_sequence = []
        self.selection_status_label.configure(text="Auswahl: —", text_color=TEXT_MUTED)

        self._update_score_label()

        if self.word_animator:
            self.word_animator.cancel_all()
            self.word_animator.remember_word_style(text_color=text_color, container_color=CARD_BG)
        self.word_container.configure(fg_color=CARD_BG)
        self.word_label.configure(text=word, text_color=text_color, fg_color=CARD_BG)
        self._adjust_word_font(text=word)

        if self.word_animator:
            self.word_animator.fade_to(CARD_BG, background_color)
            self.word_animator.schedule_conceal(1200)
        self._set_color_buttons_state("disabled")
        self._schedule_button_enable(1200)

        self._clear_feedback()

        self.cancel_timer()
        if self.timer_enabled.get():
            self.update_timer()
        else:
            self._update_time_label(None)

        if self.music_controller:
            self.music_controller.start()

    def _on_color_selected(self, color_name: str) -> None:
        if not self.game_active:
            return

        self.player_sequence.append(color_name)
        self.selection_status_label.configure(
            text="Auswahl: " + " · ".join(self.player_sequence),
            text_color=ACCENT_BLUE,
        )
        self._flash_color_button(color_name)

        expected = self.engine.sequence
        index = len(self.player_sequence) - 1

        if index >= len(expected):
            self.cancel_timer()
            self._cancel_button_enable()
            self._handle_failure()
            return

        if self.player_sequence[index].casefold() != expected[index].casefold():
            self.cancel_timer()
            self._cancel_button_enable()
            self._handle_failure()
            return

        if len(self.player_sequence) == len(expected):
            self.cancel_timer()
            self._cancel_button_enable()
            self.engine.register_success()
            play_feedback_sound("success", bell=self.root.bell)
            self._show_feedback("Richtig!", "#2f8c68")
            self._update_score_label()
            self.selection_status_label.configure(text="Auswahl: ✓", text_color="#2f8c68")
            self._set_color_buttons_state("disabled")
            self.root.after(600, self.next_round)

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
        score, new_highscore, solution = self.engine.register_failure()
        play_feedback_sound("failure", bell=self.root.bell)
        message = f"Falsch! Runde {score} geschafft."
        if new_highscore:
            message += " Neuer Highscore!"
        self._show_feedback(message, "#c34d5e")
        if self.music_controller:
            self.music_controller.stop(with_feedback=False)
        self._update_score_label(score)
        self.selection_status_label.configure(text="Auswahl: ✗", text_color="#c34d5e")
        self._handle_stop(
            label_text="Game Over",
            label_color="#c34d5e",
            cleanup_music=False,
            reset_progress=False,
            solution="Lösung: " + solution,
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
        if cleanup_music and self.music_controller:
            self.music_controller.cleanup()
        if self.word_animator:
            self.word_animator.cancel_all()
        self.cancel_timer()
        self._cancel_button_enable()
        self.game_active = False
        if reset_progress:
            self.engine.reset()
        self._set_color_buttons_state("disabled")
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
            self.selection_status_label.configure(text="Auswahl: —", text_color=TEXT_MUTED)
        self.player_sequence = []

    def cancel_timer(self) -> None:
        if self.timer_id is not None:
            self.root.after_cancel(self.timer_id)
            self.timer_id = None

    def _update_score_label(self, current: int | None = None) -> None:
        if current is None:
            current = self.engine.round
        self.score_label.configure(text=f"Runde: {current} · Best: {self.engine.highscore}")

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
                self.remaining_time = float(max(1, self.engine.round) * 2)
            self.update_timer()
        else:
            self._update_time_label(None)

    # ------------------------------------------------------------------#
    # Feedback & animation helpers
    # ------------------------------------------------------------------#

    def _set_color_buttons_state(self, state: str) -> None:
        for button in self.color_buttons.values():
            button.configure(state=state)

    def _enable_color_buttons(self) -> None:
        self.enable_buttons_id = None
        if not self.game_active:
            return
        self._set_color_buttons_state("normal")

    def _schedule_button_enable(self, delay_ms: int) -> None:
        self._cancel_button_enable()
        self.enable_buttons_id = self.root.after(delay_ms, self._enable_color_buttons)

    def _cancel_button_enable(self) -> None:
        if self.enable_buttons_id is not None:
            self.root.after_cancel(self.enable_buttons_id)
            self.enable_buttons_id = None

    def _flash_color_button(self, color_name: str, duration: int = 220) -> None:
        button = self.color_buttons.get(color_name)
        if button is None:
            return
        button.configure(border_width=3, border_color=ACCENT_BLUE)

        def reset_border() -> None:
            button.configure(border_width=0)

        self.root.after(duration, reset_border)

    def _show_feedback(self, message: str, target_color: str) -> None:
        self.feedback_label.configure(text=message)
        current_color = self.feedback_label.cget("text_color")
        if self.feedback_animator:
            self.feedback_animator.animate_color(current_color, target_color)
            self.feedback_animator.pulse()
        else:
            self.feedback_label.configure(text_color=target_color)

    def _clear_feedback(self) -> None:
        if self.feedback_animator:
            self.feedback_animator.cancel_all()
        self.feedback_label.configure(text="", text_color=FEEDBACK_BASE)

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

    def _apply_background_color(self, color: str) -> None:
        self.root.configure(fg_color=color)
        self.body_frame.configure(fg_color=color)
        self.controls_frame.configure(fg_color=color)
        self.selection_frame.configure(fg_color=color)
        self.feedback_label.configure(fg_color=color)
        self.selection_hint_label.configure(fg_color=color)
        self.selection_status_label.configure(fg_color=color)
        self.authors_label.configure(fg_color=color)

    # ------------------------------------------------------------------#
    # Persistence & utilities
    # ------------------------------------------------------------------#

    def reset_highscore(self) -> None:
        self.engine.reset_highscore()
        self._update_score_label(0)
        self._show_feedback("Highscore zurückgesetzt.", "#c67b1e")

    def _on_close(self) -> None:
        if self.music_controller:
            self.music_controller.cleanup()
        self.root.destroy()

    @staticmethod
    def _ideal_text_color(hex_color: str) -> str:
        r, g, b = hex_to_rgb(hex_color)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#1f1f1f" if luminance > 0.6 else "#ffffff"


def main() -> None:
    root = ctk.CTk()
    ColorMemoryGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
