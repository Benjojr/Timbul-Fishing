import tempfile
import unittest
from pathlib import Path

from bukti_tf.config import DB_NAME, LEGACY_DB_NAME, database_path


class DatabasePathTest(unittest.TestCase):
    def test_folder_kosong_memakai_nama_baru(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(database_path(Path(tmp)), Path(tmp) / DB_NAME)

    def test_file_lama_disalin_sekali_dan_dibiarkan_sebagai_cadangan(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / LEGACY_DB_NAME).write_bytes(b"data-lama")
            path = database_path(folder)
            self.assertEqual(path.read_bytes(), b"data-lama")
            self.assertTrue((folder / LEGACY_DB_NAME).exists())
            path.write_bytes(b"data-baru")          # panggilan berikutnya tidak menimpa
            self.assertEqual(database_path(folder).read_bytes(), b"data-baru")


if __name__ == "__main__":
    unittest.main()
