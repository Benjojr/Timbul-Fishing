
"""Tema visual bersama untuk antarmuka BuktiTF.

Palet warna dan API lama dipertahankan.
Penyempurnaan berfokus pada tipografi, padding, dan komponen UI.

Palet: "laut" | "biru" | "gelap"
"""

import os
import tkinter as tk
from tkinter import ttk


DEFAULT_THEME = "gelap"

# Ukuran font terpusat agar konsisten di seluruh aplikasi.
FONT = "Segoe UI"
FONT_SIZE = 10
FONT_SIZE_SMALL = 10
FONT_SIZE_BUTTON = 11
FONT_SIZE_HEADING = 11


PALETTES = {
    "laut": dict(
        BG="#EDF2F2", CARD="#FFFFFF", SURFACE="#F5F8F8",
        PRIMARY="#0F766E", PRIMARY_HOVER="#0B5F59", ON_PRIMARY="#FFFFFF",
        SOFT="#E2F1EF", SOFT_HOVER="#CFE8E4",
        TEXT="#10282B", MUTED="#5E7578", BORDER="#DAE5E5",
        RED="#B42318", GREEN="#17803D", AMBER="#A15C07",
        SUCCESS_BG="#DDF3E4", DANGER_BG="#FCE4E1", WARN_BG="#FCEFC7",
        NEUTRAL_BG="#E8EEEE", NEUTRAL_FG="#5E7578",
        INPUT_BG="#FBFDFD", SELECT_BG="#D5ECE8", ROW_ALT="#F6FAFA",
        DISABLED_FG="#A9B9BA",
        HEADER_BG="#0B4F4A", HEADER_FG="#FFFFFF",
        HEADER_MUTED="#9FD1CB",
        SCROLL_THUMB="#C2D3D3", SCROLL_HOVER="#A5BBBB",
    ),
    "biru": dict(
        BG="#F1F4FA", CARD="#FFFFFF", SURFACE="#F6F8FD",
        PRIMARY="#2457C5", PRIMARY_HOVER="#1946A5", ON_PRIMARY="#FFFFFF",
        SOFT="#EAF0FF", SOFT_HOVER="#DCE6FF",
        TEXT="#17243B", MUTED="#68758A", BORDER="#E1E8F2",
        RED="#C0394A", GREEN="#16845B", AMBER="#A96708",
        SUCCESS_BG="#DCF5E8", DANGER_BG="#FDE4E7", WARN_BG="#FCEFC7",
        NEUTRAL_BG="#EDF0F6", NEUTRAL_FG="#68758A",
        INPUT_BG="#FBFCFE", SELECT_BG="#DCE8FF", ROW_ALT="#F7F9FD",
        DISABLED_FG="#AAB4C4",
        HEADER_BG="#1B3F94", HEADER_FG="#FFFFFF",
        HEADER_MUTED="#B7C9F2",
        SCROLL_THUMB="#C5CFE2", SCROLL_HOVER="#A7B5D0",
    ),
    "gelap": dict(
        BG="#0E161D", CARD="#16212B", SURFACE="#1B2833",
        PRIMARY="#2DD4BF", PRIMARY_HOVER="#5EEAD4", ON_PRIMARY="#05211E",
        SOFT="#20373A", SOFT_HOVER="#294A4D",
        TEXT="#E5EDF2", MUTED="#8DA2B0", BORDER="#2A3A47",
        RED="#F87171", GREEN="#4ADE80", AMBER="#FBBF24",
        SUCCESS_BG="#15382B", DANGER_BG="#3E1E22", WARN_BG="#3B2F12",
        NEUTRAL_BG="#243240", NEUTRAL_FG="#9DB0BE",
        INPUT_BG="#101922", SELECT_BG="#244650", ROW_ALT="#1A2631",
        DISABLED_FG="#718493",
        HEADER_BG="#0A1117", HEADER_FG="#E5EDF2",
        HEADER_MUTED="#7FA6A2",
        SCROLL_THUMB="#34495A", SCROLL_HOVER="#4A6479",
    ),
}


_name = os.environ.get("BUKTITF_THEME", DEFAULT_THEME).strip().lower()
THEME_NAME = _name if _name in PALETTES else DEFAULT_THEME
_P = PALETTES[THEME_NAME]

