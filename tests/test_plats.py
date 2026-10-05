"""Recorded Plats in a plat group folder: made-up file names, and made-up images for the drawing."""
import io
import tempfile
import unittest
from pathlib import Path

from surveysleuth.app import plat_file
from surveysleuth.plats import PlatAreas, draw_plat, plat_images, recorded_plats

try:
    from PIL import Image  # ingestion only: these tests skip without Pillow
except ImportError:
    Image = None


def names(*files):
    return [Path("Sample Plats Group 9") / f for f in files]


class RecordedPlats(unittest.TestCase):
    def test_each_file_is_a_recorded_plat_known_by_its_volume_and_page(self):
        plats, copies, skipped = recorded_plats(names("Volume 7/7_12.tif", "Volume 7/7_12.1.tif", "Volume 31A/31A_5.tif"))
        self.assertEqual(plats, {"7_12": (names("Volume 7/7_12.tif")[0], 0),
                                 "7_12.1": (names("Volume 7/7_12.1.tif")[0], 0),
                                 "31A_5": (names("Volume 31A/31A_5.tif")[0], 0)})
        self.assertEqual((copies, skipped), ([], []))

    def test_an_a_map_is_its_own_plat_beside_the_plain_map_of_that_page(self):
        files = names("Volume 7/7_16.tif", "Volume 7/7_16-A.tif", "Volume 7/7_17A.tif")
        plats, _, _ = recorded_plats(files)
        self.assertEqual(plats, {"7_16": (files[0], 0), "7_16A": (files[1], 0), "7_17A": (files[2], 0)})

    def test_a_file_named_for_two_or_three_map_numbers_holds_them_in_page_order(self):
        files = names("Volume 7/7_20, 7_21.tif", "Volume 7/7_30_31.tif", "Volume 7/7_40-41-42.tif",
                      "Volume 7/7_50-1999012345.tif")
        plats, _, _ = recorded_plats(files)
        self.assertEqual(plats, {"7_20": (files[0], 0), "7_21": (files[0], 1), "7_30": (files[1], 0), "7_31": (files[1], 1),
                                 "7_40": (files[2], 0), "7_41": (files[2], 1), "7_42": (files[2], 2), "7_50": (files[3], 0)})

    def test_only_the_next_page_counts_as_a_second_map_and_a_longer_number_is_not_a_volume(self):
        files = names("Volume 7/7_60-1.tif", "Volume 7/7_62-2004.tif", "Volume 7/1999012345-7_64.tif")
        plats, _, _ = recorded_plats(files)
        self.assertEqual(plats, {"7_60": (files[0], 0), "7_62": (files[1], 0), "7_64": (files[2], 0)})

    def test_the_plain_tiff_wins_and_the_other_files_of_its_volume_and_page_are_extra_copies(self):
        files = names("Volume 7/7_12 - 1999012345.tif", "Volume 7/Rotation of 7_12.tif", "Volume 7/7_12.pdf",
                      "Volume 7/7-12 - 1999012346.tif", "Volume 7/7_12.tif")
        plats, copies, skipped = recorded_plats(files)
        self.assertEqual(plats, {"7_12": (files[4], 0)})
        self.assertEqual((sorted(copies), skipped), (sorted(files[:4]), []))

    def test_a_copy_is_the_plat_when_no_plain_tiff_has_its_volume_and_page(self):
        files = names("Volume 7/7_13 - 1999012399.tif", "Volume 7/7_14.pdf", "Volume 7/7_14 - Sample.pdf",
                      "Volume 7/Sample Replat - 7_15.pdf")
        plats, copies, _ = recorded_plats(files)
        self.assertEqual(plats, {"7_13": (files[0], 0), "7_14": (files[1], 0), "7_15": (files[3], 0)})
        self.assertEqual(copies, [files[2]])

    def test_a_file_that_is_not_a_plat_image_or_pdf_is_skipped(self):
        files = names("Volume 7/Thumbs.db", "Volume 7/7_12.tif~RF12ab.TMP", "Volume 7/notes.txt")
        self.assertEqual(recorded_plats(files), ({}, [], files))


