from __future__ import annotations

from datetime import date
from typing import List, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from timbul_fishing.core.formatting import keterangan
from timbul_fishing.domain.daily_report import DailyReport

_HARI = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
_GOLD, _BAND, _LINE = colors.HexColor("#E8B04B"), colors.HexColor("#F8EDD3"), colors.HexColor("#D9C9A3")
_TEXT, _RED = colors.HexColor("#2B2B2B"), colors.HexColor("#C0392B")

_HEADERS = ["Tanggal", "Hari", "Sesi 1", "Sesi 2", "Sesi 3",
            "Ticket\nSesi 1", "Ticket\nSesi 2", "Ticket\nSesi 3",
            "Total\nPemasukan", "Hadiah", "Pengeluaran", "Total\nPengeluaran", "Sisa", "Keterangan"]
_WIDTHS = [52, 28, 30, 30, 30, 42, 42, 42, 62, 58, 54, 62, 58, 204]   # total 794 pt


def _n(v: int) -> str:
    """Angka dengan titik ribuan (5.560.000); nol dikosongkan."""
    return "" if v == 0 else f"{v:,}".replace(",", ".")


def _total(v: int) -> str:
    return "-" if v == 0 else f"{v:,}".replace(",", ".")


def _rp(v: int) -> str:
    return f"Rp {v:,}".replace(",", ".")


