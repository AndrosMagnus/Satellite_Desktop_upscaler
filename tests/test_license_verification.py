import json
import unittest
from pathlib import Path


class TestLicenseVerification(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.verification_path = repo_root / "models" / "license_verification.json"
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_json(self, path: Path):
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def test_verification_file_exists(self) -> None:
        self.assertTrue(
            self.verification_path.is_file(),
            "models/license_verification.json is missing",
        )

    def test_verification_schema(self) -> None:
        data = self._load_json(self.verification_path)
        self.assertIsInstance(data, list, "license_verification.json must be a list")
        self.assertGreater(len(data), 0, "license_verification.json must contain entries")

        required_fields = {"name", "license", "source_url", "verified_at"}
        for index, entry in enumerate(data):
            self.assertIsInstance(entry, dict, f"Entry {index} must be an object")
            missing = required_fields - entry.keys()
            self.assertEqual(
                missing,
                set(),
                f"Entry {index} missing required fields: {sorted(missing)}",
            )
            self.assertEqual(
                set(entry.keys()),
                required_fields,
                f"Entry {index} must only contain required fields",
            )
            for key in required_fields:
                self.assertIsInstance(
                    entry[key],
                    str,
                    f"Entry {index} {key} must be a string",
                )
                self.assertTrue(
                    entry[key],
                    f"Entry {index} {key} must not be empty",
                )

    def test_bundled_model_licenses_verified(self) -> None:
        verification = self._load_json(self.verification_path)
        registry = self._load_json(self.registry_path)
        registry_by_name = {entry["name"]: entry for entry in registry}

        bundled_models = {
            "Real-ESRGAN": "BSD-3-Clause",
            "Satlas": "Apache-2.0",
        }
        permissive_licenses = {"MIT", "BSD-3-Clause", "Apache-2.0"}
        verification_by_name = {entry["name"]: entry for entry in verification}

        for name, expected_license in bundled_models.items():
            self.assertIn(
                name,
                verification_by_name,
                f"{name} must be listed in license_verification.json",
            )
            verification_entry = verification_by_name[name]
            self.assertEqual(
                verification_entry["license"],
                expected_license,
                f"{name} license should be {expected_license}",
            )
            registry_entry = registry_by_name.get(name)
            self.assertIsNotNone(registry_entry, f"{name} missing from registry.json")
            self.assertEqual(
                registry_entry["license"],
                verification_entry["license"],
                f"{name} license mismatch between registry and verification",
            )
            self.assertIn(
                verification_entry["license"],
                permissive_licenses,
                f"{name} license must be permissive",
            )

    def test_confirmed_models_not_bundled(self) -> None:
        verification = self._load_json(self.verification_path)
        registry = self._load_json(self.registry_path)
        registry_by_name = {entry["name"]: entry for entry in registry}
        verification_by_name = {entry["name"]: entry for entry in verification}

        confirmed_optional_models = {
            "SRGAN adapted to EO": "Apache-2.0",
            "SenGLEAN": "etalab-2.0",
        }
        for name, expected_license in confirmed_optional_models.items():
            self.assertIn(
                name,
                verification_by_name,
                f"{name} must be listed in license_verification.json",
            )
            verification_entry = verification_by_name[name]
            self.assertEqual(
                verification_entry["license"],
                expected_license,
                f"{name} license should be {expected_license}",
            )
            registry_entry = registry_by_name.get(name)
            self.assertIsNotNone(registry_entry, f"{name} missing from registry.json")
            self.assertEqual(
                registry_entry["license"],
                expected_license,
                f"{name} license mismatch between registry and verification",
            )
            self.assertFalse(
                bool(registry_entry.get("bundled")),
                f"{name} must not be bundled in default distribution artifacts",
            )


if __name__ == "__main__":
    unittest.main()
