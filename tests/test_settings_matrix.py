import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("settings_matrix", ROOT / "scripts/settings-matrix.py")
settings_matrix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(settings_matrix)


class SettingsInventoryTests(unittest.TestCase):
    def test_uses_complete_orcastrate_inventory(self):
        names = settings_matrix.select_repositories(ROOT / "orchestrator.toml")
        self.assertIn("michidk/rost", names)
        self.assertIn("michidk/CodeTend", names)
        self.assertEqual(["michidk/rost"], settings_matrix.select_repositories(
            ROOT / "orchestrator.toml", "michidk/rost"))

    def test_rejects_target_outside_inventory(self):
        with self.assertRaisesRegex(ValueError, "not managed"):
            settings_matrix.select_repositories(ROOT / "orchestrator.toml", "michidk/unmanaged")

    def test_rejects_empty_or_duplicate_inventory(self):
        for config in ('repos = []', 'repos = [{name = "a/b"}, {name = "a/b"}]'):
            with self.subTest(config=config), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "orchestrator.toml"
                path.write_text(config)
                with self.assertRaises(ValueError):
                    settings_matrix.select_repositories(path)
