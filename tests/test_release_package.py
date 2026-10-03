import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

REPO = Path(__file__).resolve().parents[1]
BUILDER = REPO / "scripts" / "build_release.py"


class ReleasePackageTest(unittest.TestCase):
    def test_release_zip_is_clean_and_installable(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "K1-Klipper-Eddy-ci-test.zip"
            subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--version", "ci-test",
                    "--output", str(output),
                ],
                cwd=REPO,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertTrue(output.exists())

            prefix = "K1-Klipper-Eddy-ci-test/"
            with zipfile.ZipFile(output) as zf:
                names = sorted(zf.namelist())

                required = {
                    prefix + "README.md",
                    prefix + "LICENSE",
                    prefix + "install.sh",
                    prefix + "scripts/k1max_cfs_eddy.py",
                    prefix + "klippy/extras/eddy_z_acquire.py",
                    prefix + "klippy/extras/upgrade/ldc1612.py",
                    prefix + "config/btteddy.cfg",
                    prefix + "docs/K1MAX-CFS-EDDY-DUO-23533.md",
                    prefix + "docs/CREALITY-HELPER-SCRIPT.md",
                    prefix + "docs/RELEASE-CHECKLIST.md",
                    prefix + "RELEASE-MANIFEST.json",
                }
                self.assertTrue(required.issubset(set(names)))

                self.assertFalse(
                    any("/tests/" in name for name in names)
                )
                self.assertFalse(
                    any("/.github/" in name for name in names)
                )
                self.assertFalse(
                    any("__pycache__" in name for name in names)
                )
                self.assertFalse(
                    any(name.endswith(".pyc") for name in names)
                )

                manifest = json.loads(
                    zf.read(prefix + "RELEASE-MANIFEST.json")
                )
                self.assertEqual(
                    manifest["target_firmware"], "2.3.5.33"
                )
                self.assertEqual(
                    manifest["production_reference"],
                    "known-good-eddy-production-20261001-153849",
                )
                self.assertEqual(
                    manifest["entrypoint"], "install.sh"
                )

    def test_identical_source_builds_identical_zip(self):
        with tempfile.TemporaryDirectory() as td:
            first = Path(td) / "a.zip"
            second = Path(td) / "b.zip"
            for output in (first, second):
                subprocess.run(
                    [
                        sys.executable,
                        str(BUILDER),
                        "--version", "ci-test",
                        "--output", str(output),
                    ],
                    cwd=REPO,
                    text=True,
                    capture_output=True,
                    check=True,
                )
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
