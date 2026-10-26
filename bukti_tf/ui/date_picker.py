"""Kalender kecil untuk memilih tanggal (tanpa pustaka tambahan)."""
from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from typing import Callable, Optional, Set

from bukti_tf.ui.theme import (BORDER, CARD, FONT, GREEN, MUTED, ON_PRIMARY, PRIMARY,
                               RED, SOFT, SOFT_HOVER, SUCCESS_BG, TEXT)

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
HARI_PENDEK = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


class DatePicker(tk.Toplevel):
    """
    on_select(date) dipanggil saat sebuah hari diklik.
    marked_days(year, month) -> set hari (angka) yang sudah punya data; diberi warna hijau.
    """

    def __init__(
        self,
        parent: tk.Misc,
        initial: date,
        on_select: Callable[[date], None],
        marked_days: Optional[Callable[[int, int], Set[int]]] = None,
        anchor: Optional[tk.Misc] = None,
    ) -> None:
        super().__init__(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        self.title("Pilih Tanggal · Kalender")
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())

        self._selected = initial
        self._year, self._month = initial.year, initial.month
        self._on_select = on_select
        self._marked = marked_days or (lambda y, m: set())

        self._build()
        self._render()
        self._place(anchor)
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_set()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass  # sebagian lingkungan tidak mengizinkan grab; kalender tetap berfungsi

    # ---------- susunan ----------
    def _build(self) -> None:
        nav = tk.Frame(self, bg=CARD)
        nav.pack(fill="x", padx=10, pady=(10, 4))
        for text, delta in (("«", -12), ("‹", -1)):
            self._nav_button(nav, text, delta).pack(side="left")
        self._title = tk.Label(nav, bg=CARD, fg=TEXT, font=(FONT, 10, "bold"), width=16)
        self._title.pack(side="left", expand=True, padx=5)
        for text, delta in (("›", 1), ("»", 12)):
            self._nav_button(nav, text, delta).pack(side="left")

        self._grid = tk.Frame(self, bg=CARD)
        self._grid.pack(padx=12, pady=(2, 0))
        for c, name in enumerate(HARI_PENDEK):
            tk.Label(self._grid, text=name, bg=CARD, fg=RED if c == 6 else MUTED,
                     font=(FONT, 9, "bold"), width=4).grid(row=0, column=c, pady=(0, 5))
        self._cells = [[None] * 7 for _ in range(6)]
        for r in range(6):
            for c in range(7):
                lbl = tk.Label(self._grid, text="", width=4, font=(FONT, 10), bg=CARD,
                               fg=TEXT, pady=3, bd=0, highlightthickness=1,
                               highlightbackground=CARD)
                lbl.grid(row=r + 1, column=c, padx=1, pady=1)
                self._cells[r][c] = lbl

        bottom = tk.Frame(self, bg=CARD)
        bottom.pack(fill="x", padx=10, pady=(6, 10))
        today = tk.Label(bottom, text="Hari ini", bg=SOFT, fg=PRIMARY, cursor="hand2",
                         font=(FONT, 9, "bold"), padx=10, pady=4)
        today.pack(side="left")
        today.bind("<Button-1>", lambda e: self._pick(date.today()))
        close = tk.Label(bottom, text="Tutup", bg=CARD, fg=MUTED, cursor="hand2",
                         font=(FONT, 9), padx=10, pady=4)
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.destroy())

    def _nav_button(self, parent, text: str, delta_months: int) -> tk.Label:
        lbl = tk.Label(parent, text=text, bg=SOFT, fg=PRIMARY, cursor="hand2",
                       font=(FONT, 11, "bold"), width=2)
        lbl.bind("<Button-1>", lambda e: self._shift(delta_months))
        lbl.bind("<Enter>", lambda e: lbl.config(bg=SOFT_HOVER))
        lbl.bind("<Leave>", lambda e: lbl.config(bg=SOFT))
        return lbl

    def _place(self, anchor: Optional[tk.Misc]) -> None:
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        if anchor is not None:
            x, y = anchor.winfo_rootx(), anchor.winfo_rooty() + anchor.winfo_height() + 4
        else:
            x, y = self.master.winfo_rootx() + 40, self.master.winfo_rooty() + 80
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, min(x, sw - w - 4))
        y = max(0, min(y, sh - h - 48))  # sisakan ruang untuk taskbar
        self.geometry(f"+{x}+{y}")

    # ---------- perilaku ----------
    def _shift(self, months: int) -> None:
        index = self._year * 12 + (self._month - 1) + months
        self._year, self._month = divmod(index, 12)
        self._month += 1
        self._render()

    def _pick(self, d: date) -> None:
        self.destroy()
        self._on_select(d)

    def _render(self) -> None:
        self._title.config(text=f"{BULAN[self._month - 1]} {self._year}")
        marked = self._marked(self._year, self._month)
        today = date.today()
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(self._year, self._month)
        weeks += [[0] * 7] * (6 - len(weeks))

        for r in range(6):
            for c in range(7):
                lbl, day = self._cells[r][c], weeks[r][c]
                lbl.unbind("<Button-1>")
                lbl.unbind("<Enter>")
                lbl.unbind("<Leave>")
                if day == 0:
                    lbl.config(text="", bg=CARD, highlightbackground=CARD, cursor="")
                    continue
                d = date(self._year, self._month, day)
                bg, fg = CARD, RED if c == 6 else TEXT
                if day in marked:
                    bg, fg = SUCCESS_BG, GREEN
                if d == self._selected:
                    bg, fg = PRIMARY, ON_PRIMARY
                lbl.config(text=str(day), bg=bg, fg=fg, cursor="hand2",
                           highlightbackground=PRIMARY if d == today else CARD)
                lbl.bind("<Button-1>", lambda e, d=d: self._pick(d))
                if d != self._selected:
                    lbl.bind("<Enter>", lambda e, l=lbl: l.config(bg=SOFT_HOVER))
                    lbl.bind("<Leave>", lambda e, l=lbl, b=bg: l.config(bg=b))
