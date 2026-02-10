import unittest
from pathlib import Path


class TestPackagingAssets(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[1]

    def test_pyinstaller_spec_exists(self) -> None:
        spec = self.repo_root / "packaging" / "pyinstaller" / "satellite_upscale.spec"
        self.assertTrue(spec.is_file(), "PyInstaller spec is missing")

    def test_platform_packaging_scripts_exist(self) -> None:
        windows = self.repo_root / "scripts" / "package_windows.ps1"
        macos = self.repo_root / "scripts" / "package_macos.sh"
        linux = self.repo_root / "scripts" / "package_linux.sh"
        self.assertTrue(windows.is_file(), "Windows packaging script missing")
        self.assertTrue(macos.is_file(), "macOS packaging script missing")
        self.assertTrue(linux.is_file(), "Linux packaging script missing")

    def test_windows_installer_wix_template_exists(self) -> None:
        wix = self.repo_root / "packaging" / "windows" / "installer.wxs"
        self.assertTrue(wix.is_file(), "Windows WiX installer template missing")


if __name__ == "__main__":
    unittest.main()
