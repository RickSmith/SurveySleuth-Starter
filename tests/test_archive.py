"""Tests for the archive module, on made-up Records. No Firm data, Poppler, Ollama or network."""
import math
import re
import unittest

from surveysleuth.archive import build_index, nearby_search

HOME = (29.30, -94.80)  # the search point in these tests
M_PER_DEG_LAT = 111195.08  # metres in one degree of latitude on the mean Earth


def at(m):
    """The point m metres due north of HOME."""
    return HOME[0] + m / M_PER_DEG_LAT, HOME[1]


def north(m):
    """A printed A5 lat/long m metres due north of HOME."""
    lat, lon = at(m)[0], -HOME[1]

    def dms(x):
        d, rest = divmod(round(x * 3600, 4), 3600)
        m, s = divmod(rest, 60)
        return f"{int(d)}°{int(m):02d}'{s:07.4f}\""
    return f"N {dms(lat)}, W {dms(lon)}"


def own_parcel_id(m):
    return f"1000-0000-{round(m):04d}-000"


def cert(file, at_m=None, **facts):
    """A typed Elevation Certificate with the given raw Facts, all read from page 1's text layer.
    at_m: its printed lat/long lies at_m metres north of HOME, inside its own made-up GCAD parcel (see build)."""
    labels = {"latlong": "Lat/long", "zone": "Flood zone", "bfe": "BFE", "address": "Address",
              "parcel": "Parcel ID", "date": "Date", "owner": "Owner", "legal": "Lot and block", "basis": "Basis",
              "floor": "Top of bottom floor", "lag": "Lowest adjacent grade", "lsm": "Lowest structural member",
              "benchmark": "Benchmark", "ground": "Natural ground"}
    if at_m is not None:
        facts = {"latlong": north(at_m), "parcel": own_parcel_id(at_m), **facts}
    return {"file": file, "kind": "Elevation Certificate", "at_m": at_m,
            "facts": [{"label": labels[k], "value": v, "page": 1, "read_by": "text layer"} for k, v in facts.items()]}


def box(lat, lon, half):
    """A square shape (one closed ring of [lat, lon]), 2 x half metres wide, centred on lat, lon."""
    dlat, dlon = half / M_PER_DEG_LAT, half / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
    ring = [[lat - dlat, lon - dlon], [lat - dlat, lon + dlon], [lat + dlat, lon + dlon], [lat + dlat, lon - dlon]]
    return [ring + ring[:1]]


def square(pid, lat, lon, half=20, situs="", acres=0.2, legal=""):
    """A made-up square GCAD parcel, 2 x half metres wide, centred on lat, lon."""
    return {"id": pid, "situs": situs, "legal": legal, "acres": acres, "centre": [lat, lon], "shape": box(lat, lon, half)}


def parcel(pid, m, **kw):
    """A made-up square GCAD parcel centred m metres north of HOME."""
    return square(pid, *at(m), **kw)


def build(*records, parcels=(), **kw):
    """build_index, with the own GCAD parcel of every certificate made with cert(at_m=...)."""
    own = [parcel(own_parcel_id(r["at_m"]), r["at_m"]) for r in records if r.get("at_m") is not None]
    return build_index(list(records), [*parcels, *own], **kw)


class JobNumber(unittest.TestCase):
    def test_job_number_comes_from_the_file_name_with_spaces_and_suffixes(self):
        names = {"certs/07-0101 -REV.pdf": "07-0101", "certs/07-0102-12.pdf": "07-0102",
                 "certs/07-0103-T.pdf": "07-0103", "certs/07-0104 CD.pdf": "07-0104",
                 "certs/07-0105-NG.pdf": "07-0105", "certs/07-0106-rev.pdf": "07-0106",
                 "certs/07-0107cd.pdf": "07-0107"}
        index, _ = build_index([cert(f) for f in names])
        self.assertEqual({r["id"]: r["job"] for r in index["records"]}, names)

    def test_a_file_name_with_no_job_number_is_skipped_and_reported(self):
        index, report = build_index([cert("certs/Bay-Road-sketch.pdf")])
        self.assertEqual(index["records"], [])
        self.assertEqual(report["skipped"], {"no Job number in the file name": ["certs/Bay-Road-sketch.pdf"]})


class Facts(unittest.TestCase):
    def test_each_fact_keeps_its_page_how_it_was_read_and_its_check(self):
        index, _ = build_index([cert("certs/11-0001.pdf", zone="VE"), cert("certs/11-0002.pdf", zone="Q7")])
        good, bad = (r["facts"] for r in index["records"])
        self.assertEqual(good, [{"label": "Flood zone", "value": "VE", "page": 1, "read_by": "text layer", "ok": True, "note": None}])
        self.assertFalse(bad[0]["ok"])
        self.assertEqual(bad[0]["note"], "Not a FEMA zone name.")

    def test_each_certificate_fact_has_its_simple_check(self):
        cases = [  # label, a value that passes, a value that fails, the note on the failure
            ("Job number", "11-0001", "11-0002", "The file name says 11-0001."),
            ("Address", "12 Example Lane", "--", "Not an address."),
            ("Lot and block", "Lot 3, Block 2, Sample Shores", "", "No text."),
            ("Date", "23-MAR-11", "32-MAR-11", "Not a date."),
            ("Date", "27-SEPT-10", "SEPT-10", "Not a date."),
            ("Date", "03-23-2011", "23-03-2011", "Not a date."),
            ("Date", "May 3, 2011", "May 32, 2011", "Not a date."),  # a Natural Ground Letter's date
            ("BFE", "12", "120", "Not a normal BFE."),
            ("BFE", "13'", "11 ft 6 in", "Not a normal BFE."),
            ("FIRM panel", "480000 0100 F, January 1, 2000", "4800000100", "Not a FIRM panel number."),
            ("Basis", "Finished construction", "Two boxes ticked", "Could not read the C1 tick boxes."),
            ("Top of bottom floor", "9.0", "90", "Not a normal height."),
            ("Lowest structural member", "15.5", "x", "Not a normal height."),
            ("Lowest adjacent grade", "5.0", "-9", "Not a normal height."),
            ("Highest adjacent grade", "6.0", "N6.0", "Not a normal height."),
            ("Highest adjacent grade", "7.1.", "*7.0", "Not a normal height."),
            ("Benchmark", "TBM 7", "~'§,.!", "Garbled text."),
            ("Flood note", "Not in the 100-year flood plain", "Zone AE", "Not a flood note."),
            ("Natural ground", "6.2", "62", "Not a normal height."),
            ("Benchmark", "Nail in the curb at the south corner of the lot, beside the drive, at an elevation of 7.31 ft", "~'§,.!",
             "Garbled text."),
        ]
        for label, good, bad, note in cases:
            with self.subTest(label=label, bad=bad):
                rec = lambda v: {"file": "certs/11-0001.pdf", "kind": "Elevation Certificate",
                                 "facts": [{"label": label, "value": v, "page": 1, "read_by": "text layer"}]}
                index, _ = build_index([rec(good), rec(bad)])
                ok, failed = (r["facts"][0] for r in index["records"])
                self.assertEqual((ok["ok"], ok["note"]), (True, None))
                self.assertEqual((failed["ok"], failed["note"]), (False, note))

    def test_a_parcel_id_must_look_right_and_be_found_in_gcad(self):
        ids = ["1234-0001-0002-000", "1234-0003-0004-000", "1234-0001-0002", "0000-0000-0000-000", "9999-0001-0001-000"]
        index, _ = build_index([cert(f"certs/07-000{i}.pdf", parcel=v) for i, v in enumerate(ids)],
                               [parcel("1234-0001-0002-000", 100)])
        self.assertEqual([(r["facts"][0]["ok"], r["facts"][0]["note"]) for r in index["records"]], [
            (True, None),
            (False, "Not in GCAD today: retired by a replat, or misread."),
            (False, "Does not look like a Parcel ID."),
            (False, "Placeholder number, not a real parcel."),
            (False, "Placeholder number, not a real parcel.")])

    def test_the_record_date_is_its_section_d_date(self):
        index, _ = build_index([cert("certs/11-0001.pdf", date="23-MAR-11"), cert("certs/11-0002.pdf")])
        self.assertEqual([r["date"] for r in index["records"]], ["2011-03-23", None])

    def test_a_certificate_date_printed_year_first_is_read_in_its_jobs_year_and_one_far_from_it_fails(self):
        survey = {"file": "surveys/11-0004.pdf", "kind": "Survey",
                  "facts": [{"label": "Date", "value": "05-MAY-05", "page": 1, "read_by": "vision model"}]}
        index, _ = build_index([cert("certs/11-0001.pdf", date="11-JUN-27"), cert("certs/11-0002.pdf", date="02-OCT-02"),
                                cert("certs/11-0003.pdf", date="15-JUN-12"), survey])
        year_first, far, later, old_survey = index["records"]
        self.assertEqual(year_first["date"], "2011-06-27")  # 27 June 2011, not 11 June 2027
        self.assertEqual((far["date"], far["facts"][0]["note"]), (None, "Far from its Job's year, 2011."))
        self.assertEqual(later["date"], "2012-06-15")
        self.assertEqual(old_survey["date"], "2005-05-05")  # a Survey can be years older than its Job

    def test_a_natural_ground_letter_date_far_from_its_jobs_year_fails_like_a_certificates(self):
        letter = {"file": "certs/11-0005-NG.pdf", "kind": "Natural Ground Letter",
                  "facts": [{"label": "Date", "value": "May 3, 2004", "page": 1, "read_by": "vision model"}]}
        [rec] = build_index([letter])[0]["records"]
        self.assertEqual((rec["date"], rec["facts"][0]["note"]), (None, "Far from its Job's year, 2011."))

    def test_owner_names_are_never_stored(self):
        index, _ = build_index([cert("certs/11-0001.pdf", owner="Jane Q. Homeowner", zone="AE")])
        self.assertNotIn("Homeowner", repr(index))