def lots(subdivision, numbers, at, town="SANDPORT", block="1", step=0.0003):
    """Made-up GCAD parcels: these lots of a subdivision side by side, going east from at (lat, lon), 30 m apart."""
    out = []
    for i, n in enumerate(numbers):
        lat, lon = at[0], at[1] + i * step
        south, west, north, east = lat - 0.0001, lon - 0.0001, lat + 0.0001, lon + 0.0001
        ring = [[south, west], [north, west], [north, east], [south, east], [south, west]]
        out.append({"id": f"{subdivision[:4].upper()}-{block}-{n}-{lat:.4f}", "situs": f"{n} OCEAN DR {town}, TX 77000",
                    "legal": f"ABST 1 SAMPLE SUR LOT {n} BLK {block} {subdivision}", "acres": 0.2, "centre": [lat, lon],
                    "shape": [ring], "bbox": [south, west, north, east]})
    return out


def plat(**fields):
    """A made-up Recorded Plat reading: Sample Shores Section 2, 10 lots, in Sandport, unless fields say otherwise."""
    return {"kind": "subdivision plat", "name": "Sample Shores", "section": "Section 2", "replat_of": None, "lots": [],
            "block": None, "lot_count": 10, "town": "Sandport", "date": "1999-01-02", "sheet": None, **fields}


def ids(parcels):
    return sorted(p["id"] for p in parcels)


