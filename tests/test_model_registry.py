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
            "license_status",
            "license_acceptance_required",
            "bundled",
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
                model["license_status"], str, f"Model entry {index} license_status must be str"
            )
            self.assertIsInstance(
                model["license_acceptance_required"],
                bool,
                f"Model entry {index} license_acceptance_required must be bool",
            )
            self.assertIsInstance(
                model["bundled"], bool, f"Model entry {index} bundled must be bool"
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

            default_options = model["default_options"]
            for key in ("scale", "tiling", "precision"):
                self.assertIn(
                    key,
                    default_options,
                    f"Model entry {index} default_options missing {key}",
                )
            self.assertIsInstance(
                default_options["scale"],
                int,
                f"Model entry {index} default_options scale must be int",
            )
            self.assertIn(
                default_options["scale"],
                model["scales"],
                f"Model entry {index} default_options scale must be supported by scales",
            )
            self.assertIsInstance(
                default_options["tiling"],
                str,
                f"Model entry {index} default_options tiling must be str",
            )
            self.assertIsInstance(
                default_options["precision"],
                str,
                f"Model entry {index} default_options precision must be str",
            )

    def test_bundled_model_licenses_permissive(self) -> None:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        models_by_name = {model["name"]: model for model in data if isinstance(model, dict)}
        expected_licenses = {
            "Real-ESRGAN": "BSD-3-Clause",
            "Satlas": "Apache-2.0",
        }
        permissive_licenses = {"MIT", "BSD-3-Clause", "Apache-2.0"}

        for name, expected_license in expected_licenses.items():
            self.assertIn(name, models_by_name, f"{name} must be listed in registry.json")
            model = models_by_name[name]
            self.assertTrue(model["bundled"], f"{name} must be marked as bundled")
            license_value = model["license"]
            self.assertEqual(
                license_value,
                expected_license,
                f"{name} license must be {expected_license}",
            )
            self.assertIn(
                license_value,
                permissive_licenses,
                f"{name} license must be permissive",
            )

        bundled_models = [model for model in data if model.get("bundled")]
        for model in bundled_models:
            self.assertIn(
                model["license"],
                permissive_licenses,
                f"Bundled model {model['name']} must have a permissive license",
            )

    def test_pending_license_models_blocked_from_bundling(self) -> None:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        models_by_name = {model["name"]: model for model in data if isinstance(model, dict)}
        self.assertIn("SRGAN adapted to EO", models_by_name)
        self.assertIn("SEN2SR", models_by_name)
        self.assertIn("LDSR-S2", models_by_name)
        self.assertIn("SenGLEAN", models_by_name)

        srgan_model = models_by_name["SRGAN adapted to EO"]
        self.assertEqual(srgan_model["license"], "UNVERIFIED")
        self.assertEqual(srgan_model["license_status"], "unverified")
        self.assertFalse(srgan_model["bundled"])

        sen2sr_model = models_by_name["SEN2SR"]
        self.assertEqual(sen2sr_model["license"], "UNVERIFIED")
        self.assertEqual(sen2sr_model["license_status"], "unverified")
        self.assertFalse(sen2sr_model["bundled"])

        ldsr_model = models_by_name["LDSR-S2"]
        self.assertEqual(ldsr_model["license"], "UNVERIFIED")
        self.assertEqual(ldsr_model["license_status"], "unverified")
        self.assertFalse(ldsr_model["bundled"])

        senglean_model = models_by_name["SenGLEAN"]
        self.assertEqual(senglean_model["license"], "UNVERIFIED")
        self.assertEqual(senglean_model["license_status"], "unverified")
        self.assertFalse(senglean_model["bundled"])

    def test_non_permissive_models_require_license_acceptance(self) -> None:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        models_by_name = {model["name"]: model for model in data if isinstance(model, dict)}
        expected_non_permissive = {
            "Swin2-MoSE": "GPL-2.0",
            "DSen2": "GPL-3.0",
        }

        for name, license_id in expected_non_permissive.items():
            self.assertIn(name, models_by_name, f"{name} must be listed in registry.json")
            model = models_by_name[name]
            self.assertEqual(
                model["license"],
                license_id,
                f"{name} license must be {license_id}",
            )
            self.assertFalse(model["bundled"], f"{name} must not be bundled")
            self.assertTrue(
                model["license_acceptance_required"],
                f"{name} must require explicit license acceptance",
            )


if __name__ == "__main__":
    unittest.main()