class Locations(unittest.TestCase):
    def test_a_certificate_is_placed_at_its_printed_lat_long(self):
        index, report = build_index([cert("certs/07-0001.pdf", latlong="N 29°12'36.0\", W 94°54'18.0\"",
                                          parcel="1234-0001-0001-000")], [square("1234-0001-0001-000", 29.21, -94.905)])
        loc = index["records"][0]["location"]
        self.assertAlmostEqual(loc["lat"], 29.210000, places=6)  # 29 + 12/60 + 36/3600
        self.assertAlmostEqual(loc["lon"], -94.905000, places=6)
        self.assertEqual(loc["found_by"], "certificate lat/long, checked by Parcel ID")
        self.assertEqual(report["not_located"], [])

    def test_a_lat_long_outside_galveston_county_fails_and_the_record_is_reported(self):
        index, report = build_index([cert("certs/11-0001.pdf", latlong="N 30°10'00.0\", W 94°54'18.0\""),
                                     cert("certs/11-0002.pdf", zone="AE")])
        far, none = index["records"]
        self.assertIsNone(far["location"])
        self.assertEqual(far["facts"][0]["note"], "Not in Galveston County.")
        self.assertEqual(report["not_located"], [
            {"id": "certs/11-0001.pdf", "reason":
             "Lat/long: Not in Galveston County. No Parcel ID. No address. Its Job has no other placed Records."},
            {"id": "certs/11-0002.pdf", "reason": "No lat/long. No Parcel ID. No address. Its Job has no other placed Records."}])

    def test_a_lat_long_with_60_or_more_minutes_or_seconds_is_not_clean(self):
        index, _ = build_index([cert("certs/07-0108.pdf", latlong="N 29°12'75.0\", W 94°54'18.0\"")])
        self.assertEqual(index["records"][0]["facts"][0]["note"], "Could not read a clean lat/long.")


