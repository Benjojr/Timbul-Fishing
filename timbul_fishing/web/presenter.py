"""Teks & warna status pencocokan untuk tampilan web (portasi dari UI Tkinter lama)."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Sequence, Tuple

from timbul_fishing.domain import check_result as cr
from timbul_fishing.domain.check_result import CheckResult
from timbul_fishing.domain.receipt import TransferReceipt
from timbul_fishing.domain.settlement import Candidate, Suggestion
from timbul_fishing.web.codec import rupiah

BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]
HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
HARI_PENDEK = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]

# status -> (label, tone). tone: ok | bad | warn | idle
CHECK_STYLES = {
    cr.CHECKED: ("CHECKED", "ok"),
    cr.SELISIH: ("SELISIH", "bad"),
    cr.GAGAL: ("TRANSFER GAGAL", "bad"),
    cr.TIDAK_TERBACA: ("NOMINAL TIDAK TERBACA", "warn"),
    cr.PERLU_CEK: ("CEK MANUAL", "warn"),
    cr.GABUNGAN: ("COCOK GABUNGAN", "warn"),
    cr.SUDAH_DIPAKAI: ("BUKTI SUDAH DIPAKAI", "bad"),
    cr.BELUM_ADA: ("BELUM ADA BUKTI", "idle"),
    cr.TIDAK_PERLU: ("TIDAK ADA TRANSFER", "idle"),
}
# status -> (teks singkat, tone) untuk tabel riwayat
CHECK_SHORT = {
    cr.CHECKED: ("Checked", "ok"), cr.SELISIH: ("Selisih", "bad"), cr.GAGAL: ("Gagal", "bad"),
    cr.TIDAK_TERBACA: ("Cek", "warn"), cr.PERLU_CEK: ("Cek", "warn"),
    cr.BELUM_ADA: ("Belum", "warn"), cr.TIDAK_PERLU: ("-", ""),
    cr.GABUNGAN: ("Cek", "warn"), cr.SUDAH_DIPAKAI: ("Dobel", "bad"),
}


def hari_text(days: Sequence[date]) -> str:
    return " + ".join(f"{d:%d/%m}" for d in days)


def describe(c: Candidate) -> str:
    days = " + ".join(f"{HARI_PENDEK[d.weekday()]} {d:%d/%m}" for d in c.days)
    extra = []
    if len(c.days) > 1 and not c.contiguous:
        extra.append("tidak berurutan")
    if c.after_transfer:
        extra.append("setelah tanggal transfer")
    return f"{days}  ({rupiah(c.total)})" + (f"  · {', '.join(extra)}" if extra else "")


def apply_suggestion(result: CheckResult, receipt: Optional[TransferReceipt],
                     cover: Sequence[date], sug: Optional[Suggestion]) -> CheckResult:
    """Bukti baru yang belum cocok satu hari: tawarkan gabungan / tandai bukti dobel."""
    if (receipt is None or cover or sug is None
            or result.status in (cr.CHECKED, cr.PERLU_CEK, cr.GAGAL, cr.TIDAK_TERBACA)):
        return result
    if sug.duplicate_days:
        return CheckResult(status=cr.SUDAH_DIPAKAI, sisa=result.sisa,
                           nominal=receipt.nominal, days=sug.duplicate_days)
    if sug.candidates:
        return CheckResult(status=cr.GABUNGAN, sisa=result.sisa, nominal=receipt.nominal,
                           days=sug.candidates[0].days)
    return result


def _detail_core(c: CheckResult, sug: Optional[Suggestion]) -> str:
    if c.status == cr.GABUNGAN:
        n = len(sug.candidates) if sug else 1
        extra = f" (+{n - 1} kemungkinan lain)" if n > 1 else ""
        return (f"Transfer {rupiah(c.nominal)} cocok dengan gabungan "
                f"{hari_text(c.days)}{extra}. Klik 'Gabungan…' untuk menerapkan.")
    if c.status == cr.SUDAH_DIPAKAI:
        return f"Bukti ini sudah tercatat untuk {hari_text(c.days)}."
    multi = len(c.days) > 1
    if c.status == cr.CHECKED:
        if multi:
            return f"Transfer {rupiah(c.nominal)} sama dengan total sisa {hari_text(c.days)}."
        return f"Transfer {rupiah(c.nominal)} sama dengan sisa."
    if c.status == cr.SELISIH:
        arah = "lebih" if (c.selisih or 0) > 0 else "kurang"
        if multi:
            return (f"Transfer {rupiah(c.nominal)}, total sisa {hari_text(c.days)} "
                    f"{rupiah(c.sisa)}: {arah} {rupiah(abs(c.selisih or 0))}.")
        return (f"Transfer {rupiah(c.nominal)}, sisa {rupiah(c.sisa)}: "
                f"{arah} {rupiah(abs(c.selisih or 0))}.")
    if c.status == cr.GAGAL:
        return "Bukti menyatakan transfer gagal."
    if c.status == cr.TIDAK_TERBACA:
        return "Nominal pada bukti tidak terbaca. Periksa gambarnya."
    if c.status == cr.PERLU_CEK:
        return "Nominal sama, tetapi status transfer tidak terbaca. Cek bukti secara manual."
    if c.status == cr.TIDAK_PERLU:
        return "Sisa 0, tidak ada yang perlu ditransfer."
    return f"Pilih bukti transfer untuk sisa {rupiah(c.sisa)}."


def check_view(c: CheckResult, sug: Optional[Suggestion]) -> Dict[str, Any]:
    label, tone = CHECK_STYLES[c.status]
    detail = _detail_core(c, sug)
    if c.catatan:
        detail += "\n" + c.catatan
    return {"status": c.status, "label": label, "tone": tone, "detail": detail}


def invalid_view() -> Dict[str, Any]:
    return {"status": "invalid", "label": "INPUT TIDAK VALID", "tone": "warn",
            "detail": "Periksa isian yang ditandai merah."}


def short_view(c: CheckResult) -> Tuple[str, str]:
    """(teks, tone) untuk satu baris riwayat."""
    ket, tone = CHECK_SHORT[c.status]
    if c.status == cr.CHECKED and len(c.days) > 1:
        ket = "Gabung"
    simbol = {"ok": "✓ ", "bad": "✕ ", "warn": "• "}.get(tone, "")
    return simbol + ket, tone
