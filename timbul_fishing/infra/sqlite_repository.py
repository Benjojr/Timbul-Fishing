"""Penyimpanan rekap harian di SQLite. Satu koneksi pendek per operasi (aman dipakai UI).

Bukti transfer disimpan terpisah dari hari (tabel `settlement`) dan dihubungkan ke satu atau
beberapa hari lewat `settlement_day`, sehingga satu bukti bisa membayar beberapa hari sekaligus.
"""
from __future__ import annotations

import calendar
import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from timbul_fishing.core.errors import ReceiptConflictError
from timbul_fishing.domain.daily_record import DailyRecord
from timbul_fishing.domain.daily_report import DailyInput, ExpenseItem, SessionEntry
from timbul_fishing.domain.receipt import TransferReceipt

_SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_record (
    tanggal      TEXT PRIMARY KEY,           -- YYYY-MM-DD
    peserta1 INTEGER NOT NULL, harga1 INTEGER NOT NULL,
    peserta2 INTEGER NOT NULL, harga2 INTEGER NOT NULL,
    peserta3 INTEGER NOT NULL, harga3 INTEGER NOT NULL,
    hadiah       INTEGER NOT NULL,
    pengeluaran  INTEGER NOT NULL,
    catatan      TEXT NOT NULL DEFAULT '',
    has_receipt  INTEGER NOT NULL DEFAULT 0, -- kolom lama; bukti kini di tabel settlement
    r_status TEXT, r_waktu TEXT, r_ke TEXT, r_nama TEXT, r_nominal INTEGER
);
CREATE TABLE IF NOT EXISTS expense_item (
    tanggal    TEXT NOT NULL,                -- YYYY-MM-DD
    urutan     INTEGER NOT NULL,
    keperluan  TEXT NOT NULL,
    nominal    INTEGER NOT NULL,
    PRIMARY KEY (tanggal, urutan)
);
CREATE TABLE IF NOT EXISTS settlement (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE,                 -- NULL jika waktu/nominal tidak terbaca
    status TEXT, waktu TEXT, ke TEXT, nama TEXT, nominal INTEGER
);
CREATE TABLE IF NOT EXISTS settlement_day (
    tanggal       TEXT PRIMARY KEY,          -- satu hari hanya punya satu bukti
    settlement_id INTEGER NOT NULL
);
"""

APP_ID = 0x54465244   # "TFRD": penanda bahwa ini file data Timbul Fishing

_DATA_COLS = ("tanggal, peserta1, harga1, peserta2, harga2, peserta3, harga3, "
              "hadiah, pengeluaran, catatan")


def _fmt(d: date) -> str:
    return d.isoformat()


class SqliteDailyRecordRepository:
    def __init__(self, db_path) -> None:
        self._path = str(db_path)
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as con, con:
            self._check_identity(con)
            con.executescript(_SCHEMA)
            self._migrate_legacy_receipts(con)
            self._migrate_catatan(con)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self._path)
        con.row_factory = sqlite3.Row
        return con

    @staticmethod
    def _check_identity(con: sqlite3.Connection) -> None:
        """File baru/lama diberi cap aplikasi; file milik program lain ditolak."""
        current = con.execute("PRAGMA application_id").fetchone()[0]
        if current == 0:
            con.execute(f"PRAGMA application_id = {APP_ID}")
        elif current != APP_ID:
            raise ValueError("Bukan file data Timbul Fishing.")

    @staticmethod
    def _migrate_catatan(con: sqlite3.Connection) -> None:
        """Database lama belum punya kolom catatan; tambahkan tanpa mengubah data."""
        cols = {r["name"] for r in con.execute("PRAGMA table_info(daily_record)")}
        if "catatan" not in cols:
            con.execute("ALTER TABLE daily_record ADD COLUMN catatan TEXT NOT NULL DEFAULT ''")

    # ---------- migrasi bukti lama (satu bukti per hari) ----------
    def _migrate_legacy_receipts(self, con: sqlite3.Connection) -> None:
        rows = con.execute(
            "SELECT tanggal, r_status, r_waktu, r_ke, r_nama, r_nominal "
            "FROM daily_record WHERE has_receipt = 1 ORDER BY tanggal"
        ).fetchall()
        for row in rows:
            receipt = TransferReceipt(
                status=row["r_status"] or "-", waktu=row["r_waktu"] or "-",
                ke=row["r_ke"] or "-", nama=row["r_nama"] or "-", nominal=row["r_nominal"],
            )
            if con.execute("SELECT 1 FROM settlement_day WHERE tanggal = ?",
                           (row["tanggal"],)).fetchone() is None:
                sid = self._upsert_settlement(con, receipt)
                con.execute("INSERT OR REPLACE INTO settlement_day VALUES (?, ?)",
                            (row["tanggal"], sid))
            con.execute("UPDATE daily_record SET has_receipt = 0, r_status = NULL, r_waktu = NULL, "
                        "r_ke = NULL, r_nama = NULL, r_nominal = NULL WHERE tanggal = ?",
                        (row["tanggal"],))

    # ---------- tulis: data harian ----------
    def save(self, record: DailyRecord) -> None:
        """Simpan isian harian saja. Bukti dihubungkan lewat `link_receipt`."""
        d = record.data
        values = [_fmt(d.tanggal)]
        for s in d.sesi:
            values += [s.peserta, s.harga]
        # Kolom `pengeluaran` selalu berisi total, jadi data lama & laporan tetap konsisten.
        total = sum(i.nominal for i in d.rincian) if d.rincian else d.pengeluaran
        values += [d.hadiah, total, d.catatan.strip()]
        with closing(self._connect()) as con, con:
            con.execute(
                f"INSERT OR REPLACE INTO daily_record ({_DATA_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?)",
                values,
            )
            con.execute("DELETE FROM expense_item WHERE tanggal = ?", (_fmt(d.tanggal),))
            con.executemany(
                "INSERT INTO expense_item VALUES (?,?,?,?)",
                [(_fmt(d.tanggal), n, item.keperluan, item.nominal)
                 for n, item in enumerate(d.rincian)],
            )

    def delete(self, tanggal: date) -> None:
        with closing(self._connect()) as con, con:
            self._unlink(con, _fmt(tanggal))
            con.execute("DELETE FROM expense_item WHERE tanggal = ?", (_fmt(tanggal),))
            con.execute("DELETE FROM daily_record WHERE tanggal = ?", (_fmt(tanggal),))

    # ---------- tulis: bukti ----------
    def link_receipt(self, receipt: TransferReceipt, days: Sequence[date],
                     replace: bool = False) -> None:
        """
        Hubungkan satu bukti ke satu atau beberapa hari (semua hari harus sudah tersimpan).

        - Bukti yang sama (waktu+rekening+nominal) yang sudah dipakai untuk hari LAIN ditolak.
        - Hari yang sudah punya bukti lain ditolak, kecuali replace=True (bukti lama dilepas).
        """
        keys = sorted({_fmt(d) for d in days})
        if not keys:
            return
        with closing(self._connect()) as con, con:
            missing = [k for k in keys if con.execute(
                "SELECT 1 FROM daily_record WHERE tanggal = ?", (k,)).fetchone() is None]
            if missing:
                raise ReceiptConflictError("Hari belum tersimpan: " + ", ".join(missing))

            fp = receipt.fingerprint
            if fp is not None:
                row = con.execute("SELECT id FROM settlement WHERE fingerprint = ?",
                                  (fp,)).fetchone()
                if row is not None:
                    used = self._days_of(con, row["id"])
                    foreign = [u for u in used if u not in keys]
                    if foreign:
                        raise ReceiptConflictError(
                            "Bukti ini sudah dipakai untuk hari lain.",
                            [date.fromisoformat(u) for u in foreign])

            for k in keys:
                cur = con.execute("SELECT settlement_id FROM settlement_day WHERE tanggal = ?",
                                  (k,)).fetchone()
                if cur is None:
                    continue
                same = fp is not None and con.execute(
                    "SELECT 1 FROM settlement WHERE id = ? AND fingerprint = ?",
                    (cur["settlement_id"], fp)).fetchone() is not None
                if same:
                    continue
                if not replace:
                    raise ReceiptConflictError(
                        f"Tanggal {k} sudah punya bukti transfer lain.", [date.fromisoformat(k)])
                self._unlink(con, k)

            sid = self._upsert_settlement(con, receipt)
            for k in keys:
                con.execute("INSERT OR REPLACE INTO settlement_day VALUES (?, ?)", (k, sid))

    def unlink_receipt(self, tanggal: date) -> None:
        """Lepas bukti dari satu hari (hari lain dalam gabungan tetap terhubung)."""
        with closing(self._connect()) as con, con:
            self._unlink(con, _fmt(tanggal))

    @staticmethod
    def _upsert_settlement(con: sqlite3.Connection, r: TransferReceipt) -> int:
        fp = r.fingerprint
        if fp is not None:
            row = con.execute("SELECT id FROM settlement WHERE fingerprint = ?", (fp,)).fetchone()
            if row is not None:
                return row["id"]
        cur = con.execute(
            "INSERT INTO settlement (fingerprint, status, waktu, ke, nama, nominal) "
            "VALUES (?,?,?,?,?,?)", (fp, r.status, r.waktu, r.ke, r.nama, r.nominal))
        return int(cur.lastrowid)

    @staticmethod
    def _days_of(con: sqlite3.Connection, settlement_id: int) -> List[str]:
        return [r["tanggal"] for r in con.execute(
            "SELECT tanggal FROM settlement_day WHERE settlement_id = ? ORDER BY tanggal",
            (settlement_id,))]

    @staticmethod
    def _unlink(con: sqlite3.Connection, key: str) -> None:
        row = con.execute("SELECT settlement_id FROM settlement_day WHERE tanggal = ?",
                          (key,)).fetchone()
        if row is None:
            return
        con.execute("DELETE FROM settlement_day WHERE tanggal = ?", (key,))
        left = con.execute("SELECT 1 FROM settlement_day WHERE settlement_id = ?",
                           (row["settlement_id"],)).fetchone()
        if left is None:  # bukti yatim: buang agar bisa dipakai lagi
            con.execute("DELETE FROM settlement WHERE id = ?", (row["settlement_id"],))

    # ---------- baca ----------
    def get(self, tanggal: date) -> Optional[DailyRecord]:
        with closing(self._connect()) as con:
            row = con.execute(
                "SELECT * FROM daily_record WHERE tanggal = ?", (_fmt(tanggal),)
            ).fetchone()
            return self._to_record(con, row) if row else None

    def list_month(self, year: int, month: int) -> List[DailyRecord]:
        first = date(year, month, 1)
        last = date(year, month, calendar.monthrange(year, month)[1])
        return self._list_between(first, last)

    def list_unsettled(self, since: Optional[date] = None,
                       until: Optional[date] = None) -> List[DailyRecord]:
        """Hari tersimpan yang belum terhubung ke bukti mana pun, urut tanggal naik."""
        sql = ("SELECT * FROM daily_record WHERE tanggal NOT IN "
               "(SELECT tanggal FROM settlement_day)")
        args: list = []
        if since is not None:
            sql += " AND tanggal >= ?"
            args.append(_fmt(since))
        if until is not None:
            sql += " AND tanggal <= ?"
            args.append(_fmt(until))
        with closing(self._connect()) as con:
            rows = con.execute(sql + " ORDER BY tanggal", args).fetchall()
            return [self._to_record(con, r) for r in rows]

    def days_for_receipt(self, receipt: TransferReceipt) -> Tuple[date, ...]:
        """Hari-hari yang sudah memakai bukti ini (kosong jika belum pernah dipakai)."""
        fp = receipt.fingerprint
        if fp is None:
            return ()
        with closing(self._connect()) as con:
            row = con.execute("SELECT id FROM settlement WHERE fingerprint = ?", (fp,)).fetchone()
            if row is None:
                return ()
            return tuple(date.fromisoformat(u) for u in self._days_of(con, row["id"]))

    def _list_between(self, first: date, last: date) -> List[DailyRecord]:
        with closing(self._connect()) as con:
            rows = con.execute(
                "SELECT * FROM daily_record WHERE tanggal BETWEEN ? AND ? ORDER BY tanggal",
                (_fmt(first), _fmt(last)),
            ).fetchall()
            return [self._to_record(con, r) for r in rows]

    def _to_record(self, con: sqlite3.Connection, row: sqlite3.Row) -> DailyRecord:
        items = tuple(
            ExpenseItem(keperluan=r["keperluan"], nominal=r["nominal"])
            for r in con.execute(
                "SELECT keperluan, nominal FROM expense_item WHERE tanggal = ? ORDER BY urutan",
                (row["tanggal"],))
        )
        data = DailyInput(
            tanggal=date.fromisoformat(row["tanggal"]),
            sesi=tuple(  # type: ignore[arg-type]
                SessionEntry(row[f"peserta{i}"], row[f"harga{i}"]) for i in (1, 2, 3)
            ),
            hadiah=row["hadiah"],
            pengeluaran=sum(i.nominal for i in items) if items else row["pengeluaran"],
            rincian=items,
            catatan=row["catatan"] or "",
        )
        link = con.execute(
            "SELECT s.* FROM settlement s JOIN settlement_day d ON d.settlement_id = s.id "
            "WHERE d.tanggal = ?", (row["tanggal"],)).fetchone()
        if link is None:
            return DailyRecord(data=data)
        receipt = TransferReceipt(
            status=link["status"] or "-", waktu=link["waktu"] or "-", ke=link["ke"] or "-",
            nama=link["nama"] or "-", nominal=link["nominal"],
        )
        cover = tuple(date.fromisoformat(u) for u in self._days_of(con, link["id"]))
        return DailyRecord(data=data, receipt=receipt, cover=cover)
