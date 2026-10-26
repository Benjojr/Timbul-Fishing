from __future__ import annotations

from datetime import datetime, time
from typing import Sequence, Tuple

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from bukti_tf.core.formatting import HARI_EXCEL, keterangan
from bukti_tf.domain.daily_report import DailyReport

HEADERS = [
    "Tanggal", "Hari", "Sesi 1", "Sesi 2", "Sesi 3",
    "Ticket Sesi 1", "Ticket Sesi 2", "Ticket Sesi 3",
    "Total Pemasukan", "Hadiah", "Pengeluaran", "Total Pengeluaran", "Sisa", "Keterangan",
]
DETAIL_HEADERS = ["Tanggal", "Keperluan", "Nominal"]
DETAIL_SHEET = "Pengeluaran"
GOLD, BAND = "#E8B04B", "#F8EDD3"
NUM = "#,##0;[Red]-#,##0"
NUM_HIDE0 = "#,##0;[Red]-#,##0;;@"   # nol dikosongkan


class XlsxMonthExporter:
    def export_month(self, rows: Sequence[Tuple[DailyReport, bool]],
                     path: str, title: str) -> None:
        data = sorted(rows, key=lambda x: x[0].tanggal)
        wb = xlsxwriter.Workbook(path)
        ws = wb.add_worksheet(title[:31])
        det = wb.add_worksheet(DETAIL_SHEET)

        base = {"font_name": "Calibri", "font_size": 11, "valign": "vcenter",
                "border": 1, "border_color": "#D9C9A3"}
        head = wb.add_format({**base, "bold": True, "bg_color": GOLD,
                              "align": "center", "text_wrap": True})

        def fmts(bg):
            b = {**base, **({"bg_color": bg} if bg else {})}
            return {
                "txt": wb.add_format(b),
                "date": wb.add_format({**b, "num_format": "dd/mm/yyyy", "align": "left"}),
                "num": wb.add_format({**b, "num_format": NUM}),
                "num0": wb.add_format({**b, "num_format": NUM_HIDE0}),
                "bold": wb.add_format({**b, "num_format": NUM, "bold": True}),
            }

        plain, band, total = fmts(None), fmts(BAND), fmts(GOLD)

        def dt(d):
            return datetime.combine(d, time())

        # ---------- Sheet 2: rincian pengeluaran (satu baris per keperluan) ----------
        for c, h in enumerate(DETAIL_HEADERS):
            det.write(0, c, h, head)
        dr = 1
        for rep, _ in data:
            items = [(i.keperluan, i.nominal) for i in rep.rincian]
            if not items and rep.pengeluaran:        # data lama: hanya satu angka total
                items = [("Belum dirinci", rep.pengeluaran)]
            for keperluan, nominal in items:
                f = band if dr % 2 == 0 else plain
                det.write_datetime(dr, 0, dt(rep.tanggal), f["date"])
                det.write(dr, 1, keperluan, f["txt"])
                det.write(dr, 2, nominal, f["num"])
                dr += 1
        det.freeze_panes(1, 0)
        det.set_column(0, 0, 12)
        det.set_column(1, 1, 34)
        det.set_column(2, 2, 14)

        # ---------- Sheet 1: rekap harian ----------
        for c, h in enumerate(HEADERS):
            ws.write(0, c, h, head)

        for i, (rep, checked) in enumerate(data):
            r, x = i + 1, i + 2          # r = indeks 0-based, x = nomor baris Excel
            f = band if i % 2 else plain
            ws.write_datetime(r, 0, dt(rep.tanggal), f["date"])
            ws.write(r, 1, HARI_EXCEL[rep.tanggal.weekday()], f["txt"])
            for c, s in enumerate(rep.sesi):
                ws.write(r, 2 + c, s.peserta or None, f["num"])
                ws.write(r, 5 + c, s.harga if s.peserta else None, f["num"])
            ws.write_formula(r, 8, f"=C{x}*F{x}+D{x}*G{x}+E{x}*H{x}", f["num"],
                             rep.total_pemasukan)
            ws.write(r, 9, rep.hadiah or None, f["num"])
            # Pengeluaran = jumlah rincian pada tanggal ini di sheet "Pengeluaran"
            ws.write_formula(
                r, 10,
                f"=SUMIF({DETAIL_SHEET}!$A:$A,A{x},{DETAIL_SHEET}!$C:$C)",
                f["num0"], rep.pengeluaran)
            ws.write_formula(r, 11, f"=J{x}+K{x}", f["num"], rep.total_pengeluaran)
            ws.write_formula(r, 12, f"=I{x}-L{x}", f["bold"], rep.sisa)
            ws.write(r, 13, keterangan(rep, checked) or None, f["txt"])

        # Baris TOTAL
        n, t = len(data), len(data) + 1
        for c in range(len(HEADERS)):
            ws.write_blank(t, c, None, total["txt"])
        ws.write(t, 0, "TOTAL", total["txt"])
        sums = {2 + k: sum(rep.sesi[k].peserta for rep, _ in data) for k in range(3)}
        sums.update({
            8: sum(r.total_pemasukan for r, _ in data),
            9: sum(r.hadiah for r, _ in data),
            10: sum(r.pengeluaran for r, _ in data),
            11: sum(r.total_pengeluaran for r, _ in data),
            12: sum(r.sisa for r, _ in data),
        })
        for c, val in sums.items():
            col = xl_col_to_name(c)
            ws.write_formula(t, c, f"=SUM({col}2:{col}{n + 1})", total["bold"], val)

        ws.freeze_panes(1, 2)
        ws.set_row(0, 32)
        ws.set_column(0, 0, 12)
        ws.set_column(1, 1, 7)
        ws.set_column(2, 4, 8)
        ws.set_column(5, 7, 13)
        ws.set_column(8, 12, 16)
        ws.set_column(13, 13, 30)
        ws.set_landscape()
        ws.fit_to_pages(1, 0)
        ws.activate()
        wb.close()
