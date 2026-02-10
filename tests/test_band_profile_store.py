import tempfile
import unittest
from pathlib import Path

from app.band_profile_store import BandProfileStore
from app.imagery_policy import RgbBandMapping


class TestBandProfileStore(unittest.TestCase):
    def test_save_and_load_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "profiles.json"
            store = BandProfileStore(path=path)
            mapping = RgbBandMapping(red=3, green=2, blue=1, source="test")

            store.save_mapping("Sentinel-2", "MSI-L2A", mapping)
            loaded = store.load_mapping("Sentinel-2", "MSI-L2A")

            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual((loaded.red, loaded.green, loaded.blue), (3, 2, 1))

    def test_load_missing_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = BandProfileStore(path=Path(tmpdir) / "profiles.json")
            self.assertIsNone(store.load_mapping("PlanetScope", "PSScene-4Band"))


if __name__ == "__main__":
    unittest.main()
