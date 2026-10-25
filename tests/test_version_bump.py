"""Exercise the version calculation embedded in the workflow template."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

TEMPLATE = (Path(__file__).resolve().parents[1] / "templates/rust-bump-version.yml").read_text()
START = TEMPLATE.index('          current="$(printf')
END = TEMPLATE.index('\n      - name: Install cargo-edit', START)
SCRIPT = textwrap.dedent(TEMPLATE[START:END])


class VersionBumpTest(unittest.TestCase):
    def calculate(self, versions, bump, tag_exists=False):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "env"
            cliff = Path(directory) / "git-cliff/bin/git-cliff"
            cliff.parent.mkdir(parents=True)
            cliff.write_text("#!/bin/sh\nprintf '1.2.3\\n'\n")
            cliff.chmod(0o755)
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c",
                 'versions=("$@")\ngit() { return "$TAG_STATUS"; }\n' + SCRIPT,
                 "test", *versions],
                env={**os.environ, "BUMP_TYPE": bump, "GITHUB_ENV": str(output),
                     "TAG_STATUS": "0" if tag_exists else "1", "RUNNER_TEMP": directory},
                text=True, capture_output=True,
            )
            return result, output.read_text() if output.exists() else ""

    def test_bumps(self):
        for current, bump, expected in [
            ("1.2.3", "patch", "1.2.4"),
            ("1.2.3", "minor", "1.3.0"),
            ("1.2.3", "major", "2.0.0"),
            ("0.0.0", "patch", "0.0.1"),
            ("0.0.0", "minor", "0.1.0"),
            ("0.0.0", "major", "1.0.0"),
            ("1.2.9", "patch", "1.2.10"),
        ]:
            with self.subTest(current=current, bump=bump):
                result, output = self.calculate([current, current], bump)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(output, f"VERSION={expected}\n")

    def test_invalid_inputs(self):
        for versions, bump in [
            (["1.2.3", "1.2.4"], "patch"),
            (["1.2.3-beta.1"], "patch"),
            (["01.2.3"], "patch"),
            ([""], "patch"),
            (["1.2.3"], "invalid"),
        ]:
            with self.subTest(versions=versions, bump=bump):
                result, output = self.calculate(versions, bump)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output, "")
                self.assertIn("::error::", result.stdout)

    def test_existing_tag_fails(self):
        result, _ = self.calculate(["1.2.3"], "patch", tag_exists=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("next version tag already exists", result.stdout)

    def test_calculated_version_cannot_be_older_than_cargo_version(self):
        result, output = self.calculate(["2.0.0"], "auto")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output, "")
        self.assertIn("older than the current Cargo version", result.stdout)


if __name__ == "__main__":
    unittest.main()
