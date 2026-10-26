"""Dialog pilih gabungan hari yang dibayar oleh satu bukti transfer."""
from __future__ import annotations

import tkinter as tk
from datetime import date
from typing import Callable, Optional, Sequence

from bukti_tf.domain.settlement import Candidate
from bukti_tf.ui.theme import BG, BORDER, CARD, FONT, MUTED, PRIMARY, SOFT, SOFT_HOVER, TEXT, HoverButton

HARI_PENDEK = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]


def _rupiah(n: int) -> str:
    return "Rp " + f"{n:,}".replace(",", ".")


def describe(c: Candidate) -> str:
    def one(d: date) -> str:
        return f"{HARI_PENDEK[d.weekday()]} {d:%d/%m}"
    days = " + ".join(one(d) for d in c.days)
    extra = []
    if len(c.days) > 1 and not c.contiguous:
        extra.append("tidak berurutan")
    if c.after_transfer:
        extra.append("setelah tanggal transfer")
    return f"{days}  ({_rupiah(c.total)})" + (f"  · {', '.join(extra)}" if extra else "")


class SettlementDialog:
    """Modal. `ask()` mengembalikan Candidate yang dipilih, atau None jika dibatalkan."""

    def __init__(self, parent: tk.Misc, nominal: int, candidates: Sequence[Candidate]) -> None:
        self._result: Optional[Candidate] = None
        self._cands = list(candidates)
        top = self._top = tk.Toplevel(parent)
        top.title("Cocokkan bukti dengan beberapa hari")
        top.configure(bg=CARD)
        top.transient(parent.winfo_toplevel())
        top.resizable(False, False)

        tk.Label(top, text=f"Transfer {_rupiah(nominal)} cocok dengan:", bg=CARD, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(anchor="w", padx=20, pady=(18, 2))
        tk.Label(top, text="Pilih hari-hari yang dibayar oleh bukti ini.", bg=CARD, fg=MUTED,
                 font=(FONT, 9)).pack(anchor="w", padx=20, pady=(0, 10))

        self._choice = tk.IntVar(value=0)
        for i, c in enumerate(self._cands):
            tk.Radiobutton(top, text=describe(c), variable=self._choice, value=i, bg=CARD,
                           fg=TEXT, selectcolor=SOFT, activebackground=CARD, anchor="w",
                           font=(FONT, 10), wraplength=460, justify="left").pack(
                fill="x", padx=20, pady=2)

        bar = tk.Frame(top, bg=CARD)
        bar.pack(fill="x", padx=20, pady=(14, 16))
        HoverButton(bar, text="Terapkan", padx=14, command=self._ok).pack(side="left")
        HoverButton(bar, text="Batal", bg=SOFT, hover=SOFT_HOVER, fg=PRIMARY, padx=14,
                    command=top.destroy).pack(side="left", padx=(8, 0))
        top.bind("<Escape>", lambda e: top.destroy())
        top.bind("<Return>", lambda e: self._ok())

    def _ok(self) -> None:
        self._result = self._cands[self._choice.get()]
        self._top.destroy()

    def ask(self) -> Optional[Candidate]:
        self._top.update_idletasks()
        top = self._top
        p = top.master.winfo_toplevel()
        x = p.winfo_rootx() + (p.winfo_width() - top.winfo_width()) // 2
        y = p.winfo_rooty() + (p.winfo_height() - top.winfo_height()) // 3
        top.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        top.grab_set()
        top.focus_set()
        top.wait_window()
        return self._result
