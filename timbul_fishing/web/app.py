"""Lapisan web (Flask). Hanya bergantung pada core dan domain, bukan pada OCR/parser/SQLite.

API tanpa status (stateless): browser mengirim isian form + bukti yang sedang tampil,
server menghitung ulang semuanya memakai core yang sama dengan versi desktop.
"""
from __future__ import annotations

import os
import tempfile
from datetime import date
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from flask import Flask, Response, abort, jsonify, request, send_file, send_from_directory


from timbul_fishing.core.errors import ReceiptConflictError, ReceiptError
from timbul_fishing.core.extractor import ReceiptExtractor
from timbul_fishing.core.formatting import format_excel_row, format_receipt
from timbul_fishing.core.interfaces import (DailyRecordRepository, MonthReportExporter,
                                            ReceiptExporter, ReceiptImageStore)
from timbul_fishing.core.report_calculator import DailyReportCalculator
from timbul_fishing.core.settlement_service import SettlementService
from timbul_fishing.domain import check_result as cr
from timbul_fishing.domain.daily_record import DailyRecord
from timbul_fishing.domain.daily_report import DailyReport
from timbul_fishing.domain.receipt import TransferReceipt
from timbul_fishing.domain.settlement import Suggestion
from timbul_fishing.web import presenter
from timbul_fishing.web.codec import (parse_days, parse_form, parse_iso, receipt_from_dict,
                                receipt_to_dict, record_to_form, rupiah, titik)

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]"}
_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
HEADER_NAME, HEADER_VALUE = "X-TimbulFishing", "1"


def _fail(message: str, status: int = 400, **extra: Any):
    return jsonify({"error": message, **extra}), status