class LocationRules(unittest.TestCase):
    def test_rule_1_keeps_a_certificate_lat_long_that_lies_inside_its_parcel(self):
        index, _ = build_index([cert("certs/07-0001.pdf", latlong=north(105), parcel="1234-0001-0001-000")],
                               parcels=[parcel("1234-0001-0001-000", 100)])
        loc = index["records"][0]["location"]
        self.assertEqual(loc["found_by"], "certificate lat/long, checked by Parcel ID")
        self.assertAlmostEqual(loc["lat"], at(105)[0], places=6)

    def test_rule_1_keeps_a_lat_long_within_100_m_of_its_parcel_and_flags_one_further_out(self):
        parcels = [parcel("1234-0001-0001-000", 100)]  # its north edge is 120 m north of HOME
        index, report = build_index([cert("certs/07-0001.pdf", latlong=north(200), parcel="1234-0001-0001-000"),
                                     cert("certs/07-0002.pdf", latlong=north(250), parcel="1234-0001-0001-000")], parcels)
        near, far = index["records"]
        self.assertEqual(near["location"]["found_by"], "certificate lat/long, checked by Parcel ID")
        self.assertEqual((far["location"]["found_by"], far["location"]["lat"]), ("placed by Parcel ID", round(at(100)[0], 7)))
        self.assertEqual(far["flags"], ["Printed lat/long is 150 m off. Placed by Parcel ID."])
        self.assertEqual(report["flagged"], [{"id": "certs/07-0002.pdf", "flags": far["flags"]}])  # for Rick to review


    def test_a_parcel_drawn_as_two_shapes_checks_against_both_and_is_placed_at_their_centre(self):
        parcels = [parcel("1234-0001-0001-000", 100), parcel("1234-0001-0001-000", 300)]
        index, _ = build_index([cert("certs/07-0001.pdf", latlong=north(305), parcel="1234-0001-0001-000"),
                                cert("certs/07-0002.pdf", parcel="1234-0001-0001-000")], parcels)
        inside, by_id = (r["location"] for r in index["records"])
        self.assertEqual(inside["found_by"], "certificate lat/long, checked by Parcel ID")
        self.assertEqual((by_id["found_by"], by_id["lat"]), ("placed by Parcel ID", round(at(200)[0], 7)))

    def test_rule_2_places_a_parcel_split_since_at_the_centre_of_its_pieces(self):
        index, _ = build_index([cert("certs/07-0001.pdf", parcel="1234-0001-0002-000")],
                               [parcel("1234-0001-0002-001", 100, acres=1), parcel("1234-0001-0002-002", 200, acres=3)])
        [rec] = index["records"]
        self.assertEqual(rec["facts"][0]["note"], "Split since: GCAD now has only newer parcels with this number.")
        self.assertEqual((rec["location"]["found_by"], rec["location"]["lat"]), ("placed by Parcel ID, since split", round(at(175)[0], 7)))  # the bigger piece pulls harder
        self.assertEqual(rec["flags"], ["Parcel split since this Record. Placed at the centre of its pieces."])


    def test_rule_3_places_a_record_by_its_street_address_and_the_city_chooses_between_two_towns(self):
        parcels = [parcel("1234-0001-0001-000", 300, situs="12 EXAMPLE DR GALVESTON, TX 77550"),
                   parcel("5678-0001-0001-000", 900, situs="12 EXAMPLE DR TEXAS CITY, TX 77590")]
        index, _ = build_index([cert("certs/07-0001.pdf", address="12 Example Drive, Galveston")], parcels)
        loc = index["records"][0]["location"]
        self.assertEqual((loc["found_by"], loc["lat"]), ("placed by address (GCAD)", round(at(300)[0], 7)))

    def test_rule_3_matches_a_gcad_situs_that_leaves_out_the_street_type_but_not_another_street_type(self):
        parcels = [parcel("1234-0001-0001-000", 300, situs="41 SAMPLE TEXAS CITY, TX 77590"),
                   parcel("5678-0001-0001-000", 900, situs="31 OTHER CT TEXAS CITY, TX 77590")]
        index, _ = build_index([cert("certs/07-0001.pdf", address="41 Sample Drive, Texas City"),
                                cert("certs/07-0002.pdf", address="31 Other Drive, Texas City")], parcels)
        same, other = (r["location"] for r in index["records"])
        self.assertEqual(same["found_by"], "placed by address (GCAD)")
        self.assertIsNone(other)

    def test_rule_3_ignores_a_note_in_brackets_in_the_address(self):
        parcels = [parcel("1234-0001-0001-000", 300, situs="88 EXAMPLE BLVD GALVESTON, TX 77551")]
        index, _ = build_index([cert("certs/07-0001.pdf", address="88 Example Blvd (Shop), Galveston")], parcels)
        self.assertEqual(index["records"][0]["location"]["found_by"], "placed by address (GCAD)")

    def test_rule_1_checks_a_lat_long_against_the_address_parcel_when_there_is_no_parcel_id(self):
        parcels = [parcel("1234-0001-0001-000", 300, situs="12 EXAMPLE DR GALVESTON, TX 77550")]
        index, report = build_index([cert("certs/07-0001.pdf", latlong=north(305), address="12 Example Dr., Galveston"),
                                     cert("certs/07-0002.pdf", latlong=north(5000), address="12 Example Dr, Galveston"),
                                     cert("certs/07-0003.pdf", latlong=north(700), address="99 Unknown Rd, Galveston")], parcels)
        good, bad, unchecked = (r["location"] for r in index["records"])
        self.assertEqual(good["found_by"], "certificate lat/long, checked by address")
        self.assertEqual(bad["found_by"], "placed by address (GCAD)")
        self.assertEqual(index["records"][1]["flags"], ["Printed lat/long is 4.7 km off. Placed by address (GCAD)."])
        self.assertIsNone(unchecked)  # never trusted blindly: nothing could check it
        self.assertEqual(report["not_located"], [{"id": "certs/07-0003.pdf", "reason": "Lat/long could not be checked "
                         "against a parcel or address. No Parcel ID. Address not found. Its Job has no other placed Records."}])

    def test_the_census_geocoder_can_check_a_lat_long_that_gcad_cannot(self):
        def census_geocoder(address):
            return at(720) if address.startswith("99") else at(2000)
        index, _ = build_index([cert("certs/07-0001.pdf", latlong=north(700), address="99 Unknown Rd, Galveston"),
                                cert("certs/07-0002.pdf", latlong=north(700), address="77 New St, Galveston")],
                               census_geocoder=census_geocoder)
        agrees, differs = index["records"]
        self.assertEqual(agrees["location"]["found_by"], "certificate lat/long, checked by address (Census Geocoder)")
        self.assertEqual(differs["location"]["found_by"], "placed by address (Census Geocoder)")
        self.assertEqual(differs["flags"], ["Printed lat/long is 1.3 km off. Placed by address (Census Geocoder)."])

    def test_rule_1_keeps_a_lat_long_its_address_agrees_with_when_the_parcel_id_points_far_away(self):
        parcels = [parcel("1234-0001-0001-000", 300, situs="12 EXAMPLE DR GALVESTON, TX 77550"),
                   parcel("5678-0001-0001-000", 5000)]  # a typo in the Parcel ID that hits another real parcel
        index, _ = build_index([cert("certs/07-0001.pdf", latlong=north(305), parcel="5678-0001-0001-000",
                                     address="12 Example Dr, Galveston")], parcels)
        [rec] = index["records"]
        self.assertEqual(rec["location"]["found_by"], "certificate lat/long, checked by address")
        self.assertEqual(rec["flags"], ["Parcel ID points to a parcel 4.7 km away. The lat/long and address agree."])
        parcel_id = next(f for f in rec["facts"] if f["label"] == "Parcel ID")  # so later Search summaries never use it
        self.assertEqual((parcel_id["ok"], parcel_id["note"]), (False, "Points to a parcel 4.7 km from the lat/long and address."))

    def test_rule_3_asks_the_census_geocoder_only_when_gcad_has_no_such_address(self):
        asked = []

        def geocode(address):
            asked.append(address)
            return at(400)
        parcels = [parcel("1234-0001-0001-000", 300, situs="12 EXAMPLE DR GALVESTON, TX 77550")]
        index, _ = build_index([cert("certs/07-0001.pdf", address="12 Example Dr, Galveston"),
                                cert("certs/07-0002.pdf", address="77 New Street, Galveston")], parcels, census_geocoder=geocode)
        self.assertEqual(asked, ["77 New Street, Galveston"])
        self.assertEqual(index["records"][1]["location"]["found_by"], "placed by address (Census Geocoder)")


    def test_rule_4_places_a_record_by_its_job_when_the_jobs_records_lie_within_300_m(self):
        survey = {"file": "surveys/07-0001.pdf", "kind": "Survey",
                  "facts": [{"label": "Parcel ID", "value": "1234-0001-0001-000", "page": 1, "read_by": "vision model"}]}
        index, report = build(
            survey, cert("certs/07-0001.pdf", at_m=250), cert("certs/07-0001-B.pdf", zone="AE"),
            cert("certs/07-0002.pdf", at_m=100), cert("certs/07-0002-1.pdf", at_m=500),
            cert("certs/07-0002-2.pdf", zone="AE"),
            {**cert("certs/07-0003.pdf", at_m=100), "kind": "Natural Ground Letter"}, cert("certs/07-0003-B.pdf", zone="AE"),
            cert("certs/07-0004.pdf", at_m=100), cert("certs/07-0004-B.pdf", latlong=north(900)),
            parcels=[parcel("1234-0001-0001-000", 200)])
        by_id = {r["id"]: r for r in index["records"]}
        loc = by_id["certs/07-0001-B.pdf"]["location"]
        self.assertEqual((loc["found_by"], loc["lat"]), ("placed by its Job", round(at(250)[0], 7)))  # the certificate's
        self.assertIsNone(by_id["certs/07-0002-2.pdf"]["location"])  # its Job's Records are 400 m apart
        self.assertEqual(report["not_located"], [
            {"id": "certs/07-0002-2.pdf", "reason":
             "No lat/long. No Parcel ID. No address. Its Job's other Records are more than 300 m apart."},
            {"id": "certs/07-0003-B.pdf", "reason": "No lat/long. No Parcel ID. No address. Its Job has no placed "
             "certificate or Survey."}])  # a Natural Ground Letter does not place its Job's other Records
        self.assertEqual(by_id["certs/07-0004-B.pdf"]["flags"], ["Printed lat/long is 800 m off. Placed by its Job."])


    def test_rule_5_an_overrides_file_entry_places_a_record_by_hand(self):
        overrides = {"certs/07-0001.pdf": {"lat": at(100)[0], "lon": at(100)[1], "why": "Lot 3 on the Survey"}}
        index, report = build_index([cert("certs/07-0001.pdf", zone="AE"), cert("certs/07-0002.pdf", zone="AE")],
                                    overrides=overrides)
        self.assertEqual(index["records"][0]["location"]["found_by"], "placed by hand")
        self.assertEqual([x["id"] for x in report["not_located"]], ["certs/07-0002.pdf"])

    def test_an_overrides_file_entry_that_cannot_be_used_is_on_the_ingestion_report(self):
        overrides = {"certs/07-0001.pdf": {"lat": 31.0, "lon": -94.8, "why": "typo"},
                     "certs/07-0999.pdf": {"lat": at(100)[0], "lon": at(100)[1], "why": "no such Record"}}
        index, report = build_index([cert("certs/07-0001.pdf", zone="AE")], overrides=overrides)
        self.assertIsNone(index["records"][0]["location"])
        self.assertEqual(report["bad_overrides"], [{"id": "certs/07-0001.pdf", "reason": "Not in Galveston County."},
                                                   {"id": "certs/07-0999.pdf", "reason": "No such Record."}])


