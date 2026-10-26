"""Lapisan tampilan. Hanya bergantung pada core dan domain, bukan pada OCR/parser/SQLite."""
from __future__ import annotations

import os
import re
import tempfile
import threading
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image, ImageGrab, ImageTk

from bukti_tf.core.errors import ReceiptConflictError, ReceiptError
from bukti_tf.core.extractor import ReceiptExtractor
from bukti_tf.core.formatting import format_excel_row, format_receipt
from bukti_tf.core.interfaces import DailyRecordRepository, MonthReportExporter, ReceiptExporter
from bukti_tf.core.report_calculator import DailyReportCalculator
from bukti_tf.core.settlement_service import SettlementService
from bukti_tf.core.transfer_checker import TransferChecker
from bukti_tf.domain import check_result as cr
from bukti_tf.domain.check_result import CheckResult
from bukti_tf.domain.daily_record import DailyRecord
from bukti_tf.domain.daily_report import DailyInput, DailyReport, ExpenseItem, SessionEntry
from bukti_tf.domain.receipt import TransferReceipt
from bukti_tf.domain.settlement import Suggestion
from bukti_tf.ui.date_picker import BULAN, DatePicker
from bukti_tf.ui.scroll_frame import ScrollFrame
from bukti_tf.ui.settlement_dialog import SettlementDialog, describe
from bukti_tf.ui.theme import (AMBER, BG, BORDER, CARD, DANGER_BG, FONT, GREEN, HEADER_BG,
                               HEADER_FG, HEADER_MUTED, INPUT_BG, MUTED, NEUTRAL_BG,
                               NEUTRAL_FG, PRIMARY, RED, ROW_ALT, SOFT, SOFT_HOVER,
                               SUCCESS_BG, SURFACE, TEXT, WARN_BG, Card, HoverButton,
                               apply_ttk_styles, soft_button)

BADGES = {
    "berhasil": ("BERHASIL", SUCCESS_BG, GREEN),
    "gagal": ("GAGAL", DANGER_BG, RED),
}
BADGE_NONE = ("TIDAK TERBACA", NEUTRAL_BG, NEUTRAL_FG)
BADGE_EMPTY = ("-", NEUTRAL_BG, NEUTRAL_FG)

_OK = (SUCCESS_BG, GREEN)
_BAD = (DANGER_BG, RED)
_WARN = (WARN_BG, AMBER)
_IDLE = (NEUTRAL_BG, NEUTRAL_FG)
CHECK_STYLES = {
    cr.CHECKED: ("CHECKED", *_OK),
    cr.SELISIH: ("SELISIH", *_BAD),
    cr.GAGAL: ("TRANSFER GAGAL", *_BAD),
    cr.TIDAK_TERBACA: ("NOMINAL TIDAK TERBACA", *_WARN),
    cr.PERLU_CEK: ("CEK MANUAL", *_WARN),
    cr.GABUNGAN: ("COCOK GABUNGAN", *_WARN),
    cr.SUDAH_DIPAKAI: ("BUKTI SUDAH DIPAKAI", *_BAD),
    cr.BELUM_ADA: ("BELUM ADA BUKTI", *_IDLE),
    cr.TIDAK_PERLU: ("TIDAK ADA TRANSFER", *_IDLE),
}
CHECK_INVALID = ("INPUT TIDAK VALID", *_WARN)
# Teks singkat + tag warna untuk tabel riwayat
CHECK_SHORT = {
    cr.CHECKED: ("Checked", "ok"), cr.SELISIH: ("Selisih", "bad"), cr.GAGAL: ("Gagal", "bad"),
    cr.TIDAK_TERBACA: ("Cek", "warn"), cr.PERLU_CEK: ("Cek", "warn"),
    cr.BELUM_ADA: ("Belum", "warn"), cr.TIDAK_PERLU: ("-", ""),
    cr.GABUNGAN: ("Cek", "warn"), cr.SUDAH_DIPAKAI: ("Dobel", "bad"),
}

PLACEHOLDER = "Belum ada gambar\n\nPilih file atau tempel (Ctrl+V)\ndari clipboard"

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
HARI_PENDEK = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
DATE_FORMAT = "%d/%m/%Y"


def _titik(angka: int) -> str:
    sign = "-" if angka < 0 else ""
    return sign + f"{abs(angka):,}".replace(",", ".")


def _rupiah(angka: Optional[int]) -> str:
    return "-" if angka is None else "Rp " + _titik(angka)


def _parse_int(teks: str) -> int:
    """'1.500.000' / 'Rp 1,500,000' / '' -> int. Selain angka -> ValueError."""
    bersih = re.sub(r"(?i)rp|[\s.,]", "", teks)
    if bersih == "":
        return 0
    if not bersih.isdigit():
        raise ValueError(teks)
    return int(bersih)


def _parse_date(teks: str) -> Optional[date]:
    try:
        return datetime.strptime(teks.strip(), DATE_FORMAT).date()
    except ValueError:
        return None


def _money_text(n: int) -> str:
    return "" if n == 0 else _titik(n)