class PlatPlacing(unittest.TestCase):
    def test_a_plat_goes_on_the_gcad_parcels_naming_its_subdivision_and_section_in_its_town(self):
        sec2 = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        others = (lots("SAMPLE SHORES SEC 1", range(1, 11), (29.31, -94.80))
                  + lots("SAMPLE SHORES SEC 2", range(1, 11), (29.40, -94.90), town="GULLHAVEN"))
        area, how = PlatAreas(sec2 + others).place(plat())
        self.assertEqual(ids(area), ids(sec2))
        self.assertTrue(how.startswith("on the parcels naming it"), how)

    def test_a_plat_never_takes_the_lots_of_a_longer_name_in_another_gcad_subdivision(self):
        shores = lots("SAMPLE SHORES", range(1, 11), (29.30, -94.80))  # GCAD subdivision SAMP, beside WEST
        west = lots("WEST SAMPLE SHORES ADDN", range(1, 4), (29.3005, -94.80))
        reserve = lots("SAMPLE SHORES", ["A"], (29.2995, -94.80))
        reserve[0].update(id="RESV-0", legal="ABST 1 SAMPLE SUR RES A SAMPLE SHORES")  # its own subdivision number
        area, _ = PlatAreas(shores + west + reserve).place(plat(section=None))
        self.assertEqual(ids(area), ids(shores + reserve))

    def test_the_town_filter_works_for_a_town_named_texas_city(self):
        here = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80), town="TEXAS CITY")
        there = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.40, -94.90))
        self.assertEqual(ids(PlatAreas(here + there).place(plat(town="Texas City"))[0]), ids(here))

    def test_a_sheet_that_is_not_a_subdivision_plat_is_never_placed(self):
        parcels = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        self.assertEqual(PlatAreas(parcels).place(plat(kind="other")), ([], "not a subdivision plat"))

    def test_a_plat_whose_name_gcad_never_gives_is_not_placed(self):
        parcels = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        self.assertEqual(PlatAreas(parcels).place(plat(name="Gull Point")), ([], "GCAD names no parcel"))

    def test_a_plat_whose_name_two_places_carry_is_not_placed(self):
        here = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        there = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.305, -94.80))  # 550 m north: the same lots again
        self.assertEqual(PlatAreas(here + there).place(plat(town=None)), ([], "two places carry its name"))

    def test_a_plat_is_not_placed_when_its_area_holds_far_more_or_far_fewer_lots_than_it_lays_out(self):
        areas = PlatAreas(lots("SAMPLE SHORES SEC 2", range(1, 31), (29.30, -94.80), step=0.0001))
        placed = [bool(areas.place(plat(lot_count=n))[0]) for n in (16, 17, 90, 91)]
        self.assertEqual(placed, [False, True, True, False])  # 30 lots: placed for a plat of 17 to 90 lots
        self.assertEqual(areas.place(plat(lot_count=91))[1], "lot count far off: its area holds 30 lots, the plat lays out 91")
        self.assertEqual(areas.place(plat(lot_count=None)), ([], "lot count not read"))

    def test_a_plat_whose_area_is_over_2_km_across_is_not_placed(self):
        spread = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80), step=0.003)  # 10 lots 290 m apart
        self.assertEqual(PlatAreas(spread).place(plat()), ([], "too wide: 10 parcels, 2.6 km"))

    def test_a_section_gcad_does_not_use_falls_back_to_the_plain_name_only_when_gcad_gives_that_name_no_sections(self):
        point = lots("GULL POINT", range(1, 11), (29.30, -94.80))
        shores = lots("SAMPLE SHORES SEC 1", range(1, 11), (29.32, -94.80)) + lots("SAMPLE SHORES", range(1, 11), (29.33, -94.80))
        areas = PlatAreas(point + shores)
        self.assertEqual(ids(areas.place(plat(name="Gull Point", section="Section One"))[0]), ids(point))
        self.assertEqual(areas.place(plat(section="Section 3")), ([], "GCAD names no parcel"))  # its Sec 1 exists
        self.assertEqual(ids(areas.place(plat(section=None))[0]), ids(shores[10:]))  # never the parcels of a section
        later = lots("GULL POINT REPLAT OF GULL POINT SEC 2", ["5"], (29.34, -94.80))  # its section named second
        self.assertEqual(PlatAreas(point + later).place(plat(name="Gull Point", section="Section One")),
                         ([], "GCAD names no parcel"))

    def test_a_replat_of_some_lots_goes_only_on_those_lots_never_on_its_whole_subdivision(self):
        sec2 = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        area, how = PlatAreas(sec2).place(plat(kind="replat", lots=["Lot 4", "5"], lot_count=2))
        self.assertEqual(ids(area), ids(sec2[3:5]))
        self.assertTrue(how.startswith("on the lots it replats: 2 lots"), how)

    def test_a_replat_of_a_reserve_goes_on_that_reserve_only(self):
        reserves = lots("SAMPLE SHORES SEC 2", ["A", "B"], (29.30, -94.80))
        for p, legal in zip(reserves, ("ABST 1 RES A (1-0) SAMPLE SHORES SEC 2", "ABST 1 RES TRACT 2 SAMPLE SHORES SEC 2")):
            p["legal"] = legal
        replat = plat(kind="replat", lots=["Reserve A"], lot_count=1)
        self.assertEqual(ids(PlatAreas(reserves).place(replat)[0]), ids(reserves[:1]))

    def test_a_replat_that_splits_one_lot_into_five_goes_on_that_lot(self):
        sec2 = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        split = plat(kind="replat", replat_of="Sample Shores, Section Two", lots=["7"], lot_count=5)
        self.assertEqual(ids(PlatAreas(sec2).place(split)[0]), ids(sec2[6:7]))

    def test_a_replat_with_a_new_name_goes_on_its_new_name_and_never_on_the_earlier_subdivisions_lots(self):
        sec2 = lots("SAMPLE SHORES SEC 2", range(1, 11), (29.30, -94.80))
        cove = lots("GULL COVE", range(1, 4), (29.31, -94.80))
        replat = plat(kind="replat", name="Gull Cove", section=None, replat_of="Sample Shores Section 2", lots=["1", "2", "3"],
                      lot_count=3)
        self.assertEqual(ids(PlatAreas(sec2 + cove).place(replat)[0]), ids(cove))
        self.assertEqual(PlatAreas(sec2).place(replat), ([], "GCAD holds none of the lots it replats"))
        bigger = cove + lots("GULL COVE", range(4, 13), (29.31, -94.7991))  # GCAD's Gull Cove is 12 lots: just its 3
        self.assertEqual(ids(PlatAreas(sec2 + bigger).place(replat)[0]), ids(cove))