class NearbySearch(unittest.TestCase):
    def test_a_record_just_inside_the_distance_is_found_and_one_just_outside_is_not(self):
        half_mile = 804.672
        index, _ = build(cert("certs/11-0001.pdf", at_m=half_mile - 10), cert("certs/11-0002.pdf", at_m=half_mile + 10))
        answer = nearby_search(index, HOME, 0.5)
        self.assertEqual([(j["rank"], j["job"]) for j in answer["jobs"]], [(1, "11-0001")])
        self.assertEqual(answer["jobs"][0]["distance_ft"], 2607)  # 794.672 m
        self.assertEqual(answer["query"], {"point": [29.30, -94.80], "distance_mi": 0.5, "parcel_id": None})

    def test_a_job_with_records_in_two_places_is_found_by_its_near_record_and_gets_a_pin_for_each(self):
        index, _ = build(cert("certs/11-0003-1.pdf", at_m=2000), cert("certs/11-0003-2.pdf", at_m=300))
        [job] = nearby_search(index, HOME, 0.5)["jobs"]
        self.assertEqual(job["distance_ft"], 984)  # 300 m, to the nearest Record
        self.assertEqual(sorted(p["records"] for p in job["pins"]), [["certs/11-0003-1.pdf"], ["certs/11-0003-2.pdf"]])

    def test_records_within_50_m_share_a_pin_and_a_search_result_shows_its_records_flags(self):
        index, _ = build(cert("certs/07-0001-1.pdf", at_m=100), cert("certs/07-0001-2.pdf", at_m=140),
                         cert("certs/07-0001-3.pdf", latlong=north(200), parcel="1234-0001-0001-000"),
                         parcels=[parcel("1234-0001-0001-000", 600)])
        [job] = nearby_search(index, HOME, 0.5)["jobs"]
        self.assertEqual([p["records"] for p in job["pins"]], [["certs/07-0001-1.pdf", "certs/07-0001-2.pdf"], ["certs/07-0001-3.pdf"]])
        self.assertEqual(job["flags"], ["Printed lat/long is 400 m off. Placed by Parcel ID."])

    def test_a_search_result_record_has_its_page_count_and_photo_page_for_the_record_viewer(self):
        index, _ = build({**cert("certs/07-0001.pdf", at_m=100), "pages": 4, "photo_page": 3, "photo": True})
        [rec] = nearby_search(index, HOME, 0.5)["jobs"][0]["records"]
        self.assertEqual((rec["pages"], rec["photo_page"], rec["photo"]), (4, 3, True))

    def test_jobs_are_sorted_nearest_first_then_by_job_number(self):
        index, _ = build(cert("certs/11-0005.pdf", at_m=400), cert("certs/11-0009.pdf", at_m=100),
                         cert("certs/11-0004.pdf", at_m=400))
        answer = nearby_search(index, HOME, 0.5)
        self.assertEqual([(j["rank"], j["job"]) for j in answer["jobs"]], [(1, "11-0009"), (2, "11-0004"), (3, "11-0005")])

    def test_a_search_result_gives_the_address_of_its_nearest_record_its_kinds_and_the_counts(self):
        index, _ = build(cert("certs/11-0006-1.pdf", at_m=600, address="9 Far Ln"),
                         cert("certs/11-0006-2.pdf", at_m=50, address="1 Near St"),
                         cert("certs/11-0007.pdf", address="No Location Rd"), cert("certs/11-0008.pdf", at_m=5000))
        answer = nearby_search(index, HOME, 0.5)
        [job] = answer["jobs"]
        self.assertEqual((job["address"], job["kinds"]), ("1 Near St", ["Elevation Certificate"]))
        self.assertEqual([r["id"] for r in job["records"]], ["certs/11-0006-2.pdf", "certs/11-0006-1.pdf"])
        self.assertEqual(answer["counts"], {"jobs": 1, "records": 2})
        self.assertEqual(index["counts"], {"jobs": 3, "records": 4, "kinds": {"Elevation Certificate": 4}})


def survey(file, kind="Survey", drawn=(), **facts):
    """A Survey folder Record with raw Facts read by the vision model from page 1.
    drawn: (label, value) pairs read from its drawing, e.g. ("Building", "Shed")."""
    labels = {"job": "Job number", "date": "Date", "parcel": "Parcel ID", "legal": "Lot and block", "flood": "Flood note",
              "plat": "Recorded Plat"}
    pairs = [(labels[k], v) for k, v in facts.items()] + list(drawn)
    return {"file": file, "kind": kind, "facts": [{"label": k, "value": v, "page": 1, "read_by": "vision model"} for k, v in pairs]}