class TkApp:
    # Ukuran jendela relatif terhadap layar (default dan minimum)
    DEFAULT_RATIO = (0.72, 0.86)
    MIN_RATIO = (0.58, 0.70)
    MIN_FLOOR = (700, 700)   # batas mutlak agar isi tidak terpotong
    MAX_RATIO = 0.95         # jangan melebihi layar
    DATE_DEBOUNCE_MS = 500

    def __init__(
        self,
        extractor: ReceiptExtractor,
        exporter: ReceiptExporter,
        calculator: DailyReportCalculator,
        checker: TransferChecker,
        repository: DailyRecordRepository,
        service: SettlementService,
        pdf_exporter: MonthReportExporter,
    ) -> None:
        self._extractor = extractor
        self._exporter = exporter
        self._calculator = calculator
        self._checker = checker
        self._repo = repository
        self._service = service
        self._pdf = pdf_exporter

        self._last: Optional[TransferReceipt] = None
        self._cover: Tuple[date, ...] = ()        # hari yang berbagi bukti `_last` (sudah tersimpan)
        self._suggestion: Optional[Suggestion] = None
        self._suggest_job = None
        self._input: Optional[DailyInput] = None
        self._report: Optional[DailyReport] = None
        self._check: Optional[CheckResult] = None
        self._loaded_date: Optional[date] = None  # tanggal rekap yang sedang dimuat/disimpan
        self._dirty = False                       # ada perubahan yang belum disimpan
        self._loading = False                     # sedang mengisi form dari data tersimpan
        self._busy = False                        # OCR sedang berjalan
        self._formatting = False                  # penjaga format ribuan
        self._date_job = None
        self._photo = None
        self._orig: Optional[Image.Image] = None
        self._resize_job = None
        self._check_widgets = []
        self._exp_rows: List[Dict] = []           # baris rincian pengeluaran
        self._hist_year, self._hist_month = date.today().year, date.today().month
        self._build()
        self._recalc()
        self._dirty = False
        self._process_date_change()  # muat data tanggal hari ini jika sudah ada

    # ================= Susunan tampilan =================
    def _build(self) -> None:
        root = self._root = tk.Tk()
        root.title("BuktiTF · Rekap & Verifikasi Transfer")
        root.configure(bg=BG)
        self._apply_window_size()
        apply_ttk_styles(root)

        # Header tipis supaya ruang kerja lebih luas
        header = tk.Frame(root, bg=HEADER_BG)
        header.pack(fill="x")
        bar = tk.Frame(header, bg=HEADER_BG)
        bar.pack(fill="x", padx=24, pady=12)
        tk.Label(bar, text="BuktiTF", bg=HEADER_BG, fg=HEADER_FG,
                 font=(FONT, 14, "bold")).pack(side="left")
        tk.Frame(bar, bg=HEADER_MUTED, width=1, height=16).pack(side="left", padx=14)
        tk.Label(bar, text="Rekap harian & verifikasi transfer", bg=HEADER_BG,
                 fg=HEADER_MUTED, font=(FONT, 10)).pack(side="left")

        # Status bar dipasang lebih dulu di bawah agar tidak pernah tertutup
        self._status_var = tk.StringVar(value="Siap")
        status_bar = tk.Frame(root, bg=BG)
        status_bar.pack(side="bottom", fill="x", padx=24, pady=(0, 10))
        tk.Label(status_bar, textvariable=self._status_var, bg=BG, fg=MUTED,
                 font=(FONT, 9), anchor="w").pack(fill="x")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=20, pady=(16, 8))
        body.columnconfigure(0, weight=2, uniform="kolom")
        body.columnconfigure(1, weight=3, uniform="kolom")
        body.rowconfigure(0, weight=1)

        self._build_left(body)
        self._build_right(body)
        root.bind_all("<Control-v>", self._on_paste)
        root.bind_all("<Control-V>", self._on_paste)
    def _build_left(self, body) -> None:
        card = Card(body)
        card.grid(row=0, column=0, sticky="nsew", padx=(0, 16))

        # Urutan pack penting: tombol (bawah) dipasang SEBELUM preview,
        # sehingga tombol selalu terlihat dan preview yang mengalah.
        btns = tk.Frame(card, bg=CARD)
        btns.pack(side="bottom", fill="x", padx=18, pady=(12, 18))
        btns.columnconfigure(0, weight=1, uniform="tombol")
        btns.columnconfigure(1, weight=1, uniform="tombol")
        self._pick_btn = HoverButton(btns, text="Pilih File", command=self._on_pick)
        self._pick_btn.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._paste_btn = soft_button(btns, "Tempel  (Ctrl+V)", self._on_paste)
        self._paste_btn.grid(row=0, column=1, sticky="ew", padx=(5, 0))

        tk.Label(card, text="Bukti Transfer", bg=CARD, fg=TEXT,
                 font=(FONT, 12, "bold")).pack(side="top", anchor="w", padx=18, pady=(16, 10))

        self._preview_box = tk.Frame(card, bg=SURFACE, highlightthickness=1,
                                     highlightbackground=BORDER)
        self._preview_box.pack(side="top", fill="both", expand=True, padx=18)
        self._preview = tk.Label(self._preview_box, text=PLACEHOLDER, bg=SURFACE, fg=MUTED,
                                 font=(FONT, 10), justify="center")
        self._preview.place(relx=0.5, rely=0.5, anchor="center")
        self._preview_box.bind("<Configure>", self._on_preview_resize)
    def _build_right(self, body) -> None:
        card = Card(body)
        card.grid(row=0, column=1, sticky="nsew")

        # Baris tombol di bawah (dipasang dulu agar tidak tertutup); isinya ganti per tab
        bottom = tk.Frame(card, bg=CARD)
        bottom.pack(side="bottom", fill="x")
        tk.Frame(bottom, bg=BORDER, height=1).pack(fill="x")
        actions = tk.Frame(bottom, bg=CARD)
        actions.pack(fill="x", padx=20, pady=14)
        self._build_action_bars(actions)

        # Tab bergaya garis bawah
        tabs = tk.Frame(card, bg=CARD)
        tabs.pack(side="top", fill="x", padx=20, pady=(14, 0))
        self._tab_labels, self._tab_marks = {}, {}
        for key, text in (("rekap", "Rekap Harian"), ("bukti", "Hasil Bukti"),
                          ("riwayat", "Riwayat")):
            cell = tk.Frame(tabs, bg=CARD, cursor="hand2")
            cell.pack(side="left", padx=(0, 22))
            lbl = tk.Label(cell, text=text, bg=CARD, fg=MUTED, cursor="hand2",
                           font=(FONT, 10, "bold"), pady=6)
            lbl.pack()
            mark = tk.Frame(cell, bg=CARD, height=3)
            mark.pack(fill="x")
            for w in (cell, lbl, mark):
                w.bind("<Button-1>", lambda e, k=key: self._show_page(k))
            self._tab_labels[key], self._tab_marks[key] = lbl, mark
        tk.Frame(card, bg=BORDER, height=1).pack(side="top", fill="x", padx=20)

        self._progress = ttk.Progressbar(card, mode="indeterminate")
        self._pages_box = tk.Frame(card, bg=CARD)
        self._pages_box.pack(side="top", fill="both", expand=True, padx=20, pady=(12, 14))

        self._pages = {
            "rekap": self._build_page_rekap(self._pages_box),
            "bukti": self._build_page_bukti(self._pages_box),
            "riwayat": self._build_page_riwayat(self._pages_box),
        }
        self._show_page("rekap")
    def _build_action_bars(self, container) -> None:
        def soft(parent, text, command, **kw):
            return soft_button(parent, text, command, padx=12, **kw)

        self._bars = {}
        # Rekap
        bar = tk.Frame(container, bg=CARD)
        self._save_rec_btn = HoverButton(bar, text="Simpan", padx=18,
                                         command=self._on_save_record)
        self._save_rec_btn.pack(side="left")
        self._excel_btn = soft(bar, "Salin ke Excel", self._on_copy_excel)
        self._excel_btn.pack(side="left", padx=(8, 0))
        self._combine_btn = soft(bar, "Gabungan…", self._on_combine, state=tk.DISABLED)
        self._combine_btn.pack(side="left", padx=(8, 0))
        self._new_btn = soft(bar, "Baru", self._on_new)
        self._new_btn.pack(side="right")
        self._bars["rekap"] = bar
        # Bukti
        bar = tk.Frame(container, bg=CARD)
        self._copy_btn = soft(bar, "Salin Bukti", self._on_copy, state=tk.DISABLED)
        self._copy_btn.pack(side="left")
        self._save_btn = soft(bar, "Simpan .txt", self._on_save, state=tk.DISABLED)
        self._save_btn.pack(side="left", padx=(8, 0))
        self._bars["bukti"] = bar
        # Riwayat
        bar = tk.Frame(container, bg=CARD)
        self._month_btn = HoverButton(bar, text="Salin Bulan ke Excel", padx=16,
                                      command=self._on_copy_month)
        self._month_btn.pack(side="left")
        self._pdf_btn = soft(bar, "Ekspor Bulan ke PDF", self._on_export_month_pdf)
        self._pdf_btn.pack(side="left", padx=(8, 0))
        self._del_btn = soft(bar, "Hapus", self._on_delete_record)
        self._del_btn.pack(side="left", padx=(8, 0))
        self._bars["riwayat"] = bar
    # ---------- Halaman: rekap harian ----------
    def _entry(self, parent, var, width=12, justify="right") -> tk.Entry:
        return tk.Entry(parent, textvariable=var, width=width, justify=justify,
                        font=(FONT, 11), fg=TEXT, bg=INPUT_BG, relief="flat", bd=0,
                        highlightthickness=1, highlightbackground=BORDER,
                        highlightcolor=PRIMARY, insertbackground=TEXT)

    def _section(self, parent, text: str) -> tk.Frame:
        """Judul bagian kecil + garis tipis. Widget di kanan: pack(side="right") sesudahnya."""
        head = tk.Frame(parent, bg=CARD)
        tk.Label(head, text=text, bg=CARD, fg=MUTED, font=(FONT, 8, "bold")).pack(side="left")
        tk.Frame(head, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(10, 0))
        return head
    def _build_page_rekap(self, parent) -> tk.Frame:
        container = tk.Frame(parent, bg=CARD)

        # Ringkasan & status pencocokan tetap di bawah (tidak ikut tergulir)
        summary = tk.Frame(container, bg=SURFACE, highlightthickness=1,
                           highlightbackground=BORDER)
        summary.pack(side="bottom", fill="x", pady=(10, 0))
        self._build_summary(summary)

        # Formulir bisa digulir bila isinya (mis. banyak pengeluaran) melebihi tinggi jendela
        self._rekap_scroll = ScrollFrame(container)
        self._rekap_scroll.pack(side="top", fill="both", expand=True)
        form = tk.Frame(self._rekap_scroll.body, bg=CARD)
        form.pack(fill="x", padx=(0, 8))
        for c in (1, 2, 3):
            form.columnconfigure(c, weight=1, uniform="isi")
        self._vars, self._entries = {}, {}

        def add_entry(key, row, col, width=10, columnspan=1, initial="", money=False,
                      parent=form, pady=3, padx=(0, 8)):
            var = tk.StringVar(value=initial)
            self._vars[key] = var
            if money:
                # Tk mengabaikan perubahan kursor yang dibuat di dalam trace, jadi
                # pemformatan dijalankan sesudah event pengetikan selesai (after_idle).
                var.trace_add("write", lambda *_a, k=key: self._schedule_format(k))
            var.trace_add("write", self._recalc)
            e = self._entry(parent, var, width)
            e.grid(row=row, column=col, columnspan=columnspan, sticky="ew", padx=padx,
                   pady=pady, ipady=4)
            self._entries[key] = e

        # --- Tanggal: ketik atau pilih lewat kalender ---
        head = self._section(form, "TANGGAL")
        head.grid(row=0, column=0, columnspan=4, sticky="ew")
        self._state_lbl = tk.Label(head, font=(FONT, 9, "bold"), padx=10, pady=2)
        self._state_lbl.pack(side="right", padx=(10, 0))

        date_row = tk.Frame(form, bg=CARD)
        date_row.grid(row=1, column=0, columnspan=4, sticky="w", pady=(8, 0))
        add_entry("tanggal", 0, 0, width=14, initial=date.today().strftime(DATE_FORMAT),
                  parent=date_row)
        self._vars["tanggal"].trace_add("write", self._schedule_date_change)
        self._date_btn = soft_button(date_row, "Pilih tanggal", self._open_picker,
                                     padx=12, pady=5)
        self._date_btn.grid(row=0, column=1, sticky="w")

        # --- Sesi ---
        head = self._section(form, "SESI MEMANCING")
        head.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        for col, text in enumerate(("Sesi", "Peserta", "Harga ticket", "Subtotal")):
            tk.Label(form, text=text, bg=CARD, fg=MUTED, font=(FONT, 9),
                     anchor="w" if col == 0 else "e").grid(
                row=3, column=col, sticky="ew", pady=(8, 2), padx=(0, 8))
        self._subtotals = []
        for i in range(3):
            r = 4 + i
            tk.Label(form, text=f"Sesi {i + 1}", bg=CARD, fg=TEXT,
                     font=(FONT, 10, "bold")).grid(row=r, column=0, sticky="w", padx=(0, 14))
            add_entry(f"peserta{i}", r, 1)
            add_entry(f"harga{i}", r, 2, money=True)
            sub = tk.Label(form, text="-", bg=CARD, fg=TEXT, font=(FONT, 10), anchor="e")
            sub.grid(row=r, column=3, sticky="ew", padx=(0, 8))
            self._subtotals.append(sub)

        # --- Hadiah ---
        head = self._section(form, "HADIAH")
        head.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        add_entry("hadiah", 8, 0, columnspan=4, money=True, pady=(8, 3), padx=0)

        # --- Pengeluaran: daftar rincian (keperluan + nominal) dengan tombol Tambah ---
        self._build_expense_block(form, row=9)

        # --- Catatan harian (masuk kolom Keterangan di Excel) ---
        head = self._section(form, "CATATAN")
        head.grid(row=10, column=0, columnspan=4, sticky="ew", pady=(20, 0))
        var = tk.StringVar()
        self._vars["catatan"] = var
        var.trace_add("write", self._recalc)
        e = self._entry(form, var, 40, justify="left")
        e.grid(row=11, column=0, columnspan=4, sticky="ew", pady=(8, 3), ipady=4)
        self._entries["catatan"] = e
        return container

    def _build_summary(self, summary) -> None:
        """Total dan status pencocokan; selalu terlihat di bawah formulir."""
        stats = tk.Frame(summary, bg=SURFACE)
        stats.pack(fill="x", padx=16, pady=(12, 8))
        self._totals = {}
        for i, (key, label, size) in enumerate((
            ("pemasukan", "Pemasukan", 11), ("pengeluaran", "Pengeluaran", 11),
            ("sisa", "Sisa (ditransfer)", 15),
        )):
            stats.columnconfigure(i, weight=1)
            box = tk.Frame(stats, bg=SURFACE)
            box.grid(row=0, column=i, sticky="w")
            tk.Label(box, text=label, bg=SURFACE, fg=MUTED, font=(FONT, 9)).pack(anchor="w")
            v = tk.Label(box, text="-", bg=SURFACE, fg=TEXT, font=(FONT, size, "bold"))
            v.pack(anchor="w")
            self._totals[key] = v
        tk.Frame(summary, bg=BORDER, height=1).pack(fill="x", padx=16)
        self._make_check_box(summary, SURFACE).pack(fill="x", padx=16, pady=(8, 12))
    # ---------- Halaman: hasil bukti ----------
    def _build_page_bukti(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=CARD)
        info = tk.Frame(page, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        info.pack(fill="x", pady=(2, 0))
        info.columnconfigure(1, weight=1)
        self._values = {}
        rows = [("status", "Status"), ("waktu", "Waktu"), ("ke", "Rekening tujuan"),
                ("nama", "Nama penerima"), ("nominal", "Nominal")]
        for i, (key, label) in enumerate(rows):
            tk.Label(info, text=label, bg=SURFACE, fg=MUTED, font=(FONT, 9), anchor="w",
                     width=16).grid(row=i * 2, column=0, sticky="w", padx=(16, 8), pady=9)
            if key == "status":
                lbl = tk.Label(info, font=(FONT, 9, "bold"), padx=10, pady=2)
            else:
                size = 15 if key == "nominal" else 11
                lbl = tk.Label(info, bg=SURFACE, fg=TEXT, anchor="w", font=(FONT, size, "bold"))
            lbl.grid(row=i * 2, column=1, sticky="w", pady=9)
            self._values[key] = lbl
            if i < len(rows) - 1:
                tk.Frame(info, bg=BORDER, height=1).grid(
                    row=i * 2 + 1, column=0, columnspan=2, sticky="ew", padx=16)
        self._make_check_box(page, CARD).pack(fill="x", pady=(16, 0))
        self._show_empty()
        return page
    def _make_check_box(self, parent, bg) -> tk.Frame:
        """Status pencocokan: lencana berwarna + penjelasan di sebelahnya."""
        box = tk.Frame(parent, bg=bg)
        badge = tk.Label(box, font=(FONT, 9, "bold"), padx=10, pady=3)
        badge.pack(side="left", anchor="n")
        detail = tk.Label(box, bg=bg, fg=MUTED, font=(FONT, 9), justify="left", anchor="nw",
                          wraplength=300)
        detail.pack(side="left", fill="x", expand=True, padx=(12, 0), anchor="n")
        box.bind("<Configure>", lambda e, d=detail, b=badge: d.config(
            wraplength=max(140, e.width - b.winfo_reqwidth() - 24)))
        self._check_widgets.append((badge, detail))
        return box
    # ---------- Halaman: riwayat ----------
    def _nav_button(self, parent, text: str, delta: int) -> tk.Label:
        b = tk.Label(parent, text=text, bg=SOFT, fg=PRIMARY, cursor="hand2",
                     font=(FONT, 13, "bold"), width=3)
        b.bind("<Button-1>", lambda e, d=delta: self._shift_history(d))
        b.bind("<Enter>", lambda e, w=b: w.config(bg=SOFT_HOVER))
        b.bind("<Leave>", lambda e, w=b: w.config(bg=SOFT))
        return b

    def _build_page_riwayat(self, parent) -> tk.Frame:
        page = tk.Frame(parent, bg=CARD)

        nav = tk.Frame(page, bg=CARD)
        nav.pack(side="top", fill="x", pady=(2, 0))
        self._nav_button(nav, "‹", -1).pack(side="left")
        self._nav_button(nav, "›", 1).pack(side="right")
        self._hist_title = tk.Label(nav, bg=CARD, fg=TEXT, font=(FONT, 12, "bold"))
        self._hist_title.pack(side="top", pady=2)

        strip = tk.Frame(page, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        strip.pack(side="bottom", fill="x", pady=(10, 0))
        self._hist_total = tk.Label(strip, bg=SURFACE, fg=TEXT, font=(FONT, 9), justify="left",
                                    anchor="w", wraplength=330)
        self._hist_total.pack(fill="x", padx=12, pady=9)
        strip.bind("<Configure>",
                   lambda e: self._hist_total.config(wraplength=max(180, e.width - 28)))

        box = tk.Frame(page, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        box.pack(side="top", fill="both", expand=True, pady=(10, 0))
        cols = (("tgl", "Tgl", 62, "w"), ("masuk", "Pemasukan", 88, "e"),
                ("keluar", "Pengeluaran", 88, "e"), ("sisa", "Sisa", 82, "e"),
                ("ket", "Ket", 76, "w"))
        self._tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                  selectmode="browse")
        for key, text, width, anchor in cols:
            self._tree.heading(key, text=text, anchor=anchor)
            self._tree.column(key, width=width, minwidth=44, anchor=anchor, stretch=True)
        self._tree.tag_configure("alt", background=ROW_ALT)
        self._tree.tag_configure("ok", foreground=GREEN)
        self._tree.tag_configure("bad", foreground=RED)
        self._tree.tag_configure("warn", foreground=AMBER)
        scroll = ttk.Scrollbar(box, orient="vertical", command=self._tree.yview)
        self._tree.pack(side="left", fill="both", expand=True)

        def on_scroll(first, last):
            scroll.set(first, last)
            if float(first) <= 0.0 and float(last) >= 1.0:
                scroll.pack_forget()
            elif not scroll.winfo_ismapped():
                scroll.pack(side="right", fill="y", before=self._tree)

        self._tree.configure(yscrollcommand=on_scroll)
        self._tree.bind("<Double-1>", lambda e: self._open_history_row())
        return page
    # ================= Helper tampilan =================
    def _show_page(self, key: str) -> None:
        for k, page in self._pages.items():
            page.pack_forget()
            self._bars[k].pack_forget()
            active = k == key
            self._tab_labels[k].config(fg=PRIMARY if active else MUTED)
            self._tab_marks[k].config(bg=PRIMARY if active else CARD)
        self._pages[key].pack(fill="both", expand=True)
        self._bars[key].pack(fill="x")
        if key == "riwayat":
            d = _parse_date(self._vars["tanggal"].get())
            if d is not None:
                self._hist_year, self._hist_month = d.year, d.month
            self._refresh_history()
    def _apply_window_size(self) -> None:
        """Ukuran default & minimum dihitung dari resolusi layar, lalu jendela dipusatkan."""
        root = self._root
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        max_w, max_h = int(sw * self.MAX_RATIO), int(sh * self.MAX_RATIO)

        min_w = min(max(int(sw * self.MIN_RATIO[0]), self.MIN_FLOOR[0]), max_w)
        min_h = min(max(int(sh * self.MIN_RATIO[1]), self.MIN_FLOOR[1]), max_h)
        w = min(max(int(sw * self.DEFAULT_RATIO[0]), min_w), max_w)
        h = min(max(int(sh * self.DEFAULT_RATIO[1]), min_h), max_h)

        x, y = (sw - w) // 2, max((sh - h) // 3, 0)
        root.geometry(f"{w}x{h}+{x}+{y}")
        root.minsize(min_w, min_h)

    def _set_badge(self, badge) -> None:
        text, bg, fg = badge
        self._values["status"].config(text=text, bg=bg, fg=fg)

    def _show_empty(self) -> None:
        self._set_badge(BADGE_EMPTY)
        for key in ("waktu", "ke", "nama", "nominal"):
            self._values[key].config(text="-")

    def _render_receipt(self) -> None:
        r = self._last
        if r is None:
            self._show_empty()
        else:
            self._set_badge(BADGES.get(r.status, BADGE_NONE))
            self._values["waktu"].config(text=r.waktu)
            self._values["ke"].config(text=r.ke)
            self._values["nama"].config(text=r.nama)
            self._values["nominal"].config(text=_rupiah(r.nominal))
        self._update_buttons()

    def _update_buttons(self) -> None:
        ok = self._report is not None
        free = not self._busy
        self._excel_btn.config(state=tk.NORMAL if ok else tk.DISABLED)
        self._save_rec_btn.config(state=tk.NORMAL if ok and free else tk.DISABLED)
        self._new_btn.config(state=tk.NORMAL if free else tk.DISABLED)
        has_receipt = self._last is not None and free
        self._copy_btn.config(state=tk.NORMAL if has_receipt else tk.DISABLED)
        self._save_btn.config(state=tk.NORMAL if has_receipt else tk.DISABLED)
        self._pick_btn.config(state=tk.NORMAL if free else tk.DISABLED)
        self._paste_btn.config(state=tk.NORMAL if free else tk.DISABLED)
        sug = self._suggestion
        can_combine = bool(sug and sug.candidates) and free
        self._combine_btn.config(state=tk.NORMAL if can_combine else tk.DISABLED)

    def _clear_preview(self) -> None:
        self._orig = None
        self._photo = None
        self._preview.config(image="", text=PLACEHOLDER)
    def _show_preview(self, path: str) -> None:
        try:
            self._orig = Image.open(path)
            self._orig.load()
        except Exception:
            self._orig = None
            self._photo = None
            self._preview.config(image="", text="Preview tidak tersedia")
            return
        self._render_preview()

    def _on_preview_resize(self, _event=None) -> None:
        # debounce: hindari render ulang berkali-kali saat jendela ditarik
        if self._resize_job is not None:
            self._root.after_cancel(self._resize_job)
        self._resize_job = self._root.after(60, self._render_preview)

    def _render_preview(self) -> None:
        self._resize_job = None
        if self._orig is None:
            return
        box_w = self._preview_box.winfo_width() - 8
        box_h = self._preview_box.winfo_height() - 8
        if box_w < 20 or box_h < 20:
            return
        img = self._orig.copy()
        img.thumbnail((box_w, box_h), Image.LANCZOS)
        self._photo = ImageTk.PhotoImage(img)
        self._preview.config(image=self._photo, text="")

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if busy:
            self._progress.pack(side="top", fill="x", padx=20, pady=(0, 4),
                                before=self._pages_box)
            self._progress.start(12)
        else:
            self._progress.stop()
            self._progress.pack_forget()
        self._update_buttons()

    # ================= Isian & format angka =================
    def _schedule_format(self, key: str) -> None:
        self._schedule_format_entry(self._vars[key], self._entries[key])

    def _schedule_format_entry(self, var, entry) -> None:
        if not self._formatting:
            self._root.after_idle(self._format_entry, var, entry)

    def _format_money(self, key: str) -> None:
        self._format_entry(self._vars[key], self._entries[key])

    def _format_entry(self, var, entry) -> None:
        """Titik tiap tiga digit dari belakang; kursor tetap di tempatnya."""
        try:
            if not entry.winfo_exists():
                return
        except tk.TclError:
            return
        text = var.get()
        digits = re.sub(r"\D", "", text)
        formatted = f"{int(digits):,}".replace(",", ".") if digits else ""
        if formatted == text:
            return

        cursor = entry.index(tk.INSERT)
        digits_left = len(re.sub(r"\D", "", text[:cursor]))
        new_cursor, seen = 0, 0
        for i, ch in enumerate(formatted):
            if seen == digits_left:
                break
            if ch.isdigit():
                seen += 1
            new_cursor = i + 1

        self._formatting = True
        try:
            var.set(formatted)
            entry.icursor(new_cursor)
        finally:
            self._formatting = False

    def _mark(self, key: str, ok: bool) -> None:
        self._mark_entry(self._entries[key], ok)

    @staticmethod
    def _mark_entry(e, ok: bool) -> None:
        e.config(highlightbackground=BORDER if ok else RED,
                 highlightcolor=PRIMARY if ok else RED)

    # ================= Rincian pengeluaran =================
    def _build_expense_block(self, page, row: int) -> None:
        box = tk.Frame(page, bg=CARD)
        box.grid(row=row, column=0, columnspan=4, sticky="ew", pady=(20, 4))
        box.columnconfigure(0, weight=1)

        head = self._section(box, "PENGELUARAN")
        head.grid(row=0, column=0, sticky="ew")
        soft_button(head, "+ Tambah", lambda: self._add_expense_row(focus=True),
                    padx=12, pady=3).pack(side="right", padx=(10, 0))
        self._exp_total_lbl = tk.Label(head, text="", bg=CARD, fg=MUTED, font=(FONT, 9))
        self._exp_total_lbl.pack(side="right", padx=(10, 0))

        self._exp_inner = tk.Frame(box, bg=CARD)
        self._exp_inner.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self._exp_inner.columnconfigure(0, weight=1)
        self._set_expense_rows(())
    def _set_expense_rows(self, items) -> None:
        """Ganti seluruh baris pengeluaran; selalu tersisa minimal satu baris kosong."""
        for r in self._exp_rows:
            r["frame"].destroy()
        self._exp_rows = []
        for item in items:
            self._add_expense_row(item.keperluan, item.nominal, recalc=False)
        if not self._exp_rows:
            self._add_expense_row(recalc=False)

    def _add_expense_row(self, keperluan: str = "", nominal: int = 0,
                         focus: bool = False, recalc: bool = True) -> None:
        frame = tk.Frame(self._exp_inner, bg=CARD)
        frame.grid(row=len(self._exp_rows), column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)

        var_k = tk.StringVar(value=keperluan)
        var_n = tk.StringVar(value=_money_text(nominal))
        ent_k = self._entry(frame, var_k, width=14, justify="left")
        ent_n = self._entry(frame, var_n, width=14)
        ent_k.grid(row=0, column=0, sticky="ew", padx=(0, 8), pady=3, ipady=4)
        ent_n.grid(row=0, column=1, padx=(0, 4), pady=3, ipady=4)
        rm = tk.Label(frame, text="✕", bg=CARD, fg=MUTED, cursor="hand2",
                      font=(FONT, 10, "bold"), width=3)
        rm.grid(row=0, column=2)

        row = {"frame": frame, "k": var_k, "n": var_n, "ek": ent_k, "en": ent_n}
        self._exp_rows.append(row)

        var_k.trace_add("write", self._recalc)
        var_n.trace_add("write", lambda *_a, v=var_n, e=ent_n: self._schedule_format_entry(v, e))
        var_n.trace_add("write", self._recalc)
        rm.bind("<Button-1>", lambda _e, r=row: self._remove_expense_row(r))
        rm.bind("<Enter>", lambda _e, w=rm: w.config(fg=RED))
        rm.bind("<Leave>", lambda _e, w=rm: w.config(fg=MUTED))
        # Enter di nominal: baris berikutnya (atau baris baru bila ini yang terakhir)
        ent_n.bind("<Return>", lambda _e, r=row: self._next_expense_row(r))
        ent_k.bind("<Return>", lambda _e, w=ent_n: w.focus_set())

        if recalc:
            self._recalc()
        if focus:
            self._root.update_idletasks()
            ent_k.focus_set()
            self._rekap_scroll.see(frame)
    def _next_expense_row(self, row) -> None:
        i = self._exp_rows.index(row)
        if i + 1 < len(self._exp_rows):
            self._exp_rows[i + 1]["ek"].focus_set()
        elif row["n"].get().strip() or row["k"].get().strip():
            self._add_expense_row(focus=True)

    def _remove_expense_row(self, row) -> None:
        if row not in self._exp_rows:
            return
        row["frame"].destroy()
        self._exp_rows.remove(row)
        for i, r in enumerate(self._exp_rows):  # rapatkan urutan baris grid
            r["frame"].grid(row=i)
        if not self._exp_rows:
            self._add_expense_row(recalc=False)
        self._recalc()

    def _read_form(self) -> DailyInput:
        """Baca form. Semua isian yang salah ditandai merah, lalu ValueError dilempar."""
        invalid = False

        def num(key: str) -> int:
            nonlocal invalid
            try:
                value = _parse_int(self._vars[key].get())
                self._mark(key, True)
                return value
            except ValueError:
                self._mark(key, False)
                invalid = True
                return 0

        tanggal = _parse_date(self._vars["tanggal"].get())
        self._mark("tanggal", tanggal is not None)
        if tanggal is None:
            invalid = True
            tanggal = date.today()

        sesi = tuple(
            SessionEntry(peserta=num(f"peserta{i}"), harga=num(f"harga{i}")) for i in range(3)
        )
        items = []
        for r in self._exp_rows:
            keperluan = r["k"].get().strip()
            teks = r["n"].get().strip()
            if not keperluan and not teks:
                self._mark_entry(r["en"], True)
                continue  # baris kosong diabaikan
            try:
                nominal = _parse_int(teks)
                ok = nominal > 0 or not keperluan  # keperluan tanpa nominal = belum lengkap
            except ValueError:
                nominal, ok = 0, False
            self._mark_entry(r["en"], ok)
            if not ok:
                invalid = True
            if nominal == 0 and not keperluan:
                continue  # "0" saja tanpa keperluan: abaikan
            items.append(ExpenseItem(keperluan=keperluan, nominal=nominal))
        data = DailyInput(tanggal=tanggal, sesi=sesi,  # type: ignore[arg-type]
                          hadiah=num("hadiah"), rincian=tuple(items),
                          catatan=self._vars["catatan"].get().strip())
        if invalid:
            raise ValueError("input tidak valid")
        return data

    def _recalc(self, *_args) -> None:
        if not self._loading:
            self._dirty = True
        try:
            self._input = self._read_form()
            self._report = self._calculator.calculate(self._input)
        except ValueError:  # termasuk InvalidReportInputError
            self._input, self._report = None, None
        self._render_report()
        if not self._loading:
            self._schedule_suggest()
        self._render_check()
        self._update_state_label()
        self._update_buttons()

    def _schedule_suggest(self) -> None:
        """Hitung ulang usulan gabungan setelah form berhenti diubah (hindari kerja tiap ketukan)."""
        if self._suggest_job is not None:
            self._root.after_cancel(self._suggest_job)
            self._suggest_job = None
        if self._last is None or self._cover:
            return
        self._suggest_job = self._root.after(400, self._refresh_suggestion)

    def _refresh_suggestion(self) -> None:
        self._suggest_job = None
        if self._last is None or self._cover:
            return
        try:
            self._suggestion = self._service.suggest(self._last, self._report)
        except Exception as exc:
            self._suggestion = None
            self._status_var.set(f"Gagal mencari gabungan: {exc}")
        self._render_check()
        self._update_buttons()

    def _render_report(self) -> None:
        r = self._report
        self._exp_total_lbl.config(
            text="" if r is None or not r.rincian else f"Subtotal {_rupiah(r.pengeluaran)}")
        if r is None:
            for lbl in self._subtotals:
                lbl.config(text="-")
            for lbl in self._totals.values():
                lbl.config(text="-", fg=TEXT)
            return
        for lbl, s in zip(self._subtotals, r.sesi):
            lbl.config(text=_rupiah(s.peserta * s.harga))
        self._totals["pemasukan"].config(text=_rupiah(r.total_pemasukan))
        self._totals["pengeluaran"].config(text=_rupiah(r.total_pengeluaran))
        self._totals["sisa"].config(text=_rupiah(r.sisa), fg=RED if r.sisa < 0 else TEXT)

    def _check_detail(self, c: CheckResult) -> str:
        text = self._check_detail_core(c)
        return f"{text}\n{c.catatan}" if c.catatan else text

    def _check_detail_core(self, c: CheckResult) -> str:
        if c.status == cr.GABUNGAN:
            n = len(self._suggestion.candidates) if self._suggestion else 1
            extra = f" (+{n - 1} kemungkinan lain)" if n > 1 else ""
            return (f"Transfer {_rupiah(c.nominal)} cocok dengan gabungan "
                    f"{self._hari_text(c.days)}{extra}. Klik 'Gabungan…' untuk menerapkan.")
        if c.status == cr.SUDAH_DIPAKAI:
            return f"Bukti ini sudah tercatat untuk {self._hari_text(c.days)}."
        if c.status == cr.CHECKED and len(c.days) > 1:
            return (f"Transfer {_rupiah(c.nominal)} sama dengan total sisa "
                    f"{self._hari_text(c.days)}.")
        if c.status == cr.SELISIH and len(c.days) > 1:
            arah = "lebih" if (c.selisih or 0) > 0 else "kurang"
            return (f"Transfer {_rupiah(c.nominal)}, total sisa {self._hari_text(c.days)} "
                    f"{_rupiah(c.sisa)}: {arah} {_rupiah(abs(c.selisih or 0))}.")
        if c.status == cr.CHECKED:
            return f"Transfer {_rupiah(c.nominal)} sama dengan sisa."
        if c.status == cr.SELISIH:
            arah = "lebih" if (c.selisih or 0) > 0 else "kurang"
            return (f"Transfer {_rupiah(c.nominal)}, sisa {_rupiah(c.sisa)}: "
                    f"{arah} {_rupiah(abs(c.selisih or 0))}.")
        if c.status == cr.GAGAL:
            return "Bukti menyatakan transfer gagal."
        if c.status == cr.TIDAK_TERBACA:
            return "Nominal pada bukti tidak terbaca. Periksa gambarnya."
        if c.status == cr.PERLU_CEK:
            return "Nominal sama, tetapi status transfer tidak terbaca. Cek bukti secara manual."
        if c.status == cr.TIDAK_PERLU:
            return "Sisa 0, tidak ada yang perlu ditransfer."
        return f"Pilih bukti transfer untuk sisa {_rupiah(c.sisa)}."

    def _hari_text(self, days) -> str:
        return " + ".join(f"{d:%d/%m}" for d in days)

    def _render_check(self) -> None:
        if self._report is None:
            self._check = None
            style, detail = CHECK_INVALID, "Periksa isian yang ditandai merah."
            if not self._loading:
                self._status_var.set("Input rekap tidak valid")
        else:
            result = self._service.check_live(self._report, self._last, self._cover)
            sug = self._suggestion
            if (self._last is not None and not self._cover and sug is not None
                    and result.status not in (cr.CHECKED, cr.PERLU_CEK, cr.GAGAL, cr.TIDAK_TERBACA)):
                if sug.duplicate_days:
                    result = CheckResult(status=cr.SUDAH_DIPAKAI, sisa=result.sisa,
                                         nominal=self._last.nominal, days=sug.duplicate_days)
                elif sug.candidates:
                    best = sug.candidates[0]
                    result = CheckResult(status=cr.GABUNGAN, sisa=result.sisa,
                                         nominal=self._last.nominal, days=best.days)
            self._check = result
            style, detail = CHECK_STYLES[result.status], self._check_detail(result)
            if self._last is not None and not self._loading:
                self._status_var.set(f"Pencocokan: {style[0]}")
        text, bg, fg = style
        for badge, lbl in self._check_widgets:
            badge.config(text=text, bg=bg, fg=fg)
            lbl.config(text=detail)

    def _update_state_label(self) -> None:
        d = _parse_date(self._vars["tanggal"].get())
        if d is None:
            self._state_lbl.config(text="Format: hh/bb/tttt", bg=DANGER_BG, fg=RED)
            return
        hari = HARI[d.weekday()]
        if self._loaded_date == d and not self._dirty:
            self._state_lbl.config(text=f"{hari} · Tersimpan", bg=SUCCESS_BG, fg=GREEN)
        elif self._loaded_date == d:
            self._state_lbl.config(text=f"{hari} · Belum disimpan (ada perubahan)",
                                   bg=WARN_BG, fg=AMBER)
        else:
            self._state_lbl.config(text=f"{hari} · Belum disimpan", bg=NEUTRAL_BG, fg=NEUTRAL_FG)
    # ================= Tanggal =================
    def _saved_days(self, year: int, month: int) -> Set[int]:
        try:
            return {r.data.tanggal.day for r in self._repo.list_month(year, month)}
        except Exception:
            return set()

    def _open_picker(self) -> None:
        d = _parse_date(self._vars["tanggal"].get()) or date.today()
        DatePicker(self._root, d, on_select=self._on_picked,
                   marked_days=self._saved_days, anchor=self._date_btn)

    def _on_picked(self, d: date) -> None:
        self._vars["tanggal"].set(d.strftime(DATE_FORMAT))
        self._process_date_change()

    def _schedule_date_change(self, *_a) -> None:
        if self._loading:
            return
        if self._date_job is not None:
            self._root.after_cancel(self._date_job)
        self._date_job = self._root.after(self.DATE_DEBOUNCE_MS, self._process_date_change)

    def _process_date_change(self) -> None:
        """Jika tanggal punya data tersimpan, muat ke form (tanya dulu bila ada perubahan)."""
        if self._date_job is not None:
            self._root.after_cancel(self._date_job)
            self._date_job = None
        d = _parse_date(self._vars["tanggal"].get())
        if d is None or d == self._loaded_date:
            return
        try:
            record = self._repo.get(d)
        except Exception as exc:
            self._status_var.set(f"Gagal membaca data tersimpan: {exc}")
            return
        if record is None:
            return  # tanggal baru: biarkan isian apa adanya
        if self._dirty and not messagebox.askyesno(
            "Muat data tersimpan?",
            f"Tanggal {d.strftime(DATE_FORMAT)} sudah punya data tersimpan.\n\n"
            "Memuatnya akan mengganti isian yang sekarang (belum disimpan). Lanjutkan?",
        ):
            self._update_state_label()
            return
        self._load_record(record)

    def _load_record(self, rec: DailyRecord) -> None:
        d = rec.data
        self._loading = True
        try:
            self._vars["tanggal"].set(d.tanggal.strftime(DATE_FORMAT))
            for i, s in enumerate(d.sesi):
                self._vars[f"peserta{i}"].set("" if s.peserta == 0 else str(s.peserta))
                self._vars[f"harga{i}"].set(_money_text(s.harga))
            self._vars["hadiah"].set(_money_text(d.hadiah))
            self._vars["catatan"].set(d.catatan)
            if d.rincian:
                self._set_expense_rows(d.rincian)
            elif d.pengeluaran:  # data lama: hanya satu angka total
                self._set_expense_rows((ExpenseItem("Belum dirinci", d.pengeluaran),))
            else:
                self._set_expense_rows(())
            self._last = rec.receipt
            self._cover = rec.cover
            self._suggestion = None
            self._recalc()
        finally:
            self._loading = False
        self._clear_preview()
        if rec.receipt is not None:
            self._preview.config(text="Gambar bukti tidak disimpan")
        self._loaded_date = d.tanggal
        self._dirty = False
        self._render_receipt()
        self._render_check()
        self._update_state_label()
        self._status_var.set(f"Data {d.tanggal.strftime(DATE_FORMAT)} dimuat")

    # ================= Simpan / baru =================
    def _on_save_record(self) -> None:
        if self._input is None or self._report is None:
            self._status_var.set("Perbaiki isian yang ditandai merah dulu")
            return
        d = self._input.tanggal
        try:
            exists = self._repo.get(d) is not None
            if exists and self._loaded_date != d and not messagebox.askyesno(
                "Timpa data?",
                f"Tanggal {d.strftime(DATE_FORMAT)} sudah punya data tersimpan.\nTimpa dengan isian sekarang?",
            ):
                return
            self._repo.save(DailyRecord(data=self._input))
        except Exception as exc:
            messagebox.showerror("Gagal menyimpan", str(exc))
            return
        self._link_current_receipt(d)
        self._loaded_date = d
        self._dirty = False
        self._update_state_label()
        self._status_var.set(f"Rekap {d.strftime(DATE_FORMAT)} tersimpan")
        if self._current_tab() == "riwayat":
            self._refresh_history()

    def _link_current_receipt(self, d: date) -> None:
        """Hubungkan bukti yang sedang tampil ke hari ini (transfer harian biasa)."""
        if self._last is None or d in self._cover:
            return  # tidak ada bukti baru, atau sudah terhubung (termasuk gabungan)
        try:
            self._service.apply(self._last, [d], replace=True)
        except ReceiptConflictError as exc:
            hari = self._hari_text(exc.days) if exc.days else ""
            messagebox.showwarning(
                "Bukti tidak dihubungkan",
                f"{exc}\n{hari}\n\nRekap tetap tersimpan, tetapi tanpa bukti ini.")
            self._last = None
            self._cover = ()
            self._suggestion = None
            self._render_receipt()
            self._render_check()
            return
        except Exception as exc:
            messagebox.showerror("Gagal menghubungkan bukti", str(exc))
            return
        self._cover = (d,)
        self._suggestion = None
        self._render_check()
        self._update_buttons()

    def _on_combine(self) -> None:
        """Pilih & terapkan gabungan hari yang dibayar bukti yang sedang tampil."""
        sug = self._suggestion
        if self._last is None or sug is None or not sug.candidates or self._last.nominal is None:
            return
        choice = SettlementDialog(self._root, self._last.nominal, sug.candidates).ask()
        if choice is None:
            return
        self._apply_candidate(choice.days)

    def _apply_candidate(self, days) -> None:
        receipt = self._last
        if receipt is None:
            return
        cur = _parse_date(self._vars["tanggal"].get())
        try:
            if cur in days:
                if self._input is None:
                    self._status_var.set("Perbaiki isian yang ditandai merah dulu")
                    return
                self._repo.save(DailyRecord(data=self._input))  # hari form harus tersimpan dulu
            self._service.apply(receipt, days)
        except ReceiptConflictError as exc:
            messagebox.showwarning("Tidak bisa diterapkan", str(exc))
            return
        except Exception as exc:
            messagebox.showerror("Gagal menerapkan", str(exc))
            return
        teks = self._hari_text(days)
        if cur in days:
            self._cover = tuple(sorted(days))
            self._loaded_date = cur
            self._dirty = False
            self._suggestion = None
            self._render_check()
            self._update_state_label()
            self._update_buttons()
        else:
            # Bukti dipakai hari lain; form ini tidak ikut, jadi lepas bukti dari form.
            self._last, self._cover, self._suggestion = None, (), None
            self._clear_preview()
            self._render_receipt()
            self._render_check()
        self._status_var.set(f"Bukti diterapkan untuk {teks}")
        if self._current_tab() == "riwayat":
            self._refresh_history()

    def _on_new(self) -> None:
        if self._dirty and not messagebox.askyesno(
            "Kosongkan form?", "Isian yang belum disimpan akan hilang. Lanjutkan?"
        ):
            return
        self._loading = True
        try:
            for key, var in self._vars.items():
                var.set(date.today().strftime(DATE_FORMAT) if key == "tanggal" else "")
            self._last = None
            self._cover = ()
            self._suggestion = None
            self._set_expense_rows(())
            self._recalc()
        finally:
            self._loading = False
        self._clear_preview()
        self._loaded_date = None
        self._dirty = False
        self._render_receipt()
        self._render_check()
        self._update_state_label()
        self._status_var.set("Form dikosongkan")

    def _current_tab(self) -> str:
        return next(k for k, p in self._pages.items() if p.winfo_manager())

    # ================= Riwayat =================
    def _shift_history(self, delta: int) -> None:
        index = self._hist_year * 12 + (self._hist_month - 1) + delta
        self._hist_year, m = divmod(index, 12)
        self._hist_month = m + 1
        self._refresh_history()

    def _month_rows(self):
        """[(record, report, check)] untuk bulan yang sedang dilihat."""
        rows = []
        for rec in self._repo.list_month(self._hist_year, self._hist_month):
            try:
                report = self._calculator.calculate(rec.data)
            except ValueError:
                continue
            rows.append((rec, report, self._service.check_live(report, rec.receipt, rec.cover)))
        return rows

    def _refresh_history(self) -> None:
        self._hist_title.config(text=f"{BULAN[self._hist_month - 1]} {self._hist_year}")
        self._tree.delete(*self._tree.get_children())
        try:
            rows = self._month_rows()
        except Exception as exc:
            self._hist_total.config(text=f"Gagal membaca data: {exc}")
            return
        masuk = keluar = sisa = 0
        for n, (rec, report, res) in enumerate(rows):
            d = rec.data.tanggal
            ket, tag = CHECK_SHORT[res.status]
            if res.status == cr.CHECKED and len(res.days) > 1:
                ket = "Gabung"
            simbol = {"ok": "✓ ", "bad": "✕ ", "warn": "• "}.get(tag, "")
            ket = simbol + ket
            # Hanya baris bermasalah yang diberi warna agar tabel tetap tenang
            tags = (["bad"] if tag == "bad" else []) + (["alt"] if n % 2 else [])
            self._tree.insert(
                "", "end", iid=d.isoformat(), tags=tuple(tags),
                values=(f"{HARI_PENDEK[d.weekday()]} {d.day:02d}", _titik(report.total_pemasukan),
                        _titik(report.total_pengeluaran), _titik(report.sisa), ket),
            )
            masuk += report.total_pemasukan
            keluar += report.total_pengeluaran
            sisa += report.sisa
        if rows:
            self._hist_total.config(
                text=f"{len(rows)} hari  ·  Pemasukan {_rupiah(masuk)}  ·  "
                     f"Pengeluaran {_rupiah(keluar)}  ·  Sisa {_rupiah(sisa)}")
        else:
            self._hist_total.config(text="Belum ada data tersimpan di bulan ini.")
    def _selected_date(self) -> Optional[date]:
        sel = self._tree.selection()
        return date.fromisoformat(sel[0]) if sel else None

    def _open_history_row(self) -> None:
        d = self._selected_date()
        if d is None:
            return
        try:
            record = self._repo.get(d)
        except Exception as exc:
            self._status_var.set(f"Gagal membaca data: {exc}")
            return
        if record is None:
            return
        if self._dirty and d != self._loaded_date and not messagebox.askyesno(
            "Muat data tersimpan?",
            "Isian yang sekarang belum disimpan dan akan diganti. Lanjutkan?",
        ):
            return
        self._load_record(record)
        self._show_page("rekap")

    def _on_delete_record(self) -> None:
        d = self._selected_date()
        if d is None:
            self._status_var.set("Pilih satu baris di tabel dulu")
            return
        if not messagebox.askyesno("Hapus data?", f"Hapus rekap tanggal {d.strftime(DATE_FORMAT)}?"):
            return
        try:
            self._repo.delete(d)
        except Exception as exc:
            messagebox.showerror("Gagal menghapus", str(exc))
            return
        if self._loaded_date == d:
            self._loaded_date = None
            self._update_state_label()
        self._refresh_history()
        self._status_var.set(f"Rekap {d.strftime(DATE_FORMAT)} dihapus")

    def _on_copy_month(self) -> None:
        try:
            rows = self._month_rows()
        except Exception as exc:
            self._status_var.set(f"Gagal membaca data: {exc}")
            return
        if not rows:
            self._status_var.set("Tidak ada data untuk disalin")
            return
        lines = [format_excel_row(rep, checked=res.status == cr.CHECKED) for _, rep, res in rows]
        self._root.clipboard_clear()
        self._root.clipboard_append("\n".join(lines))
        self._status_var.set(f"{len(lines)} baris ({BULAN[self._hist_month - 1]}) disalin ke clipboard")

    def _on_export_month_pdf(self) -> None:
        try:
            rows = self._month_rows()
        except Exception as exc:
            self._status_var.set(f"Gagal membaca data: {exc}")
            return
        if not rows:
            self._status_var.set("Tidak ada data untuk diekspor")
            return
        bulan = f"{BULAN[self._hist_month - 1]} {self._hist_year}"
        dest = filedialog.asksaveasfilename(
            title="Simpan laporan bulanan", defaultextension=".pdf",
            initialfile=f"Laporan {bulan}.pdf", filetypes=[("PDF", "*.pdf")])
        if not dest:
            return
        data = [(rep, res.status == cr.CHECKED) for _, rep, res in rows]
        try:
            self._pdf.export_month(data, dest, bulan)
        except PermissionError:
            messagebox.showerror("File sedang terbuka",
                                 "Tutup file PDF itu dulu, lalu coba lagi.")
            return
        self._status_var.set(f"Laporan {bulan} disimpan: {os.path.basename(dest)}")

    # ================= OCR =================
    def _on_pick(self) -> None:
        path = filedialog.askopenfilename(
            title="Pilih Bukti Transfer",
            filetypes=[("Gambar", "*.jpg *.jpeg *.png")],
        )
        if path:
            self._process_image(path)

    def _on_paste(self, event=None):
        """Ambil gambar dari clipboard (Ctrl+V / tombol Tempel)."""
        # Biarkan Ctrl+V biasa bekerja untuk menempel teks di kolom isian
        if event is not None and isinstance(self._root.focus_get(), (tk.Entry, ttk.Entry)):
            return None
        if self._busy:
            return "break"
        try:
            clip = ImageGrab.grabclipboard()
        except Exception as exc:
            self._status_var.set(f"Gagal membaca clipboard: {exc}")
            return "break"

        if isinstance(clip, Image.Image):  # screenshot / gambar yang di-copy
            fd, path = tempfile.mkstemp(suffix=".png", prefix="bukti_")
            os.close(fd)
            clip.convert("RGB").save(path)
            self._process_image(path, temp=True)
        elif (isinstance(clip, list) and clip
              and clip[0].lower().endswith((".png", ".jpg", ".jpeg"))):
            self._process_image(clip[0])   # file yang di-copy dari Explorer
        else:
            self._status_var.set("Clipboard tidak berisi gambar")
        return "break"

    def _process_image(self, path: str, temp: bool = False) -> None:
        self._last, self._cover, self._suggestion = None, (), None
        self._show_preview(path)
        self._render_receipt()
        self._render_check()
        self._set_busy(True)
        nama = "gambar dari clipboard" if temp else os.path.basename(path)
        self._status_var.set(f"Memproses {nama}...")
        # OCR di thread terpisah supaya jendela tidak membeku
        threading.Thread(target=self._work, args=(path, temp), daemon=True).start()

    def _work(self, path: str, temp: bool = False) -> None:
        try:
            result, error = self._extractor.extract(path), None
        except ReceiptError as exc:
            result, error = None, str(exc)
        except Exception as exc:  # jaga-jaga agar UI tidak macet
            result, error = None, f"Terjadi kesalahan: {exc}"
        finally:
            if temp:  # preview sudah dimuat ke memori, file sementara boleh dibuang
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._root.after(0, self._done, result, error)

    def _done(self, receipt: Optional[TransferReceipt], error: Optional[str]) -> None:
        self._set_busy(False)
        if error is not None or receipt is None:
            self._status_var.set("Gagal memproses gambar")
            messagebox.showerror("Gagal", error or "Tidak ada hasil.")
            return
        self._last = receipt
        self._cover = ()
        self._dirty = True  # bukti baru belum tersimpan
        try:
            self._suggestion = self._service.suggest(receipt, self._report)
        except Exception as exc:
            self._suggestion = None
            self._status_var.set(f"Gagal mencari gabungan: {exc}")
        self._render_receipt()
        self._render_check()
        self._update_state_label()
        if self._report is None:
            self._status_var.set("Bukti terbaca. Perbaiki isian rekap untuk pencocokan.")
        elif self._check is not None and self._check.status == cr.GABUNGAN:
            self._on_combine()  # tawarkan langsung pilihan gabungan

    # ================= Salin / simpan lainnya =================
    def _on_copy_excel(self) -> None:
        if self._report is None:
            self._status_var.set("Perbaiki isian yang ditandai merah dulu")
            return
        checked = self._check is not None and self._check.status == cr.CHECKED
        self._root.clipboard_clear()
        self._root.clipboard_append(format_excel_row(self._report, checked=checked))
        tgl = self._report.tanggal.strftime(DATE_FORMAT)
        self._status_var.set(
            f"Baris {tgl} disalin ke clipboard"
            + (" (Keterangan: Checked)" if checked else " (tanpa Checked)")
        )

    def _on_copy(self) -> None:
        if self._last is None:
            return
        self._root.clipboard_clear()
        self._root.clipboard_append(format_receipt(self._last))
        self._status_var.set("Hasil bukti disalin ke clipboard")

    def _on_save(self) -> None:
        if self._last is None:
            return
        dest = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Teks", "*.txt")]
        )
        if dest:
            self._exporter.export(self._last, dest)
            self._status_var.set(f"Tersimpan: {os.path.basename(dest)}")

    def run(self) -> None:
        self._root.mainloop()