class PlatRoute(unittest.TestCase):
    def test_the_app_serves_the_page_image_of_a_plat_in_the_index_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as folder:
            index_dir = Path(folder)
            (index_dir / "pages" / "plats").mkdir(parents=True)
            (index_dir / "pages" / "plats" / "7_12.png").write_bytes(b"made up")
            (index_dir / "secret.json").write_bytes(b"{}")
            index = {"plats": {"7_12": {"image": "pages/plats/7_12.png"}, "7_13": {"image": None},
                               "7_14": {"image": "secret.json"}}}
            served = [plat_file(index, index_dir, {"id": i}) for i in ("7_12", "7_13", "7_99", "../secret")]
            self.assertEqual(served, [(index_dir / "pages" / "plats" / "7_12.png").resolve(), None, None, None])
            self.assertIsNone(plat_file(index, index_dir, {"id": "7_14"}))  # only page images under pages/plats/


@unittest.skipUnless(Image, "Pillow is not installed")
class PlatPages(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)

    def scan(self, *pages):
        """A made-up TIFF scan with these pages: (width, height, grey level)."""
        path = self.dir / "7_12.tif"
        frames = [Image.new("L", (w, h), grey) for w, h, grey in pages]
        frames[0].save(path, save_all=True, append_images=frames[1:])
        return path

    def test_a_plat_page_is_drawn_black_and_white_at_most_3200_px_on_its_long_side(self):
        out = self.dir / "pages" / "7_12.png"
        draw_plat(self.scan((4000, 1000, 255)), 0, out)
        with Image.open(out) as im:
            self.assertEqual((im.size, im.mode), ((3200, 800), "1"))

    def test_a_negative_scan_white_lines_on_black_is_turned_positive(self):
        out = self.dir / "7_12.png"
        draw_plat(self.scan((400, 300, 10)), 0, out)
        with Image.open(out) as im:
            self.assertEqual(im.convert("L").getextrema(), (255, 255))  # all white

    def test_the_named_page_of_a_file_is_drawn_and_a_one_page_file_named_for_two_maps_gives_its_one_page(self):
        two_pages = self.scan((100, 50, 255), (60, 120, 255))
        draw_plat(two_pages, 1, self.dir / "second.png")
        draw_plat(self.scan((80, 40, 255)), 1, self.dir / "only.png")
        with Image.open(self.dir / "second.png") as second, Image.open(self.dir / "only.png") as only:
            self.assertEqual((second.size, only.size), ((60, 120), (80, 40)))

    def test_a_plat_is_read_from_the_whole_sheet_at_1024_px_and_its_close_ups_at_up_to_4200_px_a_negative_turned_positive(self):
        sent = [Image.open(io.BytesIO(png)) for png in plat_images(self.scan((100, 50, 255), (8400, 2000, 10)), 1)]
        self.assertEqual([im.size for im in sent], [(1024, 244), (1500, 1000), (1600, 1000), (1500, 1000)])
        self.assertEqual({im.getextrema() for im in sent}, {(245, 245)})  # dark grey 10 turned to light grey 245

    def test_a_page_already_drawn_since_the_scan_changed_is_kept(self):
        scan, out = self.scan((100, 50, 255)), self.dir / "7_12.png"
        draw_plat(scan, 0, out)
        out.write_bytes(b"kept")
        draw_plat(scan, 0, out)
        self.assertEqual(out.read_bytes(), b"kept")


if __name__ == "__main__":
    unittest.main()