class Surveys(unittest.TestCase):
    def test_a_survey_links_to_the_recorded_plat_it_cites_when_that_plat_is_held(self):
        index, _ = build_index([survey("surveys/07-0001.pdf", plat="Volume 7, Page 12"),
                                survey("surveys/07-0002.pdf", plat="Volume 7, Page 30.1")], plats={"7_12", "7_30.1"})
        self.assertEqual([r["plat"] for r in index["records"]], ["7_12", "7_30.1"])
        fact = next(f for f in index["records"][0]["facts"] if f["label"] == "Recorded Plat")
        self.assertEqual((fact["value"], fact["ok"]), ("Volume 7, Page 12", True))

    def test_a_plat_not_held_or_in_another_county_stays_text_and_the_report_counts_the_citations(self):
        index, report = build_index([survey("surveys/07-0001.pdf", plat="Volume 7, Page 12"),
                                     survey("surveys/07-0002.pdf", plat="Volume 999-A, Page 5"),
                                     survey("surveys/07-0003.pdf", plat="Volume 7, Page 12, Sample County"),
                                     survey("surveys/07-0004.pdf")], plats={"7_12"})
        self.assertEqual([r["plat"] for r in index["records"]], ["7_12", None, None, None])
        self.assertEqual(report["plat_citations"], {
            "citing": 3, "found": 1,
            "not_held": [{"id": "surveys/07-0002.pdf", "plat": "Volume 999-A, Page 5"},
                         {"id": "surveys/07-0003.pdf", "plat": "Volume 7, Page 12, Sample County"}]})

    def test_a_survey_links_to_an_a_map_and_to_a_volume_written_with_a_dash(self):
        index, _ = build_index([survey("surveys/07-0001.pdf", plat="Volume 7, Page 16-A"),
                                survey("surveys/07-0002.pdf", plat="Volume 31-A, Page 5")], plats={"7_16A", "31A_5"})
        self.assertEqual([r["plat"] for r in index["records"]], ["7_16A", "31A_5"])

    def test_a_printed_job_number_that_differs_from_the_file_name_is_flagged_and_the_file_name_wins(self):
        index, report = build_index([survey("surveys/07-0001.pdf", job="07-0010"), survey("surveys/07-0002.pdf", job="07-0002")])
        wrong, right = index["records"]
        self.assertEqual((wrong["job"], wrong["flags"]), ("07-0001", ["Printed JOB No. 07-0010; the file name says 07-0001."]))
        self.assertEqual(right["flags"], [])

    def test_a_surveys_lot_and_block_are_compared_with_the_gcad_legal_description_of_its_parcel(self):
        parcels = [parcel("1234-0001-0001-000", 100, legal="SAMPLE SHORES SEC 2, BLOCK 2, LOT 3, ACRES 0.2")]
        index, _ = build_index([
            survey("surveys/07-0001.pdf", parcel="1234-0001-0001-000", legal="Lots Three (3), Block 2, Sample Shores Section 2"),
            survey("surveys/07-0002.pdf", parcel="1234-0001-0001-000", legal="Lot 9, Block 7, Other Place"),
            cert("certs/07-0003.pdf", parcel="1234-0001-0001-000", legal="Lot 9, Block 7, Other Place")], parcels)
        agrees, differs, certificate = (r["flags"] for r in index["records"])
        self.assertEqual(agrees, [])
        self.assertEqual(differs, ["Lot and block differ from GCAD's legal description for its Parcel ID."])
        lot_and_block = next(f for f in index["records"][1]["facts"] if f["label"] == "Lot and block")
        self.assertEqual((lot_and_block["ok"], lot_and_block["note"]), (False, "Differs from GCAD's legal description."))
        self.assertEqual(certificate, [])  # only a Survey's lot and block are compared

    def test_the_lot_and_block_comparison_reads_number_words_and_compares_only_what_the_survey_gives(self):
        cases = [  # the Survey's lot and block, GCAD's legal description, whether they differ
            ("Lot Three, Block Eleven, Sample Shores", "SAMPLE SHORES REPLAT, BLOCK 11, LOT 3, ACRES 0.2", False),
            ("Lots 52, 53, Sample's Addition", "LOT 52 & S 1/2 OF ALLEY BLK 2 SAMPLES ADDN", False),
            ("Lot Lot 5, Block BLOCK 88", "N 40-6 FT OF LOT 5 (5-1) BLK 88 SAMPLETON", False),
            ("Lot C, Block 12, Sample Replat", "LOT C SAMPLE REPLAT (2003)", False),
            ("Sample Harbour", "ABST 9 SAMPLE SUR TRACT 6 12.5 ACRES", False),
            ("Lots Fourteen, Block Thirty-Two, Sample Outlots", "LOT 14 SE BLK 32 SAMPLETON OUTLOTS", False),
            ("Block 141 and 142", "(0-0) BLK 142 & ADJ ST SAMPLETON", False),
            ("Lot 21A, Block Three Hundred Twelve (312)", "BLOCK 312, LOT 21A, ACRES 0.2", False),
            ("Lots 3, 4, Sample Place", "LOTS 1 THRU 4 BLK 9 SAMPLETON", False),
            ("Lot 15, Block 4, Sample Cove", "SAMPLE COVE REPLAT, BLOCK 4, LOT 15A", False),  # replatted since: a parcel change
            ("Lot 18A, Sample Cove", "LOT 18C SAMPLE COVE REPLAT", True),
            ("Lots 6, 7, Block Four, Block Four Hundred Twelve (412)", "LOTS 5 THRU 9 BLK 412 SAMPLETON", False),
            ("Lot 6, Sample Isle", "LOT 31 SAMPLE ISLE SEC 9", True),
            ("Lot 2, Block 7, Sample Shores", "SAMPLE SHORES SEC 4, BLOCK 7, LOT 9, ACRES 0.2", True),
            ("Lot 6, Block 2, Sample Isle", "LOT 31 BLOCK 2 SAMPLE ISLE", True),
            ("Lot 4, Block 4, Sample Manor", "LOT 4 BLK 3 SAMPLE MANOR", True),
            ("Lots 15, 16, Block 444", "LOTS 1 THRU 4 BLK 443 SAMPLETON", True),
        ]
        for ours, legal, differs in cases:
            with self.subTest(ours=ours):
                index, _ = build_index([survey("surveys/07-0001.pdf", parcel="1234-0001-0001-000", legal=ours)],
                                       [parcel("1234-0001-0001-000", 100, legal=legal)])
                self.assertEqual(bool(index["records"][0]["flags"]), differs)

    def test_a_survey_only_job_takes_its_address_from_gcad_by_its_parcel_id(self):
        index, _ = build_index([survey("surveys/07-0001.pdf", parcel="1234-0001-0001-000")],
                               [parcel("1234-0001-0001-000", 100, situs="12 EXAMPLE DR GALVESTON, TX 77550")])
        [job] = nearby_search(index, HOME, 0.5)["jobs"]
        self.assertEqual(job["address"], "12 EXAMPLE DR GALVESTON, TX 77550")

    def test_rule_4_places_a_record_by_its_jobs_survey_when_the_job_has_no_placed_certificate(self):
        index, _ = build_index([survey("surveys/07-0001.pdf", parcel="1234-0001-0001-000"),
                                survey("surveys/07-0001-MB.pdf", kind="Metes-and-Bounds Description")],
                               [parcel("1234-0001-0001-000", 100)])
        description = index["records"][1]["location"]
        self.assertEqual((description["found_by"], description["lat"]), ("placed by its Job", round(at(100)[0], 7)))

    def test_a_surveys_date_and_flood_note_are_kept(self):
        index, _ = build_index([survey("surveys/07-0001.pdf", date="2004-08-11", flood="In the 100-year flood plain")])
        [rec] = index["records"]
        self.assertEqual(rec["date"], "2004-08-11")  # a Survey can be years older than its Job
        self.assertTrue(all(f["ok"] for f in rec["facts"]))

    def test_a_surveys_buildings_easements_and_setback_lines_are_kept_for_the_record_viewer_and_corner_marks_never(self):
        drawn = [("Building", "Frame House"), ("Building", "Shed"), ("Easement", "7.5' U.E."), ("Setback line", "20' B.L."),
                 ("Corner mark", "Fnd. Rod")]
        [rec] = build_index([survey("surveys/07-0001.pdf", drawn=drawn)])[0]["records"]
        self.assertEqual([(f["label"], f["value"], f["ok"]) for f in rec["facts"]], [
            ("Building", "Frame House", True), ("Building", "Shed", True), ("Easement", "7.5' U.E.", True),
            ("Setback line", "20' B.L.", True)])


class AuthoritativeFacts(unittest.TestCase):
    def test_the_fema_zone_bfe_and_panel_come_from_the_saved_flood_polygons_at_the_search_point(self):
        fema = {"zones": [{"zone": "X", "bfe": None, "shape": box(*at(1000), 300)},
                          {"zone": "AE", "bfe": 14.0, "shape": box(*HOME, 300)}],
                "panels": [{"panel": "48000C0200Z", "date": "2019-08-15", "shape": box(*at(5000), 1000)},
                           {"panel": "48000C0100Z", "date": "2019-08-15", "shape": box(*HOME, 3000)}]}
        index, _ = build_index([], fema=fema)
        self.assertEqual(nearby_search(index, HOME, 0.5)["fema"],
                         {"zone": "AE", "bfe": 14.0, "panel": "48000C0100Z", "panel_date": "2019-08-15"})
        self.assertEqual(nearby_search(index, at(1000), 0.5)["fema"]["zone"], "X")

    def test_the_searched_parcel_is_found_by_its_parcel_id_or_else_by_the_parcel_holding_the_point(self):
        index, _ = build_index([], [square("1234-0001-0001-000", *HOME, half=30, situs="12 EXAMPLE DR GALVESTON, TX 77550"),
                                    parcel("5678-0001-0001-000", 500)])
        by_point = nearby_search(index, HOME, 0.5)
        self.assertEqual(by_point["parcel"], {"id": "1234-0001-0001-000", "situs": "12 EXAMPLE DR GALVESTON, TX 77550",
                                              "legal": "", "acres": 0.2})
        self.assertEqual(by_point["query"]["parcel_id"], "1234-0001-0001-000")
        self.assertEqual(nearby_search(index, HOME, 0.5, parcel_id="5678-0001-0001-000")["parcel"]["id"], "5678-0001-0001-000")
        self.assertIsNone(nearby_search(index, at(3000), 0.5)["parcel"])

    def test_the_nearest_ngs_benchmark_comes_with_its_height_and_distance(self):
        ngs = [{"id": "ZZ0002", "name": "FAR MARK", "lat": at(900)[0], "lon": HOME[1], "height_ft": 9.1},
               {"id": "ZZ0001", "name": "NEAR MARK", "lat": at(300)[0], "lon": HOME[1], "height_ft": 4.6}]
        index, _ = build_index([], ngs=ngs)
        self.assertEqual(nearby_search(index, HOME, 0.5)["ngs"], {"id": "ZZ0001", "name": "NEAR MARK", "height_ft": 4.6,
                                                                   "distance_ft": 984, "lat": at(300)[0], "lon": HOME[1]})


