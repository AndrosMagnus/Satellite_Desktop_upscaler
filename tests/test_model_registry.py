import json
import unittest
from pathlib import Path


class TestModelRegistry(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.registry_path = repo_root / "models" / "registry.json"

    def test_registry_exists(self) -> None:
        self.assertTrue(self.registry_path.is_file(), "models/registry.json is missing")

    def test_registry_schema(self) -> None:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        self.assertIsInstance(data, list, "registry.json must be a list of models")
        self.assertGreater(len(data), 0, "registry.json must contain at least one model")

        required_fields = {
            "name",
            "source_url",
            "license",
            "gpu_required",
            "cpu_supported",
            "bands_supported",
            "scales",
            "weights_url",
            "checksum",
            "default_options",
        }

        for index, model in enumerate(data):
            self.assertIsInstance(model, dict, f"Model entry {index} must be an object")
            missing = required_fields - model.keys()
            self.assertEqual(
                missing,
                set(),
                f"Model entry {index} missing required fields: {sorted(missing)}",
            )

            self.assertIsInstance(model["name"], str, f"Model entry {index} name must be str")
            self.assertIsInstance(
                model["source_url"], str, f"Model entry {index} source_url must be str"
            )
            self.assertIsInstance(
                model["license"], str, f"Model entry {index} license must be str"
            )
            self.assertIsInstance(
                model["gpu_required"], bool, f"Model entry {index} gpu_required must be bool"
            )
            self.assertIsInstance(
                model["cpu_supported"], bool, f"Model entry {index} cpu_supported must be bool"
            )
            self.assertIsInstance(
                model["bands_supported"], list, f"Model entry {index} bands_supported must be list"
            )
            self.assertIsInstance(
                model["scales"], list, f"Model entry {index} scales must be list"
            )
            self.assertIsInstance(
                model["weights_url"], str, f"Model entry {index} weights_url must be str"
            )
            self.assertIsInstance(
                model["checksum"], str, f"Model entry {index} checksum must be str"
            )
            self.assertIsInstance(
                model["default_options"], dict,
                f"Model entry {index} default_options must be object",
            )

            self.assertTrue(model["name"], f"Model entry {index} name must not be empty")
            self.assertTrue(
                model["source_url"], f"Model entry {index} source_url must not be empty"
            )
            self.assertTrue(
                model["weights_url"], f"Model entry {index} weights_url must not be empty"
            )


if __name__ == "__main__":
    unittest.main()
