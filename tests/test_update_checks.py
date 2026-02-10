import json
import tempfile
import unittest
from pathlib import Path

from app.update_checks import UpdatePreferenceStore, UpdatePreferences, check_for_updates


class TestUpdateChecks(unittest.TestCase):
    def test_preference_store_defaults_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UpdatePreferenceStore(path=Path(tmpdir) / "prefs.json")
            pref = store.load()
            self.assertFalse(pref.enabled)

    def test_preference_store_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = UpdatePreferenceStore(path=Path(tmpdir) / "prefs.json")
            store.save(UpdatePreferences(enabled=True))
            pref = store.load()
            self.assertTrue(pref.enabled)

    def test_update_check_without_feed(self) -> None:
        result = check_for_updates(
            current_app_version="0.1.0",
            model_versions={"Real-ESRGAN": "v0.1.0"},
            feed_url=None,
        )
        self.assertFalse(result.app_update_available)
        self.assertEqual(result.model_updates, ())
        self.assertIn("not configured", result.message.lower())

    def test_update_check_with_feed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            feed_path = Path(tmpdir) / "feed.json"
            feed_path.write_text(
                json.dumps(
                    {
                        "app": {"latest": "0.2.0"},
                        "models": {"Real-ESRGAN": "v0.2.0"},
                        "changelog": {
                            "app": [
                                {
                                    "date": "2026-02-10",
                                    "title": "Pipeline improvements",
                                    "details": "Recommendation-driven execution wiring.",
                                }
                            ],
                            "models": [
                                {
                                    "date": "2026-02-09",
                                    "title": "Satlas update",
                                    "details": "Wrapper/runtime fixes.",
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = check_for_updates(
                current_app_version="0.1.0",
                model_versions={"Real-ESRGAN": "v0.1.0"},
                feed_url=feed_path.as_uri(),
            )

        self.assertTrue(result.app_update_available)
        self.assertEqual(result.latest_app_version, "0.2.0")
        self.assertEqual(len(result.model_updates), 1)
        self.assertEqual(result.model_updates[0].name, "Real-ESRGAN")
        self.assertEqual(len(result.app_entries), 1)
        self.assertEqual(result.app_entries[0]["title"], "Pipeline improvements")
        self.assertEqual(len(result.model_entries), 1)
        self.assertEqual(result.model_entries[0]["title"], "Satlas update")


if __name__ == "__main__":
    unittest.main()