class NoJobs(unittest.TestCase):
    def test_with_no_jobs_in_range_the_answer_names_the_nearest_job_and_offers_2_mi_only_when_that_reaches_it(self):
        mile = 1609.344
        index, _ = build(cert("certs/07-0001.pdf", at_m=1.5 * mile))
        none_near = nearby_search(index, HOME, 0.5)
        self.assertEqual(none_near["jobs"], [])
        nearest = none_near["nearest_outside"]
        self.assertEqual((nearest["job"], nearest["distance_ft"], nearest["reaches_at_2_mi"]), ("07-0001", 7920, True))
        self.assertAlmostEqual(nearest["lat"], at(1.5 * mile)[0], places=6)  # for the map
        far, _ = build(cert("certs/07-0002.pdf", at_m=3 * mile))
        self.assertFalse(nearby_search(far, HOME, 0.5)["nearest_outside"]["reaches_at_2_mi"])
        self.assertNotIn("nearest_outside", nearby_search(index, HOME, 2))  # only when there are no Jobs


def recorded_plat(name, date, *area, section=None, kind="subdivision plat"):
    """A Recorded Plat as index.json holds it: placed on the GCAD parcels in area (none: not placed)."""
    return {"file": "Sample Plats Group 9/x.tif", "page": 0, "image": "pages/plats/x.png", "area": list(area),
            "how": "on the parcels naming it" if area else "GCAD names no parcel",
            "reading": {"kind": kind, "name": name, "section": section, "replat_of": None, "lots": [], "block": None,
                        "lot_count": 10, "town": "Sandport", "date": date, "sheet": None}}


class RecordedPlats(unittest.TestCase):
    def setUp(self):
        self.index, _ = build_index([], [square("1234-0001-0005-000", *HOME, half=30), parcel("1234-0001-0009-000", 200)])

    def plats_at(self, point, plats):
        self.index["plats"] = plats
        return nearby_search(self.index, point, 0.5)["plats"]

    def test_the_answer_lists_the_recorded_plat_whose_area_holds_the_searched_point(self):
        undrawn = {**recorded_plat("Sample Shores", "2003", "1234-0001-0005-000"), "image": None}  # nothing to show
        found = self.plats_at(HOME, {"7_12": recorded_plat("Sample Shores", "1999-01-02", "1234-0001-0005-000",
                                                           "1234-0001-0009-000", section="Section 2"),
                                     "7_13": recorded_plat("Gull Point", "2001-05-06", "1234-0001-0009-000"),
                                     "7_14": recorded_plat("Sample Shores", "1998"), "7_15": undrawn})
        self.assertEqual(found, [{"id": "7_12", "volume": "7", "page": "12", "name": "Sample Shores Section 2",
                                  "date": "1999-01-02", "kind": "subdivision plat"}])

    def test_a_point_outside_every_recorded_plats_area_lists_none(self):
        plat = recorded_plat("Sample Shores", "1999-01-02", "1234-0001-0005-000")
        self.assertEqual(self.plats_at(at(200), {"7_12": plat}), [])  # another parcel
        self.assertEqual(self.plats_at(at(3000), {"7_12": plat}), [])  # no parcel at all

    def test_a_point_inside_a_recorded_plat_and_its_replat_lists_both_newest_first(self):
        found = self.plats_at(HOME, {"7_12": recorded_plat("Sample Shores", "1999-01-02", "1234-0001-0005-000"),
                                     "7_40": recorded_plat("Sample Shores", "2004", "1234-0001-0005-000", kind="replat")})
        self.assertEqual([(p["id"], p["kind"]) for p in found], [("7_40", "replat"), ("7_12", "subdivision plat")])


HEADINGS = ["Same parcel", "Neighbors", "Flood then and now", "Ground and floor heights", "Benchmarks", "Parcel changes",
            "Recorded Plats"]
STREET = [  # made-up GCAD parcels on one street, each 40 m square
    square("1234-0001-0005-000", *HOME, situs="5 SAMPLE ST GALVESTON, TX 77550", legal="SAMPLE SHORES, BLOCK 1, LOT 5"),  # searched
    parcel("1234-0001-0006-000", 40, situs="6 SAMPLE ST GALVESTON, TX 77550"),  # next door: shares its north edge
    parcel("1234-0001-0009-000", 200),  # same block
    parcel("1234-0001-0008-001", 300), parcel("1234-0001-0008-002", 340),  # lot 8, split since
    parcel("1234-0007-0001-000", 500),  # same subdivision
    parcel("5678-0001-0001-000", 700),  # another subdivision
]
FEMA = {"zones": [{"zone": "AE", "bfe": 13.0, "shape": box(*HOME, 300)}],
        "panels": [{"panel": "48000C0100Z", "date": "2019-08-15", "shape": box(*HOME, 3000)}]}
NGS = [{"id": "ZZ0001", "name": "NEAR MARK", "lat": at(300)[0], "lon": HOME[1], "height_ft": 4.6}]


def brief(*records, fema=None, ngs=(), plats=None):
    """(the Search summary at HOME within ½ mi as {heading: text}, the search answer). Each [n] in the text is
    replaced by its Source, a Record id, a Recorded Plat's volume_page or FEMA, NGS or GCAD; a number with no Source
    fails the test."""
    index = build_index(list(records), STREET, fema=fema, ngs=ngs)[0]
    answer = nearby_search({**index, "plats": plats or {}}, HOME, 0.5)
    s = answer["summary"]
    names = {x["n"]: x.get("record") or x.get("plat") or x["source"] for x in s["sources"]}

    def read(text):
        return re.sub(r"\[(\d+)\]", lambda m: f"[{names[int(m.group(1))]}]", text)
    return {"Before you quote": read(s["advice"]), **{f["heading"]: read(f["text"]) for f in s["findings"]}}, answer


