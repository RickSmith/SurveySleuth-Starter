"""Tests for the offline map: the app's tile route and the tile build's county box. No network."""
import tempfile
import unittest
from pathlib import Path

from surveysleuth.app import map_tile
from surveysleuth.tiles import tiles_in_box

JPEG, PNG = b"\xff\xd8\xff\xe0 a jpeg", b"\x89PNG\r\n\x1a\n a png"


class TileRoute(unittest.TestCase):
    def test_the_streets_file_and_aerial_tiles_are_served_with_their_type_and_nothing_else_in_the_tiles_folder(self):
        with tempfile.TemporaryDirectory() as d:
            tiles = Path(d)
            (tiles / "galveston.pmtiles").write_bytes(b"PMTiles")
            (tiles / "USGSImageryOnly/16/100").mkdir(parents=True)
            (tiles / "USGSImageryOnly/16/100/200").write_bytes(JPEG)
            (tiles / "USGSImageryOnly/16/100/201").write_bytes(PNG)  # USGS sends small no-data tiles as PNG
            (tiles / "pmtiles-cli").mkdir()
            (tiles / "pmtiles-cli/pmtiles.exe").write_bytes(b"MZ")
            self.assertEqual(map_tile(tiles, "/tiles/galveston.pmtiles"), (b"PMTiles", "application/octet-stream"))
            self.assertEqual(map_tile(tiles, "/tiles/USGSImageryOnly/16/100/200"), (JPEG, "image/jpeg"))
            self.assertEqual(map_tile(tiles, "/tiles/USGSImageryOnly/16/100/201"), (PNG, "image/png"))
            for refused in ("/tiles/pmtiles-cli/pmtiles.exe",
                            "/tiles/USGSImageryOnly/16/100/202",  # open water: USGS has no tile
                            "/tiles/USGSImageryOnly/16/100",
                            "/tiles/USGSImageryOnly/16/x/200",
                            "/tiles/galveston.pmtiles/"):
                self.assertIsNone(map_tile(tiles, refused), refused)



class CountyBox(unittest.TestCase):
    def test_the_aerial_fetches_every_tile_that_touches_the_county_box(self):
        # The tile ranges and count from the issue #16 research (branch research/offline-tiles)
        self.assertEqual(tiles_in_box(10), (range(241, 244), range(423, 426)))
        self.assertEqual(tiles_in_box(16), (range(15431, 15589), range(27122, 27235)))
        self.assertEqual(sum(len(xs) * len(ys) for xs, ys in map(tiles_in_box, range(10, 17))), 24045)


if __name__ == "__main__":
    unittest.main()
