"""Tes seleksi berkas Tesseract untuk build exe (tanpa Tesseract asli)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import tesseract_bundle as tb  # noqa: E402


def _touch(root: Path, *names: str) -> None:
    for n in names:
        p = root / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")


class SelectTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _imports(self, graph):
        return lambda path: graph.get(path.name.lower(), [])

    def test_hanya_yang_diimpor_berantai(self):
        _touch(self.root, "tesseract.exe", "libtesseract.dll", "libleptonica.dll", "libpng.dll",
               "libcurl.dll", "uninstall.exe", "tessdata/eng.traineddata",
               "tessdata/osd.traineddata", "tessdata/configs/hocr", "doc/readme.txt")
        graph = {"tesseract.exe": ["KERNEL32.dll", "libtesseract.dll"],
                 "libtesseract.dll": ["LIBLEPTONICA.DLL"],
                 "libleptonica.dll": ["libpng.dll", "msvcrt.dll"]}
        sel = tb.select(self.root, ["eng"], self._imports(graph))
        used = {p.as_posix() for p in sel.used}
        self.assertEqual(used, {"tesseract.exe", "libtesseract.dll", "libleptonica.dll",
                                "libpng.dll", "tessdata/eng.traineddata"})
        self.assertIn("libcurl.dll", {p.as_posix() for p in sel.skipped})
        self.assertIn("tessdata/osd.traineddata", {p.as_posix() for p in sel.skipped})

    def test_datas_per_berkas_menjaga_struktur_folder(self):
        _touch(self.root, "tesseract.exe", "x.dll", "tessdata/eng.traineddata")
        sel = tb.select(self.root, ["eng"], self._imports({}))
        dests = {Path(src).name: dst for src, dst in tb.datas_for(sel, "tesseract")}
        self.assertEqual(dests["tesseract.exe"], "tesseract")
        self.assertEqual(dests["eng.traineddata"], "tesseract/tessdata")
        self.assertNotIn("x.dll", dests)

    def test_semua_terpakai_bundel_seluruh_folder(self):
        _touch(self.root, "tesseract.exe", "a.dll", "tessdata/eng.traineddata")
        sel = tb.select(self.root, ["eng"], self._imports({"tesseract.exe": ["a.dll"]}))
        self.assertEqual(sel.skipped, ())
        self.assertEqual(tb.datas_for(sel, "tesseract"), [(str(self.root), "tesseract")])

    def test_bahasa_hilang_ditolak(self):
        _touch(self.root, "tesseract.exe")
        with self.assertRaises(FileNotFoundError):
            tb.select(self.root, ["eng"], self._imports({}))

    def test_bahasa_mengikuti_engine(self):
        self.assertEqual(tb.engine_langs(), ("eng",))


if __name__ == "__main__":
    unittest.main()