class SearchSummary(unittest.TestCase):
    def test_the_recorded_plats_holding_the_address_are_named_and_cited_newest_first(self):
        home = "1234-0001-0005-000"
        plats = {"7_12": recorded_plat("Sample Shores", "1999-01-02", home, section="Section 2"),
                 "7_40": recorded_plat("Gull Cove", "2004", home, kind="replat"),
                 "7_13": recorded_plat("Gull Point", "2001-05-06", "1234-0001-0009-000")}
        text, answer = brief(plats=plats)
        self.assertEqual(text["Recorded Plats"], "This address lies in Gull Cove (a replat), Volume 7, Page 40, recorded "
                         "2004 [7_40], and in Sample Shores Section 2, Volume 7, Page 12, recorded 1999 [7_12].")
        self.assertEqual(brief()[0]["Recorded Plats"], "No placed Recorded Plat holds this address.")
        index = build_index([], STREET)[0]  # a point in the street: plat areas are parcels, so none can be matched
        street = nearby_search({**index, "plats": plats}, at(3000), 0.5)["summary"]["findings"][-1]["text"]
        self.assertEqual(street, "No GCAD parcel holds this point, so no Recorded Plat can be matched to it.")
        source = next(x for x in answer["summary"]["sources"] if x.get("plat") == "7_12")
        self.assertEqual((source["source"], source["label"]), ("Recorded Plat", "Volume 7, Page 12: Sample Shores Section 2"))
        unnamed = brief(plats={"7_12": recorded_plat(None, None, home)})[0]["Recorded Plats"]
        self.assertEqual(unnamed, "This address lies in a subdivision whose name was not read, Volume 7, Page 12 [7_12].")

    def test_the_briefing_has_advice_then_its_findings_under_fixed_headings_in_order(self):
        text, answer = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000"))
        self.assertEqual(list(text), ["Before you quote", *HEADINGS])

    def test_same_parcel_lists_the_jobs_records_and_cites_a_conflict_flag_and_the_advice_names_its_survey(self):
        text, _ = brief(survey("surveys/07-0001.pdf", parcel="1234-0001-0005-000", date="2004-08-11"),
                        cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", date="23-MAR-07", latlong=north(5000)),
                        cert("certs/07-0001-B.pdf", parcel="1234-0001-0005-000", latlong=north(5000)))
        self.assertEqual(text["Same parcel"], "The Firm has worked on this parcel before. Job 07-0001: Survey, Aug 2004 "
                         "[surveys/07-0001.pdf]; Elevation Certificate, Mar 2007 [certs/07-0001.pdf]; Elevation "
                         "Certificate, no date [certs/07-0001-B.pdf]. Flag: Printed lat/long is 5.0 km off. Placed by "
                         "Parcel ID [certs/07-0001.pdf] [certs/07-0001-B.pdf].")
        self.assertEqual(text["Before you quote"], "Get Survey 07-0001 before you quote [surveys/07-0001.pdf]. "
                         "The Firm has already worked on this parcel.")

    def test_neighbors_are_next_door_on_the_same_block_in_the_same_subdivision_or_elsewhere(self):
        text, answer = brief(cert("certs/07-0002.pdf", address="6 Sample St, Galveston"),  # its parcel by its address
                             survey("surveys/07-0003.pdf", parcel="1234-0001-0009-000"),
                             cert("certs/07-0005.pdf", parcel="1234-0007-0001-000"),
                             cert("certs/07-0006.pdf", parcel="5678-0001-0001-000"))
        self.assertEqual({j["job"]: j["relation"] for j in answer["jobs"]}, {
            "07-0002": "next door", "07-0003": "same block", "07-0005": "same subdivision", "07-0006": "nearby"})
        self.assertEqual(text["Neighbors"], "Job 07-0002 is next door, 131 ft away [certs/07-0002.pdf]. "
                         "Job 07-0003 is on the same block, 656 ft away [surveys/07-0003.pdf]. "
                         "Job 07-0005 is in the same subdivision, 1,640 ft away [certs/07-0005.pdf]. "
                         "Job 07-0006 is elsewhere within ½ mi, 2,297 ft away [certs/07-0006.pdf].")
        self.assertEqual(text["Same parcel"], "No earlier Job on this parcel.")
        self.assertEqual(text["Before you quote"], "Get Survey 07-0003, 656 ft away, before you quote [surveys/07-0003.pdf].")

    def test_same_parcel_names_the_buildings_easements_and_setback_lines_on_its_newest_drawn_survey(self):
        drawn = [("Building", "Frame House"), ("Building", "Shed"), ("Easement", "7.5' U.E."), ("Setback line", "20' B.L.")]
        text, _ = brief(survey("surveys/07-0001.pdf", parcel="1234-0001-0005-000", date="2004-08-11",
                               drawn=[("Building", "Old Cottage")]),
                        survey("surveys/09-0001.pdf", parcel="1234-0001-0005-000", date="2009-05-02", drawn=drawn),
                        survey("surveys/09-0001-2.pdf", parcel="1234-0001-0006-000", date="2009-06-02",
                               drawn=[("Building", "Next Door House")]))  # the same Job, but next door
        self.assertEqual(text["Same parcel"], "The Firm has 2 Jobs on this parcel. Job 07-0001: Survey, Aug 2004 "
                         "[surveys/07-0001.pdf]. Job 09-0001: Survey, May 2009 [surveys/09-0001.pdf]; Survey, Jun 2009 "
                         "[surveys/09-0001-2.pdf]. Survey 09-0001 (May 2009) shows buildings “Frame House”, “Shed”; "
                         "easement “7.5' U.E.”; setback line “20' B.L.” [surveys/09-0001.pdf].")

    def test_neighbors_name_what_the_nearest_survey_of_each_group_shows(self):
        text, _ = brief(survey("surveys/07-0002.pdf", parcel="1234-0001-0006-000",
                               drawn=[("Building", "Frame House"), ("Setback line", "20' B.L.")]),
                        survey("surveys/07-0003.pdf", parcel="1234-0001-0009-000", drawn=[("Easement", "7.5' U.E.")]),
                        survey("surveys/07-0005.pdf", parcel="1234-0007-0001-000",
                               drawn=[("Easement", "5' D.E."), ("Easement", "7.5' U.E.")]),
                        survey("surveys/07-0006.pdf", parcel="5678-0001-0001-000", drawn=[("Building", "Barn")]))
        self.assertEqual(text["Neighbors"], "Job 07-0002 is next door, 131 ft away; its Survey shows building "
                         "“Frame House”; setback line “20' B.L.” [surveys/07-0002.pdf]. Job 07-0003 is on the same block, "
                         "656 ft away; its Survey shows easement “7.5' U.E.” [surveys/07-0003.pdf]. Job 07-0005 is in the "
                         "same subdivision, 1,640 ft away; its Survey shows easements “5' D.E.”, “7.5' U.E.” "
                         "[surveys/07-0005.pdf]. Job 07-0006 is elsewhere within ½ mi, 2,297 ft away; its Survey shows "
                         "building “Barn” [surveys/07-0006.pdf].")

    def test_a_record_printed_with_the_searched_address_is_on_the_same_parcel_though_its_parcel_id_is_next_door(self):
        _, answer = brief(cert("certs/07-0008.pdf", parcel="1234-0001-0006-000", address="5 Sample St, Galveston"))
        self.assertEqual(answer["jobs"][0]["relation"], "same parcel")

    def test_flood_then_and_now_keeps_an_old_zone_name_as_printed_with_todays_name_beside_it(self):
        text, _ = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", date="23-MAR-07", zone="A17", bfe="12"),
                        fema=FEMA)
        self.assertEqual(text["Flood then and now"], "Job 07-0001's Elevation Certificate on this parcel (Mar 2007) "
                         "shows Zone A17 (called AE today), BFE 12 ft [certs/07-0001.pdf]. FEMA's map today shows "
                         "Zone AE, BFE 13 ft, panel 48000C0100Z, effective Aug 15, 2019 [FEMA].")
        changed, _ = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", date="23-MAR-07", zone="C"), fema=FEMA)
        self.assertEqual(changed["Flood then and now"], "Job 07-0001's Elevation Certificate on this parcel (Mar 2007) "
                         "shows Zone C (called X today) [certs/07-0001.pdf]. FEMA's map today shows Zone AE, BFE 13 ft, "
                         "panel 48000C0100Z, effective Aug 15, 2019 [FEMA]. The zone has changed since our Record "
                         "[certs/07-0001.pdf] [FEMA].")

    def test_heights_come_from_the_newest_stage_of_each_building_and_the_nearest_three_buildings(self):
        home = {"parcel": "1234-0001-0005-000", "zone": "AE"}
        text, _ = brief(  # a building is a street address: its certificates can be in one Job or several
            cert("certs/07-0001-1.pdf", address="5 Sample St, Galveston", basis="Construction drawings", date="20-JAN-07",
                 floor="10", lag="4.5", **home),
            cert("certs/07-0001-2.pdf", address="5 Sample Street, Galveston", basis="Finished construction",
                 floor="11", lag="5", lsm="9", **home),  # no date: the stage wins, not the date
            cert("certs/07-0009.pdf", address="5 Sample St., Galveston", basis="Building under construction",
                 date="02-MAR-07", floor="10.5", **home),
            cert("certs/07-0002-A.pdf", parcel="1234-0001-0006-000", address="6 Sample St - Building A, Galveston",
                 zone="VE", floor="17", lag="6", lsm="15.5"),
            cert("certs/07-0002-B.pdf", parcel="1234-0001-0006-000", address="6 Sample St - Building B, Galveston",
                 zone="VE", floor="18"),
            cert("certs/07-0006.pdf", parcel="5678-0001-0001-000", zone="AE", floor="12"))  # the fourth building
        self.assertEqual(text["Ground and floor heights"],  # the lowest structural member only in V zones
                         "Job 07-0001, on this parcel, finished construction: lowest adjacent grade 5 ft, top of bottom "
                         "floor 11 ft [certs/07-0001-2.pdf]. Job 07-0002, 131 ft away: lowest adjacent grade 6 ft, top of "
                         "bottom floor 17 ft, lowest structural member 15.5 ft [certs/07-0002-A.pdf]. Job 07-0002, 131 ft "
                         "away: top of bottom floor 18 ft [certs/07-0002-B.pdf].")
        self.assertIn("[certs/07-0001-2.pdf]", text["Flood then and now"])

    def test_a_certificate_dated_after_a_buildings_finished_one_is_a_new_building_at_the_same_address(self):
        home = {"parcel": "1234-0001-0005-000", "address": "5 Sample St, Galveston"}
        text, _ = brief(cert("certs/07-0001.pdf", basis="Finished construction", date="15-JUN-07", floor="9", **home),
                        cert("certs/09-0001.pdf", basis="Construction drawings", date="20-JUN-09", floor="14", **home))
        self.assertEqual(text["Ground and floor heights"],  # rebuilt: the new house's drawings, not the old house
                         "Job 09-0001, on this parcel, construction drawings: top of bottom floor 14 ft [certs/09-0001.pdf].")

    def test_a_natural_ground_letter_gives_its_natural_ground_height(self):
        text, _ = brief({**cert("certs/07-0004-NG.pdf", parcel="1234-0001-0009-000", ground="6.2"), "kind": "Natural Ground Letter"})
        self.assertEqual(text["Ground and floor heights"], "Job 07-0004, 656 ft away: natural ground 6.2 ft [certs/07-0004-NG.pdf].")

    def test_benchmarks_name_the_ones_nearby_jobs_used_most_and_the_nearest_ngs_benchmark(self):
        text, _ = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", benchmark="TBM 7"),
                        cert("certs/07-0002.pdf", parcel="1234-0001-0006-000", benchmark="Nail in curb, east side"),
                        cert("certs/07-0003.pdf", parcel="1234-0001-0009-000", benchmark="tbm-7"), ngs=NGS)
        self.assertEqual(text["Benchmarks"], "Our nearby Jobs carried elevations from “TBM 7” (2 Jobs) [certs/07-0001.pdf] "
                         "and “Nail in curb, east side” (1 Job) [certs/07-0002.pdf]. The nearest NGS Benchmark is ZZ0001 "
                         "“NEAR MARK”, 984 ft away, height 4.60 ft [NGS].")

    def test_parcel_changes_name_a_parcel_split_or_renumbered_since_our_job_and_give_the_searched_parcel_from_gcad(self):
        text, answer = brief(survey("surveys/07-0003.pdf", parcel="1234-0001-0008-000", date="2004-08-11"),
                             cert("certs/07-0005.pdf", parcel="1234-0007-0001-001", date="23-MAR-07"))
        self.assertEqual([x.get("parcels") for x in answer["summary"]["sources"] if x.get("source") == "GCAD"],  # popups
                         [["1234-0001-0008-001", "1234-0001-0008-002"], ["1234-0007-0001-000"], None])
        self.assertEqual(text["Parcel changes"], "Parcel 1234-0001-0008-000 on Job 07-0003's Survey (Aug 2004) has been "
                         "split since, into 2 parcels [surveys/07-0003.pdf] [GCAD]. Parcel 1234-0007-0001-001 on Job "
                         "07-0005's Elevation Certificate (Mar 2007) has been renumbered since, to 1234-0007-0001-000 "
                         "[certs/07-0005.pdf] [GCAD]. GCAD today: parcel 1234-0001-0005-000 (SAMPLE SHORES, BLOCK 1, LOT 5), "
                         "0.2 acres [GCAD].")
        unchanged, _ = brief(cert("certs/07-0002.pdf", parcel="1234-0001-0006-000"))
        self.assertTrue(unchanged["Parcel changes"].startswith(
            "None of the parcels on our nearby Records has been split or renumbered since [GCAD]."))

    def test_failed_facts_are_never_used(self):
        text, answer = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", zone="Q7", floor="90",
                                  benchmark="~'§,.!", date="32-MAR-07"))
        self.assertEqual(text["Flood then and now"], "The saved FEMA flood map has no zone at this point [FEMA].")
        self.assertEqual(text["Ground and floor heights"], "No nearby Elevation Certificate or Natural Ground Letter has checked heights.")
        self.assertEqual(text["Benchmarks"], "No Benchmark found nearby.")
        for failed in ("Q7", "90 ft", "§", "32-MAR"):
            self.assertNotIn(failed, repr(answer["summary"]))

    def test_every_citation_points_to_a_source_and_every_source_is_cited_in_reading_order(self):
        _, answer = brief(survey("surveys/07-0001.pdf", parcel="1234-0001-0005-000"),
                          cert("certs/07-0002.pdf", parcel="1234-0001-0006-000", zone="AE", floor="11", benchmark="TBM 7"),
                          survey("surveys/07-0003.pdf", parcel="1234-0001-0008-000"), fema=FEMA, ngs=NGS)
        s = answer["summary"]
        cited = re.findall(r"\[(\d+)\]", " ".join([s["advice"], *(f["text"] for f in s["findings"])]))
        self.assertEqual(list(dict.fromkeys(int(n) for n in cited)), [x["n"] for x in s["sources"]])
        self.assertEqual([x["n"] for x in s["sources"]], list(range(1, len(s["sources"]) + 1)))
        self.assertEqual([x.get("source") for x in s["sources"] if "source" in x], ["FEMA", "NGS", "GCAD", "GCAD"])
        self.assertEqual(s["sources"][0], {"n": 1, "record": "surveys/07-0001.pdf", "job": "07-0001", "kind": "Survey", "date": None})

    def test_with_no_jobs_the_briefing_says_so_and_still_gives_fema_ngs_and_gcad_facts(self):
        text, answer = brief(fema=FEMA, ngs=NGS)
        self.assertEqual(list(text), ["Before you quote", *HEADINGS])
        self.assertEqual(text["Before you quote"], "The Firm has no Jobs within ½ mi. Quote from scratch; the flood, "
                         "Benchmark and parcel findings below still help.")
        self.assertEqual(text["Neighbors"], "The Firm has no Jobs within ½ mi.")
        self.assertIn("[FEMA]", text["Flood then and now"])
        self.assertIn("[NGS]", text["Benchmarks"])
        self.assertIn("[GCAD]", text["Parcel changes"])

    def test_no_owner_name_reaches_the_answer(self):
        _, answer = brief(cert("certs/07-0001.pdf", parcel="1234-0001-0005-000", owner="Jane Q. Homeowner"))
        self.assertNotIn("Homeowner", repr(answer))


if __name__ == "__main__":
    unittest.main()
