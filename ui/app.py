"""Windows 데스크톱 AI 잔여 사용량 플로팅 위젯 애플리케이션 모듈."""

from __future__ import annotations

import datetime as dt
import threading
import tkinter as tk

from providers import (
    ProviderStatus,
    fetch_all,
    launch_cli_login,
    link_gemini_oauth,
)

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

        # Windows 위젯 형태: 타이틀바 제거, 항상 위, 약간 반투명
        self.topmost = True
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", self.topmost)
        self.root.attributes("-alpha", 0.95)

        # 우측 상단 기본 배치 (창 너비 320px 기준)
        screen_w = self.root.winfo_screenwidth()
        self.root.geometry(f"320x460+{screen_w - 340}+30")

        # 드래그 이동용 좌표 상태
        self._drag_x = 0
        self._drag_y = 0
        self._is_loading = False

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
        """드래그 이동 핸들 및 제어 버튼(새로고침, 고정, 닫기)이 있는 상단 바를 생성한다."""
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
        btn_close.bind("<Button-1>", lambda _e: self.root.destroy())

        self.btn_pin = tk.Label(
            header,
            text="📌",
            bg=BG_MAIN,
            fg=FG_TEXT,
            font=("Segoe UI Emoji", 9),
            padx=4,
            cursor="hand2",
        )
        self.btn_pin.pack(side="right")
        self.btn_pin.bind("<Button-1>", lambda _e: self._toggle_topmost())

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

    def _toggle_topmost(self) -> None:
        """다른 창 위에 항상 고정할지 여부를 토글한다."""
        self.topmost = not self.topmost
        self.root.attributes("-topmost", self.topmost)
        self.btn_pin.configure(fg=FG_TEXT if self.topmost else FG_SUB)

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
                ok = link_gemini_oauth()
                self.root.after(
                    0,
                    lambda: (
                        self.status_label.configure(
                            text="Gemini/Argon 연동 완료!" if ok else "연동 취소/실패"
                        ),
                        self.refresh_async(),
                    ),
                )

            threading.Thread(target=_gemini_worker, daemon=True).start()
        else:
            launch_cli_login(provider_name)
            self.status_label.configure(
                text=f"{provider_name} 터미널 로그인 완료 후 ↻ 버튼을 눌러주세요."
            )

    def _render_statuses(self, statuses: list[ProviderStatus]) -> None:
        """조회된 4개 카드(Claude, Codex, Gemini, Argon) 상태를 UI로 다시 그린다."""
        self._is_loading = False
        for child in self.cards_frame.winfo_children():
            child.destroy()

        for st in statuses:
            self._build_card(st)

        now_str = dt.datetime.now().strftime("%H:%M:%S")
        self.status_label.configure(text=f"최근 업데이트: {now_str} (1분마다 자동 갱신)")

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

        # 쿼터 프로그레스 바 렌더링
        for m in st.metrics:
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
                text=f"{m.remaining_percent:.1f}%",
                bg=BG_CARD,
                fg=bar_color(m.remaining_percent, brand_color),
                font=("Malgun Gothic", 8, "bold"),
            ).pack(side="right")

            # 프로그레스 바 캔버스
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