BG, CARD, SURFACE = _P["BG"], _P["CARD"], _P["SURFACE"]
PRIMARY, PRIMARY_HOVER, ON_PRIMARY = (
    _P["PRIMARY"], _P["PRIMARY_HOVER"], _P["ON_PRIMARY"]
)
SOFT, SOFT_HOVER = _P["SOFT"], _P["SOFT_HOVER"]
TEXT, MUTED, BORDER = _P["TEXT"], _P["MUTED"], _P["BORDER"]
RED, GREEN, AMBER = _P["RED"], _P["GREEN"], _P["AMBER"]
SUCCESS_BG, DANGER_BG, WARN_BG = (
    _P["SUCCESS_BG"], _P["DANGER_BG"], _P["WARN_BG"]
)
NEUTRAL_BG, NEUTRAL_FG = _P["NEUTRAL_BG"], _P["NEUTRAL_FG"]
INPUT_BG, SELECT_BG, ROW_ALT = (
    _P["INPUT_BG"], _P["SELECT_BG"], _P["ROW_ALT"]
)
DISABLED_FG = _P["DISABLED_FG"]
HEADER_BG, HEADER_FG, HEADER_MUTED = (
    _P["HEADER_BG"], _P["HEADER_FG"], _P["HEADER_MUTED"]
)
SCROLL_THUMB, SCROLL_HOVER = _P["SCROLL_THUMB"], _P["SCROLL_HOVER"]


class HoverButton(tk.Button):
    """Tombol standar dengan tipografi dan padding yang lebih nyaman."""

    def __init__(
        self, master, bg=PRIMARY, hover=PRIMARY_HOVER,
        fg=ON_PRIMARY, **kw
    ):
        kw.setdefault("padx", 18)
        kw.setdefault("pady", 10)
        kw.setdefault("font", (FONT, FONT_SIZE_BUTTON, "bold"))

        super().__init__(
            master,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            disabledforeground=DISABLED_FG,
            relief="flat",
            bd=0,
            cursor="hand2",
            highlightthickness=0,
            takefocus=True,
            **kw
        )

        self._bg = bg
        self._hover = hover
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _event=None):
        if str(self["state"]) == "normal":
            self.config(bg=self._hover)

    def _on_leave(self, _event=None):
        self.config(bg=self._bg)


class RoundedButton(tk.Canvas):
    """Tombol bersudut membulat, tanpa library tambahan.

    Gunakan sebagai alternatif HoverButton.
    API dasar: text, command, bg, hover, fg, radius, font.
    """

    def __init__(
        self,
        master,
        text="",
        command=None,
        bg=PRIMARY,
        hover=PRIMARY_HOVER,
        fg=ON_PRIMARY,
        radius=10,
        font=None,
        padx=18,
        pady=10,
        **kw
    ):
        self._text = text
        self._command = command
        self._button_bg = bg
        self._hover_bg = hover
        self._fg = fg
        self._radius = max(0, radius)
        self._font = font or (FONT, FONT_SIZE_BUTTON, "bold")
        self._padx = padx
        self._pady = pady
        self._enabled = True

        # Canvas memakai background induk, tanpa garis tepi.
        super().__init__(
            master,
            bg=kw.pop("background", master.cget("bg")),
            bd=0,
            highlightthickness=0,
            relief="flat",
            cursor="hand2",
            takefocus=True,
            **kw
        )

        self._text_id = self.create_text(
            0, 0,
            text=self._text,
            fill=self._fg,
            font=self._font,
            anchor="center",
        )

        bbox = self.bbox(self._text_id)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        self._width = text_width + 2 * padx
        self._height = text_height + 2 * pady

        self.configure(width=self._width, height=self._height)
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<space>", self._on_key)
        self.bind("<Return>", self._on_key)

        self._draw()

    def _rounded_polygon(self, x1, y1, x2, y2, r, fill):
        """Gambar poligon halus dengan sudut melengkung."""
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)

        points = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]

        return self.create_polygon(
            points,
            smooth=True,
            splinesteps=24,
            fill=fill,
            outline=fill,
            width=1,
            tags="button_shape",
        )

    def _draw(self, _event=None):
        self.delete("button_shape")
        width = self.winfo_width()
        height = self.winfo_height()

        if width <= 1 or height <= 1:
            return

        self._rounded_polygon(
            1, 1, width - 1, height - 1,
            self._radius, self._button_bg
        )
        self.tag_raise(self._text_id)
        self.coords(self._text_id, width / 2, height / 2)

    def _on_enter(self, _event=None):
        if self._enabled:
            self._button_bg = self._hover_bg
            self._draw()

    def _on_leave(self, _event=None):
        self._button_bg = self._original_bg
        self._draw()

    def _on_click(self, _event=None):
        if self._enabled and callable(self._command):
            self._command()

    def _on_key(self, _event=None):
        if self._enabled and callable(self._command):
            self._command()
        return "break"

    @property
    def _original_bg(self):
        return self._normal_bg

    @_original_bg.setter
    def _original_bg(self, value):
        self._normal_bg = value

    def configure(self, cnf=None, **kw):
        # Memungkinkan perubahan warna dan status setelah dibuat.
        if hasattr(self, "_button_bg"):
            if "bg" in kw:
                self._normal_bg = kw.pop("bg")
                self._button_bg = self._normal_bg
            if "hover" in kw:
                self._hover_bg = kw.pop("hover")
            if "fg" in kw:
                self._fg = kw.pop("fg")
                self.itemconfigure(self._text_id, fill=self._fg)
            if "text" in kw:
                self._text = kw.pop("text")
                self.itemconfigure(self._text_id, text=self._text)
            if "state" in kw:
                self._enabled = kw.pop("state") != "disabled"
                self.configure(cursor="hand2" if self._enabled else "arrow")

        return super().configure(cnf, **kw)

    config = configure


