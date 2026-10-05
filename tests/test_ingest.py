"""Ingestion's choice for each file in the Legacy archive folder: made-up files, fake saved answers, no Poppler."""
import tempfile
import unittest
from pathlib import Path

from surveysleuth.ingest import read


class FakeAnswers:
    """Answers every reading with a made-up Survey title block, and counts the questions put to the model."""

    def __init__(self):
        self.asked = 0

    def read(self, pdf, file, reading):
        self.asked += 1
        return {"record_kind": "survey plat or replat", "job_no": "07-0001", "survey_date": "2007-05-01",
                "file_no": "1234-0001-0001-000", "lots": ["1"], "block": "1", "subdivision": "Sample Shores",
                "flood_note": None, "buildings": [], "easements": [], "setback_lines": [], "corner_marks": []}


class KnownFolders(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.archive = Path(folder.name)
        self.answers = FakeAnswers()

    def file(self, name):
        path = self.archive / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4 made up")
        return path

    def test_a_file_in_a_folder_ingestion_does_not_know_is_skipped_without_asking_the_model(self):
        rec, why = read(self.file("Sample Folder/07-0002.pdf"), self.archive, self.answers)
        self.assertIsNone(rec)
        self.assertEqual(why, "a folder ingestion does not know: Sample Folder")
        self.assertEqual(self.answers.asked, 0)

    def test_a_file_at_the_top_of_the_archive_folder_is_skipped_without_asking_the_model(self):
        rec, why = read(self.file("07-0001.pdf"), self.archive, self.answers)
        self.assertIsNone(rec)
        self.assertEqual(why, "a file at the top of the archive folder, in no folder ingestion knows")
        self.assertEqual(self.answers.asked, 0)

    def test_a_file_in_the_survey_folder_is_still_read_as_a_survey(self):
        rec, why = read(self.file("SUR_GAL_Data/07-0001.pdf"), self.archive, self.answers)
        self.assertIsNone(why)
        self.assertEqual((rec["file"], rec["kind"]), ("SUR_GAL_Data/07-0001.pdf", "Survey"))
        self.assertEqual(self.answers.asked, 2)  # the title block, then the drawing

    def test_a_file_that_is_not_a_pdf_in_a_known_folder_is_still_skipped_as_not_a_pdf(self):
        rec, why = read(self.file("EL_GAL_Data/notes.txt"), self.archive, self.answers)
        self.assertEqual((rec, why), (None, "not a PDF"))


if __name__ == "__main__":
    unittest.main()
