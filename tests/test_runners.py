"""Check runner selection in workflows rendered by the real Orcastrate CLI."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
COMMAND = shlex.split(os.environ.get('ORCASTRATE', 'orcastrate'))


class RunnerTest(unittest.TestCase):
    def render(self, source, override=None):
        if override is not None:
            if '# params:\n' not in source:
                source = source.replace('# @end-orcastrate', '# params:\n# @end-orcastrate')
            source = source.replace('# params:\n', '# params:\n#   custom_runner: ' + json.dumps(override) + '\n')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.fixture', dir=ROOT / 'fixtures') as fixture:
            fixture.write(source)
            fixture.flush()
            return subprocess.check_output(COMMAND + ['render', str(Path(fixture.name).relative_to(ROOT))], cwd=ROOT, text=True)

    def test_every_template_has_a_fixture(self):
        covered = {re.search(r'^# template: (.+)$', p.read_text(), re.M)[1]
                   for p in (ROOT / 'fixtures').glob('*.yml')}
        templates = {p.relative_to(ROOT / 'templates').with_suffix('').as_posix()
                     for p in (ROOT / 'templates').rglob('*.yml')}
        self.assertFalse(templates - covered)

    def test_runner_defaults_and_overrides(self):
        for fixture in sorted((ROOT / 'fixtures').glob('*.yml')):
            source = fixture.read_text()
            if '#   custom_runner:' in source:
                continue
            with self.subTest(fixture=fixture.name):
                default = self.render(source)
                runners = re.findall(r'^\s+runs-on: (.+)$', default, re.M)
                self.assertTrue(runners)
                self.assertNotIn('ubicloud-', default)
                for runner in runners:
                    self.assertRegex(runner, r'^(ubuntu-|windows-|macos-|\$\{\{ matrix\.)')
                for override in ['ubicloud-standard-2', ['self-hosted', 'linux', 'x64'],
                                 "${{ vars.CI_RUNNER || 'ubuntu-24.04' }}"]:
                    rendered = self.render(source, override)
                    actual = re.findall(r'^\s+runs-on: (.+)$', rendered, re.M)
                    expected = json.dumps(override) if isinstance(override, list) else override
                    self.assertEqual(actual, [expected] * len(runners))

    def test_platform_defaults_are_preserved(self):
        expectations = {
            'rust-ci-matrix.yml': ['macos-latest', 'windows-latest', 'runs-on: ${{ matrix.os }}'],
            'rust-release-vscli.yml': ['runs-on: ${{ matrix.os }}', 'os: windows-latest'],
            'projects-codetend-ci.yml': ["matrix.platform == 'linux/amd64' && 'ubuntu-24.04' || 'ubuntu-24.04-arm'"],
            'projects-divetracx-ci.yml': ['runner: ubuntu-24.04-arm', 'runs-on: ${{ matrix.runner }}'],
        }
        for name, expected in expectations.items():
            with self.subTest(fixture=name):
                rendered = self.render((ROOT / 'fixtures' / name).read_text())
                for value in expected:
                    self.assertIn(value, rendered)