def soft_button(parent, text, command=None, **kw) -> HoverButton:
    """Tombol sekunder dengan warna lembut."""
    return HoverButton(
        parent,
        text=text,
        bg=SOFT,
        hover=SOFT_HOVER,
        fg=PRIMARY,
        command=command,
        **kw
    )


class Card(tk.Frame):
    """Panel dengan garis tepi tipis.

    Frame tetap dipertahankan agar widget anak tidak rusak.
    """

    def __init__(self, master, **kw):
        super().__init__(
            master,
            bg=CARD,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
            **kw
        )


def apply_ttk_styles(root: tk.Misc) -> None:
    """Terapkan tipografi dan gaya komponen ttk."""

    style = ttk.Style(root)

    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # Tabel: ukuran teks lebih nyaman dan baris lebih lapang.
    style.configure(
        "Treeview",
        font=(FONT, FONT_SIZE),
        rowheight=36,
        background=CARD,
        fieldbackground=CARD,
        foreground=TEXT,
        borderwidth=0,
        relief="flat",
        padding=(5, 4),
    )

    style.configure(
        "Treeview.Heading",
        font=(FONT, FONT_SIZE_HEADING, "bold"),
        background=SURFACE,
        foreground=TEXT,
        padding=(12, 11),
        relief="flat",
        borderwidth=0,
    )

    style.map(
        "Treeview",
        background=[("selected", SELECT_BG)],
        foreground=[("selected", TEXT)],
    )

    style.map(
        "Treeview.Heading",
        background=[("active", SOFT)],
        foreground=[("active", TEXT)],
    )

    style.layout(
        "Treeview",
        [("Treeview.treearea", {"sticky": "nswe"})],
    )

    # Scrollbar tanpa tombol panah, dengan area klik yang lebih nyaman.
    style.layout(
        "Vertical.TScrollbar",
        [
            (
                "Vertical.Scrollbar.trough",
                {
                    "sticky": "ns",
                    "children": [
                        (
                            "Vertical.Scrollbar.thumb",
                            {
                                "expand": "1",
                                "sticky": "nswe",
                            },
                        )
                    ],
                },
            )
        ],
    )

    style.configure(
        "Vertical.TScrollbar",
        troughcolor=CARD,
        background=SCROLL_THUMB,
        bordercolor=CARD,
        lightcolor=SCROLL_THUMB,
        darkcolor=SCROLL_THUMB,
        gripcount=0,
        width=10,
        relief="flat",
    )

    style.map(
        "Vertical.TScrollbar",
        background=[("active", SCROLL_HOVER)],
        lightcolor=[("active", SCROLL_HOVER)],
        darkcolor=[("active", SCROLL_HOVER)],
    )

    # Progress bar sedikit lebih tebal agar mudah dilihat.
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=SURFACE,
        background=PRIMARY,
        bordercolor=SURFACE,
        lightcolor=PRIMARY,
        darkcolor=PRIMARY,
        thickness=6,
    )
