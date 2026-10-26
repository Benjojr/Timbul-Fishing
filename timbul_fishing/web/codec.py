"""Penerjemah antara JSON (dari browser) dan objek domain. Tanpa Flask, tanpa GUI."""
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from timbul_fishing.domain.daily_record import DailyRecord
from timbul_fishing.domain.daily_report import DailyInput, ExpenseItem, SessionEntry
from timbul_fishing.domain.receipt import TransferReceipt

MAX_DIGITS = 12  # batas wajar (sampai ratusan miliar) agar aman disimpan di SQLite


def titik(angka: int) -> str:
    sign = "-" if angka < 0 else ""
    return sign + f"{abs(angka):,}".replace(",", ".")


def rupiah(angka: Optional[int]) -> str:
    return "-" if angka is None else "Rp " + titik(angka)


def money_text(n: int) -> str:
    return "" if n == 0 else titik(n)


def parse_int(teks: str) -> int:
    """'1.500.000' / 'Rp 1,500,000' / '' -> int. Selain angka -> ValueError."""
    bersih = re.sub(r"(?i)rp|[\s.,]", "", teks)
    if bersih == "":
        return 0
    if not bersih.isdigit() or len(bersih) > MAX_DIGITS:
        raise ValueError(teks)
    return int(bersih)


def parse_iso(teks: str) -> Optional[date]:
    try:
        return date.fromisoformat(teks.strip())
    except ValueError:
        return None


# ---------------------------------------------------------------- form <-> domain
def parse_form(form: Dict[str, Any]) -> Tuple[Optional[DailyInput], List[str]]:
    """
    Form JSON -> DailyInput. Bila ada isian salah, kembalikan (None, [kunci isian salah]).
    Kunci: tanggal, peserta0..2, harga0..2, hadiah, rincian<indeks baris>.
    """
    invalid: List[str] = []

    def num(key: str, raw: Any) -> int:
        try:
            return parse_int("" if raw is None else str(raw))
        except ValueError:
            invalid.append(key)
            return 0

    tanggal = parse_iso(str(form.get("tanggal") or ""))
    if tanggal is None:
        invalid.append("tanggal")

    raw_sesi = form.get("sesi") or []
    sesi = []
    for i in range(3):
        row = raw_sesi[i] if i < len(raw_sesi) and isinstance(raw_sesi[i], dict) else {}
        sesi.append(SessionEntry(peserta=num(f"peserta{i}", row.get("peserta")),
                                 harga=num(f"harga{i}", row.get("harga"))))

    hadiah = num("hadiah", form.get("hadiah"))

    items: List[ExpenseItem] = []
    for i, row in enumerate(form.get("rincian") or []):
        if not isinstance(row, dict):
            continue
        keperluan = str(row.get("keperluan") or "").strip()
        teks = str(row.get("nominal") or "").strip()
        if not keperluan and not teks:
            continue  # baris kosong diabaikan
        try:
            nominal = parse_int(teks)
            ok = nominal > 0 or not keperluan  # keperluan tanpa nominal = belum lengkap
        except ValueError:
            nominal, ok = 0, False
        if not ok:
            invalid.append(f"rincian{i}")
        if nominal == 0 and not keperluan:
            continue  # "0" saja tanpa keperluan: abaikan
        items.append(ExpenseItem(keperluan=keperluan, nominal=nominal))

    if invalid or tanggal is None:
        return None, invalid
    data = DailyInput(tanggal=tanggal, sesi=tuple(sesi),  # type: ignore[arg-type]
                      hadiah=hadiah, rincian=tuple(items),
                      catatan=str(form.get("catatan") or "").strip())
    return data, []


def record_to_form(rec: DailyRecord) -> Dict[str, Any]:
    d = rec.data
    rincian = [{"keperluan": i.keperluan, "nominal": money_text(i.nominal)} for i in d.rincian]
    if not rincian and d.pengeluaran:  # data lama: hanya satu angka total
        rincian = [{"keperluan": "Belum dirinci", "nominal": money_text(d.pengeluaran)}]
    return {
        "tanggal": d.tanggal.isoformat(),
        "sesi": [{"peserta": "" if s.peserta == 0 else str(s.peserta),
                  "harga": money_text(s.harga)} for s in d.sesi],
        "hadiah": money_text(d.hadiah),
        "rincian": rincian,
        "catatan": d.catatan,
    }


# ---------------------------------------------------------------- bukti <-> JSON
def receipt_to_dict(r: Optional[TransferReceipt]) -> Optional[Dict[str, Any]]:
    if r is None:
        return None
    return {"status": r.status, "waktu": r.waktu, "ke": r.ke, "nama": r.nama,
            "nominal": r.nominal}


def receipt_from_dict(d: Optional[Dict[str, Any]]) -> Optional[TransferReceipt]:
    if not d:
        return None
    nominal = d.get("nominal")
    if nominal is not None and (isinstance(nominal, bool) or not isinstance(nominal, int)):
        raise ValueError("nominal bukti tidak valid")
    return TransferReceipt(status=str(d.get("status") or "-"), waktu=str(d.get("waktu") or "-"),
                           ke=str(d.get("ke") or "-"), nama=str(d.get("nama") or "-"),
                           nominal=nominal)


def parse_days(raw: Any) -> Tuple[date, ...]:
    """['2026-10-19', ...] -> tuple tanggal terurut. ValueError jika ada yang salah."""
    return tuple(sorted(date.fromisoformat(str(x)) for x in (raw or [])))