def create_app(
    extractor: ReceiptExtractor,
    exporter: ReceiptExporter,
    calculator: DailyReportCalculator,
    repository: DailyRecordRepository,
    service: SettlementService,
    pdf_exporter: MonthReportExporter,
    images: ReceiptImageStore,
    lan: bool = False,
) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
    app.json.ensure_ascii = False  # type: ignore[attr-defined]

    # ------------------------------------------------------------ pengaman
    @app.before_request
    def _guard():
        if not lan:  # cegah DNS-rebinding: hanya nama host lokal yang dilayani
            host = request.host
            name = host[:host.rfind(":")] if ":" in host and not host.endswith("]") else host
            if name not in _LOCAL_HOSTS:
                abort(403)
        # Header kustom memaksa preflight CORS, sehingga situs lain tidak bisa menulis data.
        if request.method not in ("GET", "HEAD", "OPTIONS") \
                and request.headers.get(HEADER_NAME) != HEADER_VALUE:
            abort(403)

    @app.after_request
    def _no_cache(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(403)
    def _forbidden(_e):
        return _fail("Akses ditolak.", 403)

    @app.errorhandler(413)
    def _too_big(_e):
        return _fail("Gambar terlalu besar (maksimum 20 MB).", 413)

    @app.errorhandler(404)
    def _missing(_e):
        return _fail("Tidak ditemukan.", 404)

    @app.errorhandler(Exception)
    def _unexpected(exc):
        from werkzeug.exceptions import HTTPException
        if isinstance(exc, HTTPException):
            return _fail(exc.description or exc.name, exc.code or 500)
        app.logger.exception("Kesalahan tak terduga")
        return _fail(f"Terjadi kesalahan: {exc}", 500)

    # ------------------------------------------------------------ halaman
    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")  # type: ignore[arg-type]

    # ------------------------------------------------------------ helper
    def _body() -> Dict[str, Any]:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            abort(400, "Permintaan tidak valid.")
        return data

    def _month_params() -> Tuple[int, int]:
        try:
            year, month = int(request.args["year"]), int(request.args["month"])
        except (KeyError, ValueError):
            abort(400, "Parameter year/month tidak valid.")
        if not (1 <= month <= 12 and 1900 <= year <= 3000):
            abort(400, "Bulan atau tahun di luar jangkauan.")
        return year, month

    def _report_dict(r: DailyReport) -> Dict[str, Any]:
        return {
            "subtotals": [rupiah(s.peserta * s.harga) for s in r.sesi],
            "pemasukan": rupiah(r.total_pemasukan),
            "pengeluaran": rupiah(r.total_pengeluaran),
            "rincian": rupiah(r.pengeluaran) if r.rincian else "",
            "sisa": rupiah(r.sisa),
            "sisa_negatif": r.sisa < 0,
        }

    def _cands(sug: Optional[Suggestion]) -> List[Dict[str, Any]]:
        if sug is None:
            return []
        return [{"days": [d.isoformat() for d in c.days], "total": c.total,
                 "text": presenter.describe(c)} for c in sug.candidates]

    # ------------------------------------------------------------ gambar bukti
    def _has_image(rec: Optional[DailyRecord]) -> bool:
        image = getattr(rec, "image", None)
        return image is not None and images.path_of(image) is not None

    def _keep_image(token: Optional[str], days) -> Optional[str]:
        """Pindahkan gambar sementara ke folder bukti dan catat di database.
        Mengembalikan teks peringatan bila gagal (rekap sendiri tetap tersimpan)."""
        if not token or not days:
            return None
        first = min(days)
        try:
            rec = repository.get(first)
            if rec is not None and _has_image(rec):  # bukti ini sudah punya gambar yang utuh
                images.discard(token)
                return None
            repository.set_receipt_image(first, images.commit(token, first))
        except (OSError, ValueError) as exc:
            app.logger.exception("Gagal menyimpan gambar bukti")
            return f"Gambar bukti gagal disimpan: {exc}"
        return None

    def _release_image(name: Optional[str]) -> None:
        """Singkirkan berkas gambar yang tidak dipakai bukti mana pun lagi."""
        if not name or repository.image_in_use(name):
            return
        try:
            images.archive(name)
        except OSError:
            app.logger.exception("Gagal memindahkan gambar bukti yang tidak terpakai")

    @app.get("/api/receipt-image")
    def receipt_image():
        d = parse_iso(request.args.get("tanggal", ""))
        if d is None:
            return _fail("Tanggal tidak valid.")
        rec = repository.get(d)
        image = getattr(rec, "image", None)
        path = images.path_of(image) if image else None
        if path is None:
            abort(404)
        return send_file(path)

    # ------------------------------------------------------------ evaluasi
    @app.post("/api/evaluate")
    def evaluate():
        body = _body()
        try:
            receipt = receipt_from_dict(body.get("receipt"))
            cover = parse_days(body.get("cover"))
        except (ValueError, TypeError):
            return _fail("Data bukti tidak valid.")
        data, invalid = parse_form(body.get("form") or {})
        report = None
        if data is not None:
            try:
                report = calculator.calculate(data)
            except ValueError:
                invalid = ["form"]

        sug: Optional[Suggestion] = None
        warning = None
        if receipt is not None and not cover:
            try:
                sug = service.suggest(receipt, report)
            except Exception as exc:  # pencarian gabungan tidak boleh menjatuhkan form
                warning = f"Gagal mencari gabungan: {exc}"

        if report is None:
            check = presenter.invalid_view()
            excel_row = None
        else:
            result = service.check_live(report, receipt, cover)
            result = presenter.apply_suggestion(result, receipt, cover, sug)
            check = presenter.check_view(result, sug)
            excel_row = format_excel_row(report, checked=result.status == cr.CHECKED)
        return jsonify({
            "invalid": invalid,
            "report": _report_dict(report) if report else None,
            "check": check,
            "candidates": _cands(sug),
            "excel_row": excel_row,
            "receipt_text": format_receipt(receipt) if receipt else None,
            "warning": warning,
        })

    # ------------------------------------------------------------ OCR
    @app.post("/api/ocr")
    def ocr():
        file = request.files.get("image")
        if file is None or not file.filename and not file.mimetype.startswith("image/"):
            return _fail("Tidak ada gambar yang dikirim.")
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in _IMAGE_EXT:
            ext = ".png" if file.mimetype == "image/png" else ".jpg"
        data = file.read()
        fd, path = tempfile.mkstemp(suffix=ext, prefix="bukti_")
        os.close(fd)
        try:
            with open(path, "wb") as f:
                f.write(data)
            receipt = extractor.extract(path)
        except ReceiptError as exc:
            return _fail(str(exc), 422)
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        token, image_error = None, None
        try:  # gambar ditahan dulu; baru disimpan permanen saat rekap disimpan
            token = images.stage(data)
        except (OSError, ValueError) as exc:
            app.logger.warning("Gambar bukti tidak bisa ditahan: %s", exc)
            image_error = str(exc)
        return jsonify({"receipt": receipt_to_dict(receipt), "image_token": token,
                        "image_error": image_error})

    # ------------------------------------------------------------ rekap tersimpan
    @app.get("/api/record")
    def get_record():
        d = parse_iso(request.args.get("tanggal", ""))
        if d is None:
            return _fail("Tanggal tidak valid.")
        rec = repository.get(d)
        if rec is None:
            return jsonify({"record": None})
        return jsonify({"record": {
            "form": record_to_form(rec),
            "receipt": receipt_to_dict(rec.receipt),
            "cover": [x.isoformat() for x in rec.cover],
            "has_image": _has_image(rec),
        }})

    @app.post("/api/record")
    def save_record():
        body = _body()
        data, invalid = parse_form(body.get("form") or {})
        if data is None:
            return _fail("Perbaiki isian yang ditandai merah dulu.", invalid=invalid)
        try:
            receipt = receipt_from_dict(body.get("receipt"))
            cover = parse_days(body.get("cover"))
        except (ValueError, TypeError):
            return _fail("Data bukti tidak valid.")
        d = data.tanggal
        before = repository.get(d)
        if (before is not None and body.get("loaded") != d.isoformat()
                and not body.get("overwrite")):
            return _fail(f"Tanggal {d:%d/%m/%Y} sudah punya data tersimpan.", 409,
                         needs_confirm=True)
        repository.save(DailyRecord(data=data))

        warning = None
        if receipt is not None and d not in cover:  # transfer harian biasa
            try:
                service.apply(receipt, [d], replace=True)
                cover = (d,)
            except ReceiptConflictError as exc:
                hari = presenter.hari_text(exc.days) if exc.days else ""
                warning = (f"{exc} {hari}. Rekap tetap tersimpan, tetapi tanpa bukti ini.").strip()
                receipt, cover = None, ()

        if receipt is not None:
            image_warning = _keep_image(body.get("image_token"), cover)
            warning = " ".join(x for x in (warning, image_warning) if x) or None
        if before is not None:  # bukti lama yang tergantikan: gambarnya ikut disingkirkan
            _release_image(before.image)
        return jsonify({
            "saved": d.isoformat(),
            "receipt": receipt_to_dict(receipt),
            "cover": [x.isoformat() for x in cover],
            "has_image": _has_image(repository.get(d)),
            "warning": warning,
        })

    @app.delete("/api/record")
    def delete_record():
        d = parse_iso(request.args.get("tanggal", ""))
        if d is None:
            return _fail("Tanggal tidak valid.")
        before = repository.get(d)
        repository.delete(d)
        if before is not None:
            _release_image(before.image)
        return jsonify({"deleted": d.isoformat()})

    @app.post("/api/apply")
    def apply_days():
        """Terapkan satu bukti ke beberapa hari (pembayaran gabungan)."""
        body = _body()
        try:
            receipt = receipt_from_dict(body.get("receipt"))
            days = parse_days(body.get("days"))
        except (ValueError, TypeError):
            return _fail("Data tidak valid.")
        if receipt is None or not days:
            return _fail("Bukti dan hari harus diisi.")
        data, invalid = parse_form(body.get("form") or {})
        current = data.tanggal if data is not None else parse_iso(
            str((body.get("form") or {}).get("tanggal") or ""))
        includes_form = current in days
        try:
            if includes_form:
                if data is None:
                    return _fail("Perbaiki isian yang ditandai merah dulu.", invalid=invalid)
                repository.save(DailyRecord(data=data))  # hari form harus tersimpan dulu
            service.apply(receipt, days)
        except ReceiptConflictError as exc:
            return _fail(str(exc), 409)
        return jsonify({
            "includes_form": includes_form,
            "cover": [d.isoformat() for d in days] if includes_form else [],
            "text": presenter.hari_text(days),
            "warning": _keep_image(body.get("image_token"), days),
        })

    # ------------------------------------------------------------ riwayat
    def _month_rows(year: int, month: int):
        rows = []
        for rec in repository.list_month(year, month):
            try:
                report = calculator.calculate(rec.data)
            except ValueError:
                continue
            rows.append((rec, report, service.check_live(report, rec.receipt, rec.cover)))
        return rows

    @app.get("/api/month")
    def month():
        year, mon = _month_params()
        rows = _month_rows(year, mon)
        out, masuk, keluar, sisa = [], 0, 0, 0
        for rec, rep, res in rows:
            d = rec.data.tanggal
            ket, tone = presenter.short_view(res)
            out.append({
                "tanggal": d.isoformat(),
                "hari": f"{presenter.HARI_PENDEK[d.weekday()]} {d.day:02d}",
                "masuk": titik(rep.total_pemasukan), "keluar": titik(rep.total_pengeluaran),
                "sisa": titik(rep.sisa), "ket": ket, "tone": tone,
                "has_image": _has_image(rec),
                "has_receipt": rec.receipt is not None,
            })
            masuk += rep.total_pemasukan
            keluar += rep.total_pengeluaran
            sisa += rep.sisa
        summary = (f"{len(rows)} hari  ·  Pemasukan {rupiah(masuk)}  ·  "
                   f"Pengeluaran {rupiah(keluar)}  ·  Sisa {rupiah(sisa)}") if rows else None
        return jsonify({
            "title": f"{presenter.BULAN[mon - 1]} {year}",
            "rows": out,
            "summary": summary,
        })

    @app.get("/api/month.pdf")
    def month_pdf():
        year, mon = _month_params()
        rows = _month_rows(year, mon)
        if not rows:
            abort(404, "Tidak ada data untuk diekspor.")
        bulan = f"{presenter.BULAN[mon - 1]} {year}"
        fd, path = tempfile.mkstemp(suffix=".pdf", prefix="laporan_")
        os.close(fd)
        try:
            pdf_exporter.export_month([(rep, res.status == cr.CHECKED) for _, rep, res in rows],
                                      path, bulan)
            with open(path, "rb") as f:
                content = f.read()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        return Response(content, mimetype="application/pdf", headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'Laporan {bulan}.pdf')}"})

    # ------------------------------------------------------------ ekspor bukti
    @app.post("/api/receipt/txt")
    def receipt_txt():
        try:
            receipt = receipt_from_dict(_body().get("receipt"))
        except (ValueError, TypeError):
            return _fail("Data bukti tidak valid.")
        if receipt is None:
            return _fail("Belum ada bukti.")
        fd, path = tempfile.mkstemp(suffix=".txt", prefix="bukti_")
        os.close(fd)
        try:
            exporter.export(receipt, path)
            with open(path, "rb") as f:
                content = f.read()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        return Response(content, mimetype="text/plain; charset=utf-8", headers={
            "Content-Disposition": "attachment; filename=bukti-transfer.txt"})

    return app
