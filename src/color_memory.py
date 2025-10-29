import asyncio
import os
import time
import inspect
from concurrent.futures import Future
from typing import Any, Callable, Coroutine, Optional

import flet as ft

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


class ColorMemoryApp:
    """Flet implementation of the Color Memory Game."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.engine = ColorMemoryEngine(allowed_words=ACTIVE_COLORS)
        call_from_thread = getattr(self.page, "call_from_thread", None)

        def notify_callback(message: str, color: str) -> None:
            if callable(call_from_thread):
                call_from_thread(lambda: self._show_feedback(message, color))
            else:
                self._show_feedback(message, color)

        def invoke_later(func: Callable[[], None]) -> None:
            if callable(call_from_thread):
                call_from_thread(func)
            else:
                func()

        self.music = MusicController(
            music_file=MUSIC_PATH,
            notify=notify_callback,
            invoke_later=invoke_later,
        )

        # Runtime state
        self.player_name: str = "Spieler"
        self.game_active: bool = False
        self.tiles_enabled: bool = False
        self.timer_enabled: bool = False
        self.remaining_time: float = 0.0
        self.timer_deadline: Optional[float] = None
        self.player_sequence: list[str] = []
        self.session_start_time: float = 0.0
        self.round_start_time: float = 0.0

        # Async tasks
        self.timer_task: Optional[Any] = None
        self.round_delay_task: Optional[Any] = None
        self.flash_tasks: dict[str, Any] = {}
        self._tracked_tasks: set[asyncio.Task] = set()
        self._tracked_futures: set[Future] = set()

        # UI controls (initialised in setup)
        self.menu_container: Optional[ft.Control] = None
        self.game_container: Optional[ft.Control] = None
        self.player_field: Optional[ft.TextField] = None
        self.round_text: Optional[ft.Text] = None
        self.best_text: Optional[ft.Text] = None
        self.timer_text: Optional[ft.Text] = None
        self.player_badge: Optional[ft.Text] = None
        self.word_text: Optional[ft.Text] = None
        self.word_container: Optional[ft.Container] = None
        self.selection_status: Optional[ft.Text] = None
        self.feedback_text: Optional[ft.Text] = None
        self.color_tiles: dict[str, ft.Container] = {}
        self.timer_switch: Optional[ft.Switch] = None
        self.summary_dialog: Optional[ft.AlertDialog] = None

    async def setup(self) -> None:
        self.page.title = "Color Memory"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 24
        self.page.bgcolor = NEUTRAL_BG
        self.page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
        self.page.vertical_alignment = ft.MainAxisAlignment.CENTER
        self.page.window_bgcolor = NEUTRAL_BG
        self.page.on_close = self._on_page_close

        menu = await self._build_menu_view()
        game = await self._build_game_view()
        self.menu_container = menu
        self.game_container = game
        self.game_container.visible = False

        root = ft.Container(
            content=ft.Stack(
                controls=[self.menu_container, self.game_container],
                expand=True,
            ),
            bgcolor=NEUTRAL_BG,
            expand=True,
        )
        self.page.add(root)
        self.page.update()

    async def _build_menu_view(self) -> ft.Container:
        subtitle = ft.Text(
            "Merke dir die Farbwörter und klicke anschließend der Reihe nach auf die passenden Kacheln.",
            size=18,
            text_align=ft.TextAlign.CENTER,
            color=TEXT_MUTED,
        )

        def _on_submit(e: ft.ControlEvent) -> None:
            self._spawn(self._handle_menu_start)

        self.player_field = ft.TextField(
            label="Dein Name",
            hint_text="z. B. Alex",
            width=260,
            border_radius=14,
            text_align=ft.TextAlign.CENTER,
            autofocus=True,
            on_submit=_on_submit,
        )

        start_button = ft.FilledButton(
            "Spiel starten",
            icon="play_arrow_rounded",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
            on_click=lambda e: self._spawn(self._handle_menu_start),
            width=220,
            height=48,
        )
        exit_button = ft.TextButton(
            "Beenden",
            icon="logout_rounded",
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
            on_click=lambda e: self.page.window_close(),
            width=180,
            height=44,
        )

        logo_control: Optional[ft.Control] = None
        if os.path.exists(LOGO_PATH):
            logo_control = ft.Image(
                src=LOGO_PATH,
                height=180,
                fit=ft.ImageFit.CONTAIN,
            )

        content = ft.Column(
            controls=[
                *( [logo_control] if logo_control else [] ),
                subtitle,
                ft.Container(height=24),
                self.player_field,
                ft.Container(height=12),
                start_button,
                exit_button,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            expand=True,
        )

        card = ft.Container(
            content=content,
            padding=40,
            bgcolor=NEUTRAL_BG_ALT,
            border_radius=28,
            border=ft.border.all(2, ACCENT_BLUE + "20"),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=24,
                color=ACCENT_BLUE + "1A",
                offset=ft.Offset(0, 12),
            ),
            alignment=ft.alignment.center,
        )
        return ft.Container(content=card, alignment=ft.alignment.center, expand=True)

    async def _build_game_view(self) -> ft.Container:
        self.round_text = ft.Text("Runde: 0", size=20, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY)
        self.best_text = ft.Text(
            f"Best: {self.engine.highscore} · {self.engine.best_player}",
            size=20,
            weight=ft.FontWeight.W_600,
            color=ACCENT_BLUE,
        )
        self.timer_text = ft.Text("Zeit: ∞", size=20, weight=ft.FontWeight.W_600, color=TIME_COLOR)
        self.player_badge = ft.Text("👤 Spieler", size=18, color=TEXT_MUTED)

        stats_row = ft.ResponsiveRow(
            controls=[
                ft.Container(self.round_text, col={"xs": 12, "sm": 6, "md": 3}),
                ft.Container(self.best_text, alignment=ft.alignment.center, col={"xs": 12, "sm": 6, "md": 3}),
                ft.Container(self.timer_text, alignment=ft.alignment.center, col={"xs": 12, "sm": 6, "md": 3}),
                ft.Container(self.player_badge, alignment=ft.alignment.center_right, col={"xs": 12, "sm": 6, "md": 3}),
            ],
            run_spacing=12,
        )

        logo_controls: list[ft.Control] = []
        if os.path.exists(LOGO_PATH):
            game_logo = ft.Image(
                src=LOGO_PATH,
                height=160,
                fit=ft.ImageFit.CONTAIN,
            )
            logo_controls.append(
                ft.Container(
                    content=game_logo,
                    alignment=ft.alignment.center,
                )
            )
        if not logo_controls:
            logo_controls.append(ft.Container(height=0))
        logo_section = ft.Column(
            controls=logo_controls,
            spacing=6,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

        authors_footer = ft.Container(
            content=ft.Text(
                "Younes Wimmer · John Grosch · Parnia Esfahani",
                size=18,
                weight=ft.FontWeight.W_600,
                color=TEXT_MUTED,
                text_align=ft.TextAlign.CENTER,
            ),
            alignment=ft.alignment.center,
            padding=ft.padding.only(top=12, bottom=12),
        )

        self.word_text = ft.Text(
            "Drücke Start",
            size=56,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            color=TEXT_PRIMARY,
        )
        self.word_container = ft.Container(
            content=ft.Column(
                [self.word_text],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            bgcolor=CARD_BG,
            padding=30,
            border_radius=24,
            height=240,
            alignment=ft.alignment.center,
            animate=ft.Animation(400, ft.AnimationCurve.EASE_IN_OUT),
        )

        self.selection_status = ft.Text(
            "Auswahl: —",
            size=18,
            weight=ft.FontWeight.W_600,
            color=TEXT_MUTED,
            text_align=ft.TextAlign.CENTER,
        )

        tiles_row = ft.ResponsiveRow(alignment=ft.MainAxisAlignment.CENTER, spacing=12, run_spacing=12)
        self.color_tiles = {}
        for name in self.engine.active_words:
            base_color = self.engine.color_map.get(name, CARD_BG)
            text_color = self._ideal_text_color(base_color)
            tile = ft.Container(
                content=ft.Column(
                    [
                        ft.Text(name, size=20, weight=ft.FontWeight.BOLD, color=text_color, text_align=ft.TextAlign.CENTER),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    expand=True,
                ),
                bgcolor=base_color,
                padding=20,
                border_radius=24,
                height=120,
                alignment=ft.alignment.center,
                animate=ft.Animation(250, ft.AnimationCurve.EASE_IN_OUT),
                animate_scale=ft.Animation(150, ft.AnimationCurve.EASE_IN_OUT),
                col={"xs": 12, "sm": 6, "md": 4, "lg": 3, "xl": 2},
            )
            tile.on_click = self._create_color_handler(name)
            tiles_row.controls.append(tile)
            self.color_tiles[name] = tile

        self.feedback_text = ft.Text(
            "",
            size=18,
            weight=ft.FontWeight.W_600,
            text_align=ft.TextAlign.CENTER,
            color=FEEDBACK_BASE,
        )

        controls_row = ft.ResponsiveRow(
            controls=[
                ft.FilledButton(
                    "Start",
                    icon="play_circle_filled_rounded",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
                    on_click=lambda e: self._spawn(self._start_game),
                    height=44,
                    col={"xs": 12, "sm": 6, "md": 3},
                ),
                ft.OutlinedButton(
                    "Stop",
                    icon="pause_circle_filled_rounded",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
                    on_click=lambda e: self._spawn(lambda: self._stop_game(manual=True)),
                    height=44,
                    col={"xs": 12, "sm": 6, "md": 3},
                ),
                ft.OutlinedButton(
                    "Highscore zurücksetzen",
                    icon="restart_alt_rounded",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
                    on_click=lambda e: self._spawn(self._reset_highscore),
                    height=44,
                    col={"xs": 12, "sm": 6, "md": 3},
                ),
                ft.OutlinedButton(
                    "Zum Menü",
                    icon="home_rounded",
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=16)),
                    on_click=lambda e: self._spawn(self._return_to_menu),
                    height=44,
                    col={"xs": 12, "sm": 6, "md": 3},
                ),
            ],
            run_spacing=12,
        )

        self.timer_switch = ft.Switch(
            label="Timer aktiv",
            value=self.timer_enabled,
            on_change=lambda e: self._spawn(lambda: self._toggle_timer(e.control.value)),
        )
        timer_row = ft.Row(
            controls=[self.timer_switch],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        layout = ft.Column(
            controls=[
                ft.Column(
                    controls=[
                        stats_row,
                        logo_section,
                        self.word_container,
                        self.selection_status,
                        tiles_row,
                        self.feedback_text,
                        controls_row,
                        timer_row,
                    ],
                    spacing=20,
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                authors_footer,
            ],
            spacing=8,
            expand=True,
        )

        return ft.Container(
            content=layout,
            expand=True,
            alignment=ft.alignment.center,
        )

    def _create_color_handler(self, color_name: str) -> Callable[[ft.ControlEvent], None]:
        async def handler(_: ft.ControlEvent) -> None:
            await self._on_color_selected(color_name)

        def wrapper(event: ft.ControlEvent) -> None:
            self._spawn(lambda: handler(event))

        return wrapper

    async def _handle_menu_start(self) -> None:
        if self.player_field:
            value = (self.player_field.value or "").strip()
            if value:
                self.player_name = value
            else:
                self.player_name = "Spieler"
            self.player_field.value = self.player_name
        self.player_badge.value = f"👤 {self.player_name}"
        if self.menu_container and self.game_container:
            self.menu_container.visible = False
            self.game_container.visible = True
        self.page.update()
        await self._start_game()

    async def _start_game(self) -> None:
        if self.game_active:
            return
        self.session_start_time = time.perf_counter()
        await self._prepare_new_session()
        self.game_active = True
        self._show_feedback("Merke dir das Wort!", "#5164d8")
        self._schedule_next_round(START_DELAY_MS / 1000)

    async def _prepare_new_session(self) -> None:
        self._cancel_all_tasks()
        self.music.cleanup()
        self.engine.reset()
        self.player_sequence.clear()
        self.tiles_enabled = False
        self.remaining_time = 0.0
        self.timer_deadline = None
        self._update_score_label(0)
        self._update_time_label()
        if self.selection_status:
            self.selection_status.value = "Auswahl: —"
            self.selection_status.color = TEXT_MUTED
        if self.word_text:
            self.word_text.value = "Bereit?"
            self.word_text.color = TEXT_PRIMARY
        if self.word_container:
            self.word_container.bgcolor = CARD_BG
        self._set_tiles_enabled(False)
        self._clear_feedback()
        self.page.update()

    def _schedule_next_round(self, delay: float) -> None:
        self._cancel_task(self.round_delay_task)
        self.round_delay_task = self._spawn(lambda: self._delayed_round_start(delay))

    async def _delayed_round_start(self, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
            if self.game_active:
                await self._advance_round()
        except asyncio.CancelledError:
            pass

    async def _advance_round(self) -> None:
        if not self.game_active:
            return
        self._clear_feedback()
        round_data = self.engine.prepare_next_round()
        word = str(round_data["word"])
        text_color = str(round_data["text_color"])
        background_color = str(round_data["background_color"])
        self.remaining_time = float(round_data["time_budget"])
        self.player_sequence = []
        self.tiles_enabled = False
        self.round_start_time = time.perf_counter()
        self._update_score_label()
        if self.selection_status:
            self.selection_status.value = "Auswahl: —"
            self.selection_status.color = TEXT_MUTED

        if self.word_text:
            self.word_text.value = word
            self.word_text.color = text_color
        if self.word_container:
            self.word_container.bgcolor = CARD_BG

        self._set_tiles_enabled(False)
        self._start_timer()
        self.music.start()
        self.page.update()

        await asyncio.sleep(0.18)
        if self.word_container:
            self.word_container.bgcolor = background_color
        self.page.update()

        self._set_tiles_enabled(True)
        if self.selection_status and not self.player_sequence:
            self.selection_status.value = "Auswahl: bereit"
            self.selection_status.color = ACCENT_BLUE
        self.page.update()

        await asyncio.sleep(1.2)
        if not self.game_active:
            return
        if self.word_text:
            self.word_text.value = "?"
            self.word_text.color = TEXT_PRIMARY
        if self.word_container:
            self.word_container.bgcolor = CARD_BG
        self._set_tiles_enabled(True)
        self.page.update()

    async def _on_color_selected(self, color_name: str) -> None:
        if not self.game_active or not self.tiles_enabled:
            return
        self.player_sequence.append(color_name)
        if self.selection_status:
            self.selection_status.value = "Auswahl: " + " · ".join(self.player_sequence)
            self.selection_status.color = ACCENT_BLUE
        self._flash_tile(color_name)
        self.page.update()

        expected = self.engine.sequence
        index = len(self.player_sequence) - 1

        if index >= len(expected):
            await self._trigger_failure()
            return

        if self.player_sequence[index].casefold() != expected[index].casefold():
            await self._trigger_failure()
            return

        if len(self.player_sequence) == len(expected):
            self._cancel_timer()
            self.engine.register_success(self.player_name)
            play_feedback_sound("success")
            self._show_feedback("Richtig!", "#2f8c68")
            self._update_score_label()
            if self.selection_status:
                self.selection_status.value = "Auswahl: ✓"
                self.selection_status.color = "#2f8c68"
            self._set_tiles_enabled(False)
            self.page.update()
            self._schedule_next_round(0.6)

    async def _trigger_failure(self) -> None:
        self._cancel_timer()
        await self._handle_failure()

    async def _handle_failure(self) -> None:
        if not self.game_active:
            return
        score, new_highscore, solution = self.engine.register_failure(self.player_name)
        play_feedback_sound("failure")
        message = f"Falsch! Runde {score} geschafft."
        if new_highscore:
            message += " Neuer Highscore!"
        self._show_feedback(message, "#c34d5e")
        solution_text = "Lösung: " + solution
        await self._handle_stop(
            label_text="Game Over",
            label_color="#c34d5e",
            cleanup_music=False,
            reset_progress=False,
            solution_text=solution_text,
        )
        self.music.stop()
        await self._show_summary(score, new_highscore, solution)

    async def _stop_game(self, manual: bool = False) -> None:
        if not self.game_active:
            self._show_feedback("Kein Spiel läuft.", "#d48b1f")
            return
        self._show_feedback("Spiel gestoppt.", "#c34d5e")
        await self._handle_stop(label_text="Gestoppt", label_color="#c34d5e")
        if manual and self.selection_status:
            self.selection_status.value = "Auswahl: —"
            self.selection_status.color = TEXT_MUTED
        self.page.update()

    async def _handle_stop(
        self,
        *,
        label_text: str = "Gestoppt",
        label_color: str = "#c34d5e",
        cleanup_music: bool = True,
        reset_progress: bool = True,
        solution_text: Optional[str] = None,
    ) -> None:
        self._cancel_all_tasks()
        if cleanup_music:
            self.music.cleanup()
        self.game_active = False
        self.tiles_enabled = False
        if reset_progress:
            self.engine.reset()
        if self.word_text:
            self.word_text.value = label_text
            self.word_text.color = label_color
        if self.word_container:
            self.word_container.bgcolor = CARD_BG
        self.remaining_time = 0.0
        self._update_time_label()
        self.player_sequence.clear()
        self._set_tiles_enabled(False)
        if reset_progress:
            self._update_score_label(0)
        if solution_text and self.word_text:
            self.word_text.value = solution_text
            self.word_text.color = TEXT_PRIMARY
            self.word_text.size = 32

    def _set_tiles_enabled(self, enabled: bool) -> None:
        self.tiles_enabled = enabled
        opacity = 1.0 if enabled else 0.45
        scale = 1.0 if enabled else 0.98
        for tile in self.color_tiles.values():
            tile.opacity = opacity
            tile.scale = scale
            if not enabled and tile.border is not None:
                tile.border = None

    def _start_timer(self) -> None:
        self._cancel_timer()
        if self.timer_enabled and self.game_active:
            self.timer_deadline = time.perf_counter() + max(0.0, self.remaining_time)
            self.timer_task = self._spawn(lambda: self._timer_loop(self.timer_deadline))

    async def _timer_loop(self, deadline: float) -> None:
        try:
            while self.game_active and self.timer_enabled:
                remaining = max(0.0, deadline - time.perf_counter())
                self.remaining_time = round(remaining, 1)
                self._update_time_label(self.remaining_time)
                self.page.update()
                if remaining <= 0:
                    break
                await asyncio.sleep(0.05)
            if self.game_active and self.timer_enabled and self.remaining_time <= 0:
                await self._handle_failure()
        except asyncio.CancelledError:
            pass

    async def _toggle_timer(self, enabled: bool) -> None:
        self.timer_enabled = enabled
        if self.timer_enabled:
            self._show_feedback("Timer aktiviert.", "#4352c5")
            self._start_timer()
        else:
            self._show_feedback("Timer deaktiviert.", "#c67b1e")
            self._cancel_timer()
            self._update_time_label(None)
        self.page.update()

    async def _reset_highscore(self) -> None:
        self.engine.reset_highscore()
        self._update_score_label()
        self._show_feedback("Highscore zurückgesetzt.", "#c67b1e")
        self.page.update()

    async def _return_to_menu(self) -> None:
        await self._handle_stop()
        if self.menu_container and self.game_container:
            self.menu_container.visible = True
            self.game_container.visible = False
        self.page.update()

    async def _show_highscore_dialog(self) -> None:
        if self.engine.highscore > 0:
            info = ft.Text(
                f"Beste Runde: {self.engine.highscore} · Spieler: {self.engine.best_player}",
                size=18,
                weight=ft.FontWeight.W_600,
            )
        else:
            info = ft.Text(
                "Noch kein Highscore erspielt.",
                size=18,
                color=TEXT_MUTED,
            )

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Highscore"),
            content=ft.Column(
                [info],
                tight=True,
                spacing=12,
            ),
            actions=[
                ft.TextButton("OK", on_click=lambda _: self._close_dialog()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()

    async def _show_summary(self, score: int, new_highscore: bool, solution: str) -> None:
        elapsed = max(0.0, time.perf_counter() - self.session_start_time)
        content = ft.Column(
            controls=[
                ft.Text(f"Punktestand: {score}", size=20, weight=ft.FontWeight.W_600),
                ft.Text(f"Zeit gesamt: {elapsed:0.1f} s", size=18),
                ft.Text(f"Lösung: {solution}", size=16),
                ft.Text(
                    f"Bester Wert: {self.engine.highscore} – Spieler: {self.engine.best_player}",
                    size=18,
                    color=ACCENT_BLUE if new_highscore else TEXT_MUTED,
                ),
            ],
            spacing=10,
            tight=True,
        )
        self.summary_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Spiel vorbei"),
            content=content,
            actions=[
                ft.TextButton("zum Menü", on_click=lambda _: self._spawn(self._summary_to_menu)),
                ft.FilledButton("Nochmal spielen", on_click=lambda _: self._spawn(self._summary_play_again)),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self.page.dialog = self.summary_dialog
        self.summary_dialog.open = True
        self.page.update()

    async def _summary_play_again(self) -> None:
        await self._close_dialog_async()
        await self._start_game()

    async def _summary_to_menu(self) -> None:
        await self._close_dialog_async()
        await self._return_to_menu()

    def _close_dialog(self) -> None:
        if self.page.dialog:
            self.page.dialog.open = False
            self.page.update()

    async def _close_dialog_async(self) -> None:
        if self.page.dialog:
            self.page.dialog.open = False
        self.page.update()

    def _flash_tile(self, color_name: str) -> None:
        self._cancel_task(self.flash_tasks.get(color_name))
        self.flash_tasks[color_name] = self._spawn(lambda: self._flash_tile_async(color_name))

    async def _flash_tile_async(self, color_name: str) -> None:
        tile = self.color_tiles.get(color_name)
        if not tile:
            return
        try:
            tile.border = ft.border.all(4, ACCENT_BLUE)
            self.page.update()
            await asyncio.sleep(0.25)
        except asyncio.CancelledError:
            pass
        finally:
            tile.border = None
            self.page.update()

    def _update_score_label(self, current: Optional[int] = None) -> None:
        if current is None:
            current = self.engine.round
        if self.round_text:
            self.round_text.value = f"Runde: {current}"
        if self.best_text:
            self.best_text.value = f"Best: {self.engine.highscore} · {self.engine.best_player}"

    def _update_time_label(self, seconds: Optional[float] = None) -> None:
        if self.timer_text is None:
            return
        if seconds is None or not self.timer_enabled:
            self.timer_text.value = "Zeit: ∞"
        else:
            display = max(0.0, seconds)
            self.timer_text.value = f"Zeit: {display:0.1f}s"

    def _show_feedback(self, message: str, color: str) -> None:
        if self.feedback_text:
            self.feedback_text.value = message
            self.feedback_text.color = color
        self.page.update()

    def _clear_feedback(self) -> None:
        if self.feedback_text:
            self.feedback_text.value = ""
            self.feedback_text.color = FEEDBACK_BASE

    def _cancel_timer(self) -> None:
        self._cancel_task(self.timer_task)
        self.timer_task = None
        self.timer_deadline = None

    def _cancel_all_tasks(self) -> None:
        self._cancel_timer()
        self._cancel_task(self.round_delay_task)
        self.round_delay_task = None
        for name, task in list(self.flash_tasks.items()):
            self._cancel_task(task)
            self.flash_tasks.pop(name, None)
        for task in list(self._tracked_tasks):
            self._cancel_task(task)
        for future in list(self._tracked_futures):
            future.cancel()
            self._tracked_futures.discard(future)

    def _cancel_task(self, task: Optional[Any]) -> None:
        if task is None:
            return
        if isinstance(task, asyncio.Task):
            if not task.done():
                task.cancel()
            try:
                task.result()
            except Exception:
                pass
            self._tracked_tasks.discard(task)
        elif isinstance(task, Future):
            task.cancel()
            self._tracked_futures.discard(task)

    def _on_page_close(self, _: ft.ControlEvent) -> None:
        self._cancel_all_tasks()
        self.music.cleanup()

    def _spawn(self, target: Any) -> Optional[asyncio.Task]:
        run_task = getattr(self.page, "run_task", None)
        if callable(run_task):
            if inspect.iscoroutinefunction(target):
                future = run_task(target)
            else:
                if inspect.iscoroutine(target):
                    coro = target
                elif callable(target):
                    coro = target()
                    if not inspect.iscoroutine(coro):
                        return None
                else:
                    return None

                async def runner() -> None:
                    await coro

                future = run_task(runner)

            if isinstance(future, Future):
                self._tracked_futures.add(future)
                future.add_done_callback(lambda f: self._tracked_futures.discard(f))
            return future
        try:
            loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            loop = None
        if inspect.iscoroutinefunction(target):
            coro = target()
        elif inspect.iscoroutine(target):
            coro = target
        elif callable(target):
            coro = target()
            if not inspect.iscoroutine(coro):
                return None
        else:
            return None

        if loop and loop.is_running():
            task = loop.create_task(coro)
            self._tracked_tasks.add(task)
            task.add_done_callback(lambda t: self._tracked_tasks.discard(t))
            return task
        else:
            asyncio.run(coro)
            return None

    @staticmethod
    def _ideal_text_color(hex_color: str) -> str:
        r, g, b = tuple(int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return "#1f1f1f" if luminance > 0.6 else "#ffffff"


async def main(page: ft.Page) -> None:
    app = ColorMemoryApp(page)
    await app.setup()


if __name__ == "__main__":
    ft.app(target=main)
