"""Windows 데스크톱 AI 잔여 사용량 플로팅 위젯 애플리케이션 모듈."""

from __future__ import annotations

import dataclasses
import datetime as dt
import threading
import tkinter as tk

from providers import (
    ProviderStatus,
    fetch_all,
    launch_cli_login,
    link_gemini_oauth,
)

from .settings import DisplaySettings
from .theme import (
    BG_BAR,
    BG_CARD,
    BG_MAIN,
    BORDER_COLOR,
    BRAND_COLORS,
    FG_SUB,
    FG_TEXT,
    REFRESH_INTERVAL_MS,
    bar_color,
)


class UsageWidgetApp:
    """Claude, Codex, Gemini, Argon 잔여 사용량을 표시하는 플로팅 위젯."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("AI Usage Widget")
        self.root.configure(bg=BG_MAIN)

        # Windows 위젯 형태: 타이틀바 제거, 항상 위, 약간 반투명.
        # 타이틀바가 없어 작업 표시줄로 다시 불러올 수 없으므로 '고정 해제'는 두지 않고,
        # 가리고 싶을 때는 트레이 아이콘 클릭으로 숨긴다.
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)

        # 우측 상단 기본 배치 (창 너비 320px 기준)
        screen_w = self.root.winfo_screenwidth()
        self.root.geometry(f"320x460+{screen_w - 340}+30")

        # 드래그 이동용 좌표 상태
        self._drag_x = 0
        self._drag_y = 0
        self._is_loading = False
        self.tray = None  # widget.py 에서 트레이 시작 후 주입 (없으면 ✕ 가 곧 종료)
        self.display = DisplaySettings()
        # 표시 설정을 바꿀 때 네트워크 재조회 없이 바로 다시 그리려고 마지막 조회 결과를 들고 있는다.
        self._last_statuses: list[ProviderStatus] = []
        self._menu_vars: list[tk.BooleanVar] = []

        # 외곽 테두리 프레임
        self.outer = tk.Frame(
            self.root,
            bg=BG_MAIN,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=12,
            pady=10,
        )
        self.outer.pack(fill="both", expand=True)

        self._build_header()

        # 프로바이더 카드들이 그려질 컨테이너
        self.cards_frame = tk.Frame(self.outer, bg=BG_MAIN)
        self.cards_frame.pack(fill="both", expand=True, pady=(8, 4))

        # 하단 상태 표시줄
        self.status_label = tk.Label(
            self.outer,
            text="데이터 불러오는 중...",
            bg=BG_MAIN,
            fg=FG_SUB,
            font=("Malgun Gothic", 8),
            anchor="w",
        )
        self.status_label.pack(fill="x")

        # 초기 조회 및 주기적 타이머 시작
        self.refresh_async()
        self._schedule_auto_refresh()

    def _build_header(self) -> None:
        """드래그 이동 핸들 및 제어 버튼(새로고침, 표시 설정, 닫기)이 있는 상단 바를 생성한다."""
        header = tk.Frame(self.outer, bg=BG_MAIN, cursor="fleur")
        header.pack(fill="x")

        title = tk.Label(
            header,
            text="⚡ AI 잔여 사용량",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Malgun Gothic", 10, "bold"),
            cursor="fleur",
        )
        title.pack(side="left")

        for widget in (header, title):
            widget.bind("<ButtonPress-1>", self._on_drag_start)
            widget.bind("<B1-Motion>", self._on_drag_motion)

        btn_close = tk.Label(
            header,
            text="✕",
            bg=BG_MAIN,
            fg=FG_SUB,
            font=("Segoe UI Symbol", 10),
            padx=4,
            cursor="hand2",
        )
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda _e: self._on_close())

        btn_settings = tk.Label(
            header,
            text="⚙",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI Symbol", 10),
            padx=4,
            cursor="hand2",
        )
        btn_settings.pack(side="right")
        btn_settings.bind("<Button-1>", self._open_display_menu)

        self.btn_refresh = tk.Label(
            header,
            text="↻",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI Symbol", 11, "bold"),
            padx=4,
            cursor="hand2",
        )
        self.btn_refresh.pack(side="right")
        self.btn_refresh.bind("<Button-1>", lambda _e: self.refresh_async())

    def _on_drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self.root.winfo_x()
        self._drag_y = event.y_root - self.root.winfo_y()

    def _on_drag_motion(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_x
        y = event.y_root - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def _on_close(self) -> None:
        """트레이가 있으면 숨기기만 한다(시작 프로그램 위젯을 실수로 꺼버리지 않도록). 종료는 트레이 메뉴에서."""
        if self.tray:
            self.root.withdraw()
        else:
            self.quit()

    def toggle_visible(self) -> None:
        """트레이 아이콘 클릭: 숨겨져 있으면 맨 앞에 나타내고, 보이면 숨긴다.

        타이틀바 없는(overrideredirect) 창은 Tk 에서 iconify(최소화)가 안 되므로 withdraw 로 숨긴다.
        """
        if self.root.state() == "withdrawn":
            self.root.deiconify()
            # 숨겨진 사이 전체 화면 앱 등이 topmost 를 가져갔을 수 있어 다시 맨 위로 올린다.
            self.root.attributes("-topmost", True)
            self.root.lift()
        else:
            self.root.withdraw()

    def quit(self) -> None:
        # 트레이 아이콘을 먼저 내려야 종료 후 알림 영역에 유령 아이콘이 남지 않는다.
        if self.tray:
            self.tray.stop()
        self.root.destroy()

    def _schedule_auto_refresh(self) -> None:
        self.root.after(REFRESH_INTERVAL_MS, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        self.refresh_async()
        self._schedule_auto_refresh()

    def refresh_async(self) -> None:
        """네트워크 요청 동안 UI가 멈추지 않도록 백그라운드 스레드에서 조회한다."""
        if self._is_loading:
            return
        self._is_loading = True
        self.status_label.configure(text="조회 중...")

        def _worker() -> None:
            try:
                statuses = fetch_all()
            except Exception as e:
                statuses = [ProviderStatus("오류", False, error=str(e))]
            self.root.after(0, lambda: self._render_statuses(statuses))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_link_click(self, provider_name: str) -> None:
        """연동 버튼 클릭 시 서비스별 인증 절차를 실행하고 완료 후 새로고침한다."""
        if provider_name in ("Gemini", "Argon"):
            self.status_label.configure(text="브라우저에서 Gemini 로그인을 완료해주세요...")

            def _gemini_worker() -> None:
                # 백그라운드 스레드의 예외는 아무 데도 표시되지 않아 '로그인 안내'에서 멈춘 것처럼 보이므로
                # 반드시 잡아서 원인을 상태 표시줄에 띄운다.
                try:
                    ok = link_gemini_oauth()
                    message = "Gemini/Argon 연동 완료!" if ok else "연동 취소/시간 초과"
                except Exception as e:
                    ok, message = False, f"연동 실패: {e}"
                # 실패 시 새로고침하면 '최근 업데이트' 문구가 원인 메시지를 곧바로 덮어버리므로 성공 시에만 갱신한다.
                self.root.after(
                    0,
                    lambda: (self.status_label.configure(text=message), ok and self.refresh_async()),
                )

            threading.Thread(target=_gemini_worker, daemon=True).start()
        else:
            launch_cli_login(provider_name)
            self.status_label.configure(
                text=f"{provider_name} 터미널 로그인 완료 후 ↻ 버튼을 눌러주세요."
            )

    def _open_display_menu(self, event: tk.Event) -> None:
        """⚙ 클릭 시 서비스별 '카드 표시'와 행(세부 모델 한도 포함) 체크 메뉴를 띄운다.

        행 목록은 서버 응답에 따라 달라지므로 매번 마지막 조회 결과로 새로 만든다.
        """
        menu = tk.Menu(self.root, tearoff=0)
        # BooleanVar 가 가비지 컬렉션되면 체크 표시가 사라지므로 다음 메뉴를 열 때까지 붙잡아 둔다.
        self._menu_vars = []
        if not self._last_statuses:
            menu.add_command(label="불러오는 중...", state="disabled")
        for st in self._last_statuses:
            sub = tk.Menu(menu, tearoff=0)
            card_var = tk.BooleanVar(value=self.display.card_visible(st.name))
            self._menu_vars.append(card_var)
            sub.add_checkbutton(
                label="카드 표시",
                variable=card_var,
                command=lambda n=st.name, v=card_var: self._apply_display(
                    lambda: self.display.set_card(n, v.get())
                ),
            )
            if st.metrics:
                sub.add_separator()
            for m in st.metrics:
                m_var = tk.BooleanVar(value=self.display.metric_visible(m))
                self._menu_vars.append(m_var)
                sub.add_checkbutton(
                    label=m.label,
                    variable=m_var,
                    command=lambda m=m, v=m_var: self._apply_display(
                        lambda: self.display.set_metric(m, v.get())
                    ),
                )
            menu.add_cascade(label=st.name, menu=sub)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _apply_display(self, change) -> None:
        """설정을 바꾸고(파일에 저장됨) 마지막 조회 결과로 즉시 다시 그린다."""
        change()
        self._render_cards()

    def _render_statuses(self, statuses: list[ProviderStatus]) -> None:
        """조회 결과를 저장하고 카드를 다시 그린 뒤 갱신 시각을 표시한다."""
        self._is_loading = False
        self._last_statuses = self._keep_previous_on_transient(statuses)
        self._render_cards()
        now_str = dt.datetime.now().strftime("%H:%M:%S")
        interval_min = REFRESH_INTERVAL_MS // 60_000
        if any(self.display.card_visible(st.name) for st in statuses):
            self.status_label.configure(text=f"최근 업데이트: {now_str} ({interval_min}분마다 자동 갱신)")
        else:
            self.status_label.configure(text="모든 카드가 숨겨져 있습니다. ⚙ 에서 켜주세요.")

    def _keep_previous_on_transient(self, statuses: list[ProviderStatus]) -> list[ProviderStatus]:
        """시간 초과 같은 일시적 실패 한 번에 카드가 빨간 오류로 바뀌지 않도록 직전 성공 값을 유지한다.

        인증 실패(401 등)는 사용자가 재연동해야 하므로 그대로 오류를 보여준다.
        """
        previous = {st.name: st for st in self._last_statuses}
        merged = []
        for st in statuses:
            prev = previous.get(st.name)
            if st.transient and prev and prev.connected:
                # 직전 값도 이미 '이전 값'이었다면 처음 실패 시각의 경고문을 그대로 둔다.
                warning = prev.error or f"⚠ 조회 지연 - {dt.datetime.now():%H:%M} 이전 값 표시 중"
                st = dataclasses.replace(prev, error=warning)
            merged.append(st)
        return merged

    def _render_cards(self) -> None:
        """표시 설정에서 켜진 카드만 그린다(숨긴 카드도 조회는 계속해 메뉴에 행 목록을 보여준다)."""
        for child in self.cards_frame.winfo_children():
            child.destroy()

        for st in self._last_statuses:
            if self.display.card_visible(st.name):
                self._build_card(st)

        # 내용 높이에 맞춰 창 크기를 자연스럽게 조정한다.
        self.root.update_idletasks()
        req_h = self.outer.winfo_reqheight() + 4
        cur_x = self.root.winfo_x()
        cur_y = self.root.winfo_y()
        self.root.geometry(f"320x{req_h}+{cur_x}+{cur_y}")

    def _build_card(self, st: ProviderStatus) -> None:
        brand_color = BRAND_COLORS.get(st.name, "#4ea8de")
        card = tk.Frame(
            self.cards_frame,
            bg=BG_CARD,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            padx=10,
            pady=8,
        )
        card.pack(fill="x", pady=4)

        # 카드 상단: 서비스 이름 + 요금제 배지 + 계정 연동/재연동 버튼
        top = tk.Frame(card, bg=BG_CARD)
        top.pack(fill="x")

        dot = tk.Label(
            top,
            text="●",
            bg=BG_CARD,
            fg=brand_color if st.connected else "#ef476f",
            font=("Segoe UI Symbol", 9),
        )
        dot.pack(side="left", padx=(0, 4))

        name_lbl = tk.Label(
            top,
            text=st.name,
            bg=BG_CARD,
            fg=FG_TEXT,
            font=("Malgun Gothic", 10, "bold"),
        )
        name_lbl.pack(side="left")

        if st.plan:
            plan_lbl = tk.Label(
                top,
                text=st.plan,
                bg=BG_BAR,
                fg=FG_SUB,
                font=("Malgun Gothic", 7, "bold"),
                padx=5,
                pady=1,
            )
            plan_lbl.pack(side="left", padx=6)

        link_text = "재연동" if st.connected else "계정 연동"
        link_btn = tk.Label(
            top,
            text=link_text,
            bg=BG_BAR,
            fg=FG_TEXT if not st.connected else FG_SUB,
            font=("Malgun Gothic", 8),
            padx=6,
            pady=1,
            cursor="hand2",
        )
        link_btn.pack(side="right")
        link_btn.bind("<Button-1>", lambda _e, name=st.name: self._on_link_click(name))

        # 미연동 또는 에러 상태 표시
        if not st.connected:
            err_lbl = tk.Label(
                card,
                text=st.error or "연동되지 않음",
                bg=BG_CARD,
                fg="#ef476f",
                font=("Malgun Gothic", 8),
                anchor="w",
            )
            err_lbl.pack(fill="x", pady=(4, 0))
            return

        # 연동은 됐지만 이번 조회가 일시적으로 실패해 직전 값을 보여주는 중임을 알린다.
        if st.error:
            tk.Label(
                card,
                text=st.error,
                bg=BG_CARD,
                fg="#f4a261",
                font=("Malgun Gothic", 7),
                anchor="w",
            ).pack(fill="x", pady=(4, 0))

        # 쿼터 프로그레스 바 렌더링 (⚙ 에서 끈 행은 건너뛴다)
        for m in st.metrics:
            if not self.display.metric_visible(m):
                continue
            row = tk.Frame(card, bg=BG_CARD)
            row.pack(fill="x", pady=(6, 0))

            lbl_row = tk.Frame(row, bg=BG_CARD)
            lbl_row.pack(fill="x")

            tk.Label(
                lbl_row,
                text=m.label,
                bg=BG_CARD,
                fg=FG_TEXT,
                font=("Malgun Gothic", 8),
            ).pack(side="left")

            tk.Label(
                lbl_row,
                text=m.status_text or f"{m.remaining_percent:.1f}%",
                bg=BG_CARD,
                fg=bar_color(m.remaining_percent, brand_color),
                font=("Malgun Gothic", 8, "bold"),
            ).pack(side="right")

            # 프로그레스 바 캔버스. 상태 행은 실제 잔여 % 가 없으므로 가짜 막대를 그리지 않는다.
            if not m.status_text:
                bar_w = 272
                canvas = tk.Canvas(
                    row,
                    width=bar_w,
                    height=7,
                    bg=BG_BAR,
                    highlightthickness=0,
                )
                canvas.pack(fill="x", pady=(2, 1))
                fill_w = int(bar_w * max(0.0, min(100.0, m.remaining_percent)) / 100.0)
                if fill_w > 0:
                    canvas.create_rectangle(
                        0,
                        0,
                        fill_w,
                        7,
                        fill=bar_color(m.remaining_percent, brand_color),
                        width=0,
                    )

            if m.reset_text:
                tk.Label(
                    row,
                    text=m.reset_text,
                    bg=BG_CARD,
                    fg=FG_SUB,
                    font=("Malgun Gothic", 7),
                    anchor="e",
                ).pack(fill="x")
