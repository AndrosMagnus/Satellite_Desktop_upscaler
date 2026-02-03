import unittest

from app.band_handling import BandHandling


class TestBandHandling(unittest.TestCase):
    def test_labels_match_expected(self) -> None:
        self.assertEqual(
            BandHandling.labels(),
            ["RGB only", "RGB + all bands", "All bands"],
        )

    def test_from_label_round_trip(self) -> None:
        for option in BandHandling:
            self.assertIs(BandHandling.from_label(option.value), option)

    def test_from_label_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            BandHandling.from_label("Infrared")


if __name__ == "__main__":
    unittest.main()
