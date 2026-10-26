"""Panel yang bisa digulir secara vertikal; scrollbar hanya muncul saat isinya lebih tinggi."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bukti_tf.ui.theme import CARD


class ScrollFrame(tk.Frame):
    """Pasang widget ke `.body`, bukan ke frame ini."""

    def __init__(self, master, bg: str = CARD, **kw) -> None:
        super().__init__(master, bg=bg, **kw)
        self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self._bar = ttk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._bar.set)
        self._canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(self._canvas, bg=bg)
        self._win = self._canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._on_resize)
        self._canvas.bind("<Configure>", self._on_resize)

        # Roda mouse hanya aktif saat kursor di dalam panel ini
        self.bind("<Enter>", self._bind_wheel)
        self.bind("<Leave>", self._unbind_wheel)

    # ---------- ukuran & scrollbar ----------
    def _need_scroll(self) -> bool:
        return self.body.winfo_reqheight() > self._canvas.winfo_height()

    def _on_resize(self, _event=None) -> None:
        self._canvas.itemconfigure(self._win, width=self._canvas.winfo_width())
        need = self._need_scroll()
        self._canvas.configure(scrollregion=(0, 0, 0, self.body.winfo_reqheight()))
        if need and not self._bar.winfo_ismapped():
            self._bar.pack(side="right", fill="y")
        elif not need and self._bar.winfo_ismapped():
            self._bar.pack_forget()
            self._canvas.yview_moveto(0)

    # ---------- roda mouse ----------
    def _bind_wheel(self, _event=None) -> None:
        self._canvas.bind_all("<MouseWheel>", self._on_wheel)
        self._canvas.bind_all("<Button-4>", self._on_wheel)   # Linux
        self._canvas.bind_all("<Button-5>", self._on_wheel)

    def _unbind_wheel(self, event=None) -> None:
        # <Leave> juga terkirim saat kursor pindah ke widget anak; cek posisi sebenarnya
        if event is not None:
            x, y = self.winfo_pointerxy()
            if self.winfo_containing(x, y) is not None and str(
                    self.winfo_containing(x, y)).startswith(str(self)):
                return
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self._canvas.unbind_all(seq)

    def _on_wheel(self, event) -> None:
        if not self._need_scroll():
            return
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        self._canvas.yview_scroll(step * 2, "units")

    # ---------- bantu ----------
    def see(self, widget: tk.Misc) -> None:
        """Gulir agar `widget` terlihat penuh (dipakai setelah menambah baris baru)."""
        self.update_idletasks()
        total = self.body.winfo_reqheight()
        view = self._canvas.winfo_height()
        if total <= view:
            return
        top = widget.winfo_rooty() - self.body.winfo_rooty()
        bottom = top + widget.winfo_height()
        first = self._canvas.canvasy(0)
        if top < first:
            self._canvas.yview_moveto(top / total)
        elif bottom > first + view:
            self._canvas.yview_moveto((bottom - view + 8) / total)
