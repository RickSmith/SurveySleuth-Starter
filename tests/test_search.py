"""Tests for typed address and Parcel ID search, on made-up GCAD parcels. No Firm data or network."""
import unittest

from surveysleuth.app import search
from surveysleuth.gcad import Gcad
from tests.test_archive import at, build, cert, parcel


def ids(gcad, typed):
    """The Parcel IDs GCAD finds at a typed address."""
    return [p["id"] for p in gcad.at_address(typed)]


class TypedAddress(unittest.TestCase):
    def test_a_typed_address_is_found_in_gcad_situs_whatever_its_case_street_type_city_and_zip(self):
        gcad = Gcad([parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550")])
        for typed in ("12 Sample Drive", "12 sample dr", "12 SAMPLE DR, Galveston", "12 Sample Drive, Galveston, TX 77550",
                      "12 Sample Dr Galveston", "12 sample drive galveston tx 77550", "12 Sample Dr 77550",
                      "12 Sample Dr, 77550", "12 Sample Dr Galveston 77550", "12 Sample Drive, Galveston, Texas 77550"):
            self.assertEqual(ids(gcad, typed), ["1234-0001-0001-000"], typed)

    def test_when_a_street_is_in_two_towns_the_city_or_zip_chooses_and_with_neither_no_parcel_is_found(self):
        gcad = Gcad([parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550"),
                     parcel("5678-0001-0001-000", 900, situs="12 SAMPLE DR TEXAS CITY, TX 77590")])
        for typed in ("12 Sample Dr, Texas City", "12 Sample Drive Texas City", "12 sample dr 77590", "12 Sample Dr, Texas 77590"):
            self.assertEqual(ids(gcad, typed), ["5678-0001-0001-000"], typed)
        self.assertEqual(ids(gcad, "12 Sample Dr, Galveston 77550"), ["1234-0001-0001-000"])
        self.assertEqual(ids(gcad, "12 Sample Dr"), [])

    def test_words_after_the_street_must_be_the_situs_city_state_or_zip_never_another_street(self):
        gcad = Gcad([parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550")])
        self.assertEqual(ids(gcad, "12 Sample Bay Rd"), [])
        self.assertEqual(ids(gcad, "12 Sample Dr League City"), [])


def never(address):
    """A Census Geocoder that must not be asked."""
    raise AssertionError("asked the Census Geocoder")


class TypedSearch(unittest.TestCase):
    def test_a_typed_parcel_id_searches_from_its_parcel_centre(self):
        index, _ = build(cert("certs/07-0001.pdf", at_m=500), parcels=[parcel("1234-0001-0001-000", 300)])
        status, answer = search(index, {}, {"q": " 1234-0001-0001-000 ", "r": "0.25"}, geocoder=never)
        self.assertEqual(status, 200)
        self.assertEqual([round(x, 7) for x in answer["query"]["point"]], [round(x, 7) for x in at(300)])
        self.assertEqual((answer["query"]["parcel_id"], answer["query"]["label"]), ("1234-0001-0001-000", "Parcel 1234-0001-0001-000"))
        self.assertEqual([j["job"] for j in answer["jobs"]], ["07-0001"])  # 200 m from the parcel centre: within ¼ mi
        status, answer = search(index, {}, {"q": "1234-0001-0001-009", "r": "0.25"}, geocoder=never)
        self.assertEqual(answer["query"]["label"], "Parcel 1234-0001-0001-009 (split since: searched from its pieces today)")

    def test_the_census_geocoder_is_asked_only_when_gcad_situs_has_no_such_address(self):
        index, _ = build(parcels=[parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550")])
        asked = []

        def geocoder(address):
            asked.append(address)
            return at(600)
        status, answer = search(index, {}, {"q": "12 Sample Drive 77550", "r": "0.5"}, geocoder)
        self.assertEqual((status, answer["query"]["label"], answer["query"]["parcel_id"], asked),
                         (200, "12 SAMPLE DR GALVESTON, TX 77550", "1234-0001-0001-000", []))
        status, answer = search(index, {}, {"q": "99 Other Road, Galveston", "r": "0.5"}, geocoder)
        self.assertEqual((status, answer["query"]["label"], asked), (200, "99 Other Road, Galveston", ["99 Other Road, Galveston"]))
        self.assertEqual([round(x, 7) for x in answer["query"]["point"]], [round(x, 7) for x in at(600)])

    def test_an_address_that_cannot_be_found_suggests_another_spelling_or_a_parcel_id(self):
        index, _ = build(parcels=[parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550")])
        for geocoder in (lambda a: None, lambda a: (32.78, -96.80)):  # offline or no match; a point outside the county
            status, answer = search(index, {}, {"q": "99 Other Road", "r": "0.5"}, geocoder)
            self.assertEqual(status, 404)
            self.assertIn("spelling", answer["error"])
            self.assertIn("Parcel ID", answer["error"])
        status, answer = search(index, {}, {"q": "1234-0009-0009-000", "r": "0.5"}, never)
        self.assertEqual((status, answer["error"]), (404, "No GCAD parcel has the Parcel ID 1234-0009-0009-000. Check it, or type the address."))

    def test_a_street_in_two_towns_typed_with_no_city_or_zip_asks_for_one_and_never_the_census_geocoder(self):
        index, _ = build(parcels=[parcel("1234-0001-0001-000", 300, situs="12 SAMPLE DR GALVESTON, TX 77550"),
                                  parcel("5678-0001-0001-000", 900, situs="12 SAMPLE DR TEXAS CITY, TX 77590")])
        status, answer = search(index, {}, {"q": "12 Sample Drive", "r": "0.5"}, never)
        self.assertEqual((status, answer["error"]), (404, "That address is in more than one place: "
                         "12 SAMPLE DR GALVESTON, TX 77550; 12 SAMPLE DR TEXAS CITY, TX 77590. Add its city or ZIP."))


if __name__ == "__main__":
    unittest.main()