class PdfMonthExporter:
    """Laporan bulanan sebagai PDF A4 landscape: rekap harian + rincian pengeluaran."""

    def __init__(self, usaha: str = "Timbul Fishing") -> None:
        self._usaha = usaha

    def export_month(self, rows: Sequence[Tuple[DailyReport, bool]],
                     path: str, title: str) -> None:
        data = sorted(rows, key=lambda x: x[0].tanggal)
        page = landscape(A4)
        doc = SimpleDocTemplate(
            path, pagesize=page, leftMargin=24, rightMargin=24, topMargin=22, bottomMargin=32,
            title=f"Laporan Bulanan {title}", author=self._usaha)

        h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, textColor=_TEXT, leading=18)
        h2 = ParagraphStyle("h2", fontName="Helvetica", fontSize=10.5, textColor=colors.HexColor("#6B5A2E"),
                            leading=13, spaceAfter=2)
        sec = ParagraphStyle("sec", fontName="Helvetica-Bold", fontSize=11, textColor=_TEXT,
                             leading=14, spaceBefore=14, spaceAfter=6, keepWithNext=True)
        small = ParagraphStyle("small", fontName="Helvetica", fontSize=8, textColor=_TEXT, leading=9.6)

        masuk = sum(r.total_pemasukan for r, _ in data)
        keluar = sum(r.total_pengeluaran for r, _ in data)
        sisa = sum(r.sisa for r, _ in data)
        story: List = [
            Paragraph(self._usaha, h1),
            Paragraph(f"Laporan Bulanan &middot; {title}", h2),
            Paragraph(f"{len(data)} hari &nbsp;|&nbsp; Pemasukan <b>{_rp(masuk)}</b> &nbsp;|&nbsp; "
                      f"Pengeluaran <b>{_rp(keluar)}</b> &nbsp;|&nbsp; Sisa <b>{_rp(sisa)}</b>",
                      ParagraphStyle("sum", parent=small, fontSize=9.5, leading=12, spaceAfter=6)),
            self._summary_table(data, small),
        ]

        items = self._expense_items(data)
        if items:
            story += [Paragraph("Rincian Pengeluaran", sec), self._expense_table(items, small)]

        doc.build(story, onFirstPage=self._footer(title), onLaterPages=self._footer(title))

    # ---------- tabel rekap harian ----------
    @staticmethod
    def _summary_table(data, small) -> Table:
        table = [_HEADERS]
        for rep, checked in data:
            s = rep.sesi
            table.append([
                rep.tanggal.strftime("%d/%m/%Y"), _HARI[rep.tanggal.weekday()],
                _n(s[0].peserta), _n(s[1].peserta), _n(s[2].peserta),
                *[_n(x.harga) if x.peserta else "" for x in s],
                _total(rep.total_pemasukan), _n(rep.hadiah), _n(rep.pengeluaran),
                _total(rep.total_pengeluaran), _total(rep.sisa),
                Paragraph(keterangan(rep, checked).replace("&", "&amp;").replace("<", "&lt;"), small),
            ])
        n = len(data)
        table.append([
            "TOTAL", "",
            _total(sum(r.sesi[0].peserta for r, _ in data)), _total(sum(r.sesi[1].peserta for r, _ in data)),
            _total(sum(r.sesi[2].peserta for r, _ in data)), "", "", "",
            _total(sum(r.total_pemasukan for r, _ in data)), _total(sum(r.hadiah for r, _ in data)),
            _total(sum(r.pengeluaran for r, _ in data)), _total(sum(r.total_pengeluaran for r, _ in data)),
            _total(sum(r.sisa for r, _ in data)), "",
        ])

        style = [
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), _TEXT),
            ("BACKGROUND", (0, 0), (-1, 0), _GOLD),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, n), [colors.white, _BAND]),
            ("BACKGROUND", (0, n + 1), (-1, n + 1), _GOLD),
            ("FONT", (0, n + 1), (-1, n + 1), "Helvetica-Bold", 8),
            ("FONT", (12, 1), (12, n), "Helvetica-Bold", 8),
            ("ALIGN", (2, 1), (12, -1), "RIGHT"),
            ("ALIGN", (1, 1), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
            ("TOPPADDING", (0, 0), (-1, 0), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3.5),
            ("TOPPADDING", (0, 1), (-1, -1), 1.6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 1.6),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]
        for i, (rep, _) in enumerate(data, start=1):
            if rep.sisa < 0:
                style.append(("TEXTCOLOR", (12, i), (12, i), _RED))
        if sum(r.sisa for r, _ in data) < 0:
            style.append(("TEXTCOLOR", (12, n + 1), (12, n + 1), _RED))
        t = Table(table, colWidths=_WIDTHS, repeatRows=1)
        t.setStyle(TableStyle(style))
        return t

    # ---------- rincian pengeluaran ----------
    @staticmethod
    def _expense_items(data):
        items = []
        for rep, _ in data:
            rows = [(i.keperluan, i.nominal) for i in rep.rincian]
            if not rows and rep.pengeluaran:        # data lama: hanya satu angka total
                rows = [("Belum dirinci", rep.pengeluaran)]
            items += [(rep.tanggal, k, v) for k, v in rows]
        return items

    @staticmethod
    def _expense_table(items, small) -> Table:
        table = [["Tanggal", "Hari", "Keperluan", "Nominal"]]
        for d, k, v in items:
            table.append([d.strftime("%d/%m/%Y"), _HARI[d.weekday()],
                          Paragraph(k.replace("&", "&amp;").replace("<", "&lt;") or "-", small), _n(v) or "0"])
        n = len(items)
        table.append(["TOTAL", "", "", _total(sum(v for _, _, v in items))])
        t = Table(table, colWidths=[62, 30, 300, 80], repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
            ("TEXTCOLOR", (0, 0), (-1, -1), _TEXT),
            ("BACKGROUND", (0, 0), (-1, 0), _GOLD),
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
            ("ROWBACKGROUNDS", (0, 1), (-1, n), [colors.white, _BAND]),
            ("BACKGROUND", (0, n + 1), (-1, n + 1), _GOLD),
            ("FONT", (0, n + 1), (-1, n + 1), "Helvetica-Bold", 8),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, _LINE),
            ("TOPPADDING", (0, 1), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 2.5),
        ]))
        return t

    def _footer(self, title: str):
        def draw(canvas, doc) -> None:
            canvas.saveState()
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(colors.HexColor("#8A8A8A"))
            y = 18
            canvas.drawString(doc.leftMargin, y, f"{self._usaha} - Laporan Bulanan {title}")
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, y,
                                   f"Dicetak {date.today().strftime('%d/%m/%Y')}  |  Halaman {doc.page}")
            canvas.restoreState()
        return draw

