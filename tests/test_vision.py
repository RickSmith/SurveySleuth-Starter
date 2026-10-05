"""Tests for the vision module's pure parts, on made-up pixels and answers. No Firm data, Poppler or Ollama."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from surveysleuth.vision import Answers, drawing_facts, survey_record, tiles, upright


class DrawingImages(unittest.TestCase):
    def test_the_sheet_is_cut_into_parts_of_at_most_1400_px_each_widened_100_px_into_its_neighbors(self):
        w, h = 3000, 1500
        px = bytes((x + 7 * y) % 256 for y in range(h) for x in range(w))
        cut = tiles(w, h, px)
        self.assertEqual([(tw, th) for tw, th, _ in cut], [(1100, 850), (1200, 850), (1100, 850),
                                                          (1100, 850), (1200, 850), (1100, 850)])
        tw, th, middle = cut[4]  # second row, second column: starts 100 px into the first part's corner
        self.assertEqual(middle[:3], px[650 * w + 900:650 * w + 903])
        self.assertEqual(middle[-1], px[(1500 - 1) * w + 2100 - 1])
        self.assertEqual([t[:2] for t in tiles(w, h, px, lap=0)], [(1000, 750)] * 6)  # the title-block reading's tiles

    def test_a_sideways_scan_is_turned_a_quarter_clockwise(self):
        self.assertEqual(upright(3, 2, bytes([1, 2, 3,
                                              4, 5, 6])), (2, 3, bytes([4, 1,
                                                                        5, 2,
                                                                        6, 3])))


class DrawingFacts(unittest.TestCase):
    def test_buildings_easements_and_setback_lines_are_kept_once_each_and_corner_marks_never(self):
        out = {"corner_marks": [{"label": "Fnd. Rod", "status": "found"}], "buildings": ["Frame House", " Shed ", "Shed"],
               "easements": ["7.5' U.E.", ""], "setback_lines": []}
        self.assertEqual([(f["label"], f["value"], f["page"]) for f in drawing_facts(out)], [
            ("Building", "Frame House", 1), ("Building", "Shed", 1), ("Easement", "7.5' U.E.", 1)])
        self.assertNotIn("Rod", repr(drawing_facts(out)))

    def test_a_house_number_the_model_copied_is_left_out_unless_it_is_the_whole_label(self):
        out = {"buildings": ["No. 12 Beach House", "no 34A Garage", "No. 56"], "easements": [], "setback_lines": []}
        self.assertEqual([f["value"] for f in drawing_facts(out)], ["Beach House", "Garage", "No. 56"])


def survey_answer(**citation):
    """A made-up Survey title block answer, with the plat citation fields given."""
    return {"record_kind": "survey plat or replat", "job_no": "07-0001", "survey_date": "2007-05-01",
            "file_no": "1234-0001-0001-000", "lots": ["1"], "block": "1", "subdivision": "Sample Shores",
            "flood_note": None, "street": None, "plat_citation": None, "plat_volume": None, "plat_page": None, **citation}


def plat_facts(answer):
    return [f["value"] for f in survey_record("SUR_GAL_Data/07-0001.pdf", answer)["facts"] if f["label"] == "Recorded Plat"]


class PlatCitation(unittest.TestCase):
    def test_the_plat_a_survey_cites_is_a_fact_with_its_volume_and_page(self):
        answer = survey_answer(plat_citation="Volume 7, Page 12, of the Map Records of Galveston County, Texas",
                               plat_volume="7", plat_page="12")
        self.assertEqual(plat_facts(answer), ["Volume 7, Page 12"])

    def test_a_plat_cited_in_the_office_of_the_county_clerk_is_still_a_plat_facts(self):
        answer = survey_answer(plat_citation="Volume 7, Page 12, in the Office of the County Clerk of Galveston County",
                               plat_volume="7", plat_page="12")
        self.assertEqual(plat_facts(answer), ["Volume 7, Page 12"])

    def test_a_second_map_on_a_page_keeps_its_decimal(self):
        answer = survey_answer(plat_citation="Volume 7, Page 30.1, Map Records", plat_volume="7", plat_page="30.1")
        self.assertEqual(plat_facts(answer), ["Volume 7, Page 30.1"])

    def test_a_deed_or_clerks_file_citation_is_not_a_plat_facts(self):
        deed = survey_answer(plat_citation="Volume 1234, Page 567 of the Deed Records of Galveston County",
                             plat_volume="1234", plat_page="567")
        clerk = survey_answer(plat_citation="Clerk's File No. 2007012345", plat_volume="2007012345", plat_page="1")
        self.assertEqual((plat_facts(deed), plat_facts(clerk)), ([], []))

    def test_a_citation_in_any_wording_of_another_county_keeps_that_county(self):
        def county(citation):
            return plat_facts(survey_answer(plat_citation=citation, plat_volume="8", plat_page="3"))
        self.assertEqual([county("Volume 8, Page 3, Map Records of the County of Sample"),
                          county("Volume 8, Page 3, Sample Co. Map Records"),
                          county("Volume 8, Page 3, Map Records County of Galveston")],
                         [["Volume 8, Page 3, Sample County"], ["Volume 8, Page 3, Sample County"], ["Volume 8, Page 3"]])

    def test_a_volume_with_a_space_and_a_plat_on_several_pages_give_the_volume_and_its_first_page(self):
        spaced = survey_answer(plat_citation="Volume 31 A, Page 5, Map Records", plat_volume="31 A", plat_page="5")
        pages = survey_answer(plat_citation="Volume 31-A, Pages 5, 6 & 7, Map Records", plat_volume="31-A", plat_page="5, 6 & 7")
        a_map = survey_answer(plat_citation="Volume 7, Page 16-A, Map Records", plat_volume="7", plat_page="16-A")
        self.assertEqual((plat_facts(spaced), plat_facts(pages), plat_facts(a_map)),
                         (["Volume 31A, Page 5"], ["Volume 31-A, Page 5"], ["Volume 7, Page 16-A"]))

    def test_a_volume_and_page_with_no_citation_text_is_not_a_recorded_plat(self):
        self.assertEqual(plat_facts(survey_answer(plat_volume="7", plat_page="12")), [])

    def test_another_countys_plat_is_kept_with_its_county_named(self):
        answer = survey_answer(plat_citation="Volume 8, Page 3 of the Plat Records of Sample County, Texas",
                               plat_volume="8", plat_page="3")
        self.assertEqual(plat_facts(answer), ["Volume 8, Page 3, Sample County"])


class SavedAnswers(unittest.TestCase):
    def test_each_map_of_a_file_holding_two_is_asked_once_and_a_rerun_asks_nothing(self):
        reading = {"prompt": "Read the made-up plat.", "images": lambda file, page=0: [b"page %d" % page]}
        with tempfile.TemporaryDirectory() as folder, patch("surveysleuth.vision.ask") as ask:
            ask.side_effect = lambda images, _: {"seen": images[0].decode()}
            scan, saved = Path(folder) / "7_30_31.tif", Path(folder) / "vision.jsonl"
            scan.write_bytes(b"made up")
            first = [Answers(saved).read(scan, "7_30_31.tif", reading, page) for page in (0, 1)]
            again = [Answers(saved).read(scan, "7_30_31.tif", reading, page) for page in (0, 1)]
        self.assertEqual(first, [{"seen": "page 0"}, {"seen": "page 1"}])
        self.assertEqual((again, ask.call_count), (first, 2))

    def test_a_line_cut_off_by_a_hard_stop_is_asked_again_and_the_saved_answers_are_kept(self):
        reading = {"prompt": "Read the made-up plat.", "images": lambda file: []}
        with tempfile.TemporaryDirectory() as folder, patch("surveysleuth.vision.ask", return_value={"name": "Gull Point"}) as ask:
            first, second, saved = Path(folder) / "7_12.tif", Path(folder) / "7_13.tif", Path(folder) / "vision.jsonl"
            first.write_bytes(b"made up 1")
            second.write_bytes(b"made up 2")
            Answers(saved).read(first, "7_12.tif", reading)
            Answers(saved).read(second, "7_13.tif", reading)
            saved.write_bytes(saved.read_bytes()[:-20])  # the stop cut the last answer short
            answers = Answers(saved)
            self.assertEqual([answers.read(f, f.name, reading) for f in (first, second)], [{"name": "Gull Point"}] * 2)
        self.assertEqual(ask.call_count, 3)


if __name__ == "__main__":
    unittest.main()
